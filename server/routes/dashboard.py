from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..dependencies import get_auth_context
from ..schemas import DashboardStatsOut, AuthContext
from ..models import Conversation, Message, Lead
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/stats", response_model=DashboardStatsOut)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    # This is a sample implementation. In a real app, you'd aggregate these from the DB.
    total_conversations = db.query(Conversation).filter(Conversation.organization_id == auth.organization_id).count()
    total_messages = db.query(Message).filter(Message.organization_id == auth.organization_id).count()
    active_leads = db.query(Lead).filter(Lead.organization_id == auth.organization_id).count()
    
    # Mock data for complex metrics
    peak_hours = {"09:00": 10, "12:00": 25, "15:00": 15, "18:00": 30}
    sentiment_breakdown = {"Positive": 60, "Neutral": 30, "Negative": 10}
    
    return DashboardStatsOut(
        total_conversations=total_conversations,
        total_messages=total_messages,
        active_leads=active_leads,
        peak_hours=peak_hours,
        sentiment_breakdown=sentiment_breakdown
    )
