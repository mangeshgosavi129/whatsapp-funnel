from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from server.dependencies import get_db
from server.dependencies import get_auth_context
from server.models import Message, Conversation
from server.schemas import AnalyticsReportOut, AuthContext

router = APIRouter()

from datetime import datetime, timedelta

@router.get("", response_model=AnalyticsReportOut)
def get_analytics(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    # Timezone offset for IST (UTC+5:30)
    # Using text-based interval for PostgreSQL if possible, but since we are using 'extract', 
    # we should ideally shift the timestamp before extracting.
    # In SQLAlchemy with PostgreSQL: func.timezone('Asia/Kolkata', Message.created_at)
    
    # 1. Sentiment breakdown (from conversations)
    sentiment_query = db.query(
        Conversation.user_sentiment, 
        func.count(Conversation.id)
    ).filter(
        Conversation.organization_id == auth.organization_id
    ).group_by(Conversation.user_sentiment).all()
    
    sentiment_breakdown = {s.value if s else "Unknown": count for s, count in sentiment_query}

    # 2. Peak activity time (from messages) - Hourly distribution in IST
    peak_query = db.query(
        extract('hour', func.timezone('IST', Message.created_at)).label('hour'),
        func.count(Message.id)
    ).filter(
        Message.organization_id == auth.organization_id
    ).group_by('hour').all()
    
    peak_activity_time = {str(int(hour)): count for hour, count in peak_query}

    # 3. message_from stats (from messages)
    from_query = db.query(
        Message.message_from,
        func.count(Message.id)
    ).filter(
        Message.organization_id == auth.organization_id
    ).group_by(Message.message_from).all()
    
    message_from_stats = {f.value if f else "Unknown": count for f, count in from_query}

    # 4. Intent level stats (from conversations)
    intent_query = db.query(
        Conversation.intent_level,
        func.count(Conversation.id)
    ).filter(
        Conversation.organization_id == auth.organization_id
    ).group_by(Conversation.intent_level).all()
    
    intent_level_stats = {i.value if i else "Unknown": count for i, count in intent_query}

    # 5. Daily activity (Last 14 days)
    fourteen_days_ago = datetime.utcnow() - timedelta(days=14)
    daily_query = db.query(
        func.date(func.timezone('IST', Message.created_at)).label('date'),
        func.count(Message.id)
    ).filter(
        Message.organization_id == auth.organization_id,
        Message.created_at >= fourteen_days_ago
    ).group_by('date').order_by('date').all()
    
    daily_activity = {str(row.date): row[1] for row in daily_query}

    # 6. Stage breakdown (from conversations)
    stage_query = db.query(
        Conversation.stage,
        func.count(Conversation.id)
    ).filter(
        Conversation.organization_id == auth.organization_id
    ).group_by(Conversation.stage).all()
    
    stage_breakdown = {s.value if s else "Unknown": count for s, count in stage_query}

    return AnalyticsReportOut(
        sentiment_breakdown=sentiment_breakdown,
        peak_activity_time=peak_activity_time,
        message_from_stats=message_from_stats,
        intent_level_stats=intent_level_stats,
        daily_activity=daily_activity,
        stage_breakdown=stage_breakdown
    )
