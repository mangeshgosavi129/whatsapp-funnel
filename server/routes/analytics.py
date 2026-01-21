from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import Dict
from server.dependencies import get_db
from server.dependencies import get_auth_context
from server.models import Message, Conversation
from server.schemas import AnalyticsReportOut, AuthContext
from server.enums import MessageFrom, UserSentiment, IntentLevel

router = APIRouter()

@router.get("/", response_model=AnalyticsReportOut)
def get_analytics(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    # 1. Sentiment breakdown (from conversations)
    sentiment_query = db.query(
        Conversation.user_sentiment, 
        func.count(Conversation.id)
    ).filter(
        Conversation.organization_id == auth.organization_id,
        Conversation.user_sentiment.isnot(None)
    ).group_by(Conversation.user_sentiment).all()
    
    sentiment_breakdown = {s.value if s else "Unknown": count for s, count in sentiment_query}

    # 2. Peak activity time (from messages) - Hourly distribution
    peak_query = db.query(
        extract('hour', Message.created_at).label('hour'),
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
        Conversation.organization_id == auth.organization_id,
        Conversation.intent_level.isnot(None)
    ).group_by(Conversation.intent_level).all()
    
    intent_level_stats = {i.value if i else "Unknown": count for i, count in intent_query}

    return AnalyticsReportOut(
        sentiment_breakdown=sentiment_breakdown,
        peak_activity_time=peak_activity_time,
        message_from_stats=message_from_stats,
        intent_level_stats=intent_level_stats
    )
