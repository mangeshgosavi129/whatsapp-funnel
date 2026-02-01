from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.dependencies import get_db
from server.dependencies import get_auth_context
from server.schemas import DashboardStatsOut, AuthContext
from server.models import Conversation, Message, Lead
from server.enums import IntentLevel
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
    
    # High Intent Leads
    high_intent_leads = db.query(Lead).filter(
        Lead.organization_id == auth.organization_id,
        Lead.intent_level.in_([IntentLevel.HIGH, IntentLevel.VERY_HIGH])
    ).count()

    # Action Items: Conversations needing human attention
    needs_attention = db.query(Conversation, Lead).join(Lead).filter(
        Conversation.organization_id == auth.organization_id,
        Conversation.needs_human_attention == True
    ).limit(5).all()

    action_items = []
    for conv, lead in needs_attention:
        action_items.append({
            "type": "human_needed",
            "message": f"{lead.name} needs human attention",
            "time": conv.updated_at.isoformat() if conv.updated_at else "",
            "conversation_id": str(conv.id)
        })

    # Empty metrics instead of mock data
    peak_hours = {}
    sentiment_breakdown = {}
    
    return DashboardStatsOut(
        total_conversations=total_conversations,
        total_messages=total_messages,
        active_leads=active_leads,
        peak_hours=peak_hours,
        sentiment_breakdown=sentiment_breakdown,
        high_intent_leads=high_intent_leads,
        action_items=action_items
    )
