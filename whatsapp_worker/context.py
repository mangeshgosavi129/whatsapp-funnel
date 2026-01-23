"""
Context Builder for HTL Pipeline.
Gathers all necessary context from database to run the pipeline.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from llm.schemas import (
    PipelineInput, MessageContext, TimingContext, NudgeContext
)
from server.models import (
    Conversation, Lead, Message, Organization, 
    WhatsAppIntegration
)
from server.enums import (
    ConversationStage, ConversationMode, IntentLevel, 
    UserSentiment, MessageFrom
)

logger = logging.getLogger(__name__)


def get_organization_by_phone_number_id(
    db: Session, 
    phone_number_id: str
) -> Optional[Tuple[Organization, WhatsAppIntegration]]:
    """
    Find organization by WhatsApp phone_number_id.
    
    Returns:
        Tuple of (Organization, WhatsAppIntegration) or None
    """
    integration = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.phone_number_id == phone_number_id,
        WhatsAppIntegration.is_connected == True
    ).first()
    
    if not integration:
        logger.warning(f"No integration found for phone_number_id: {phone_number_id}")
        return None
    
    org = db.query(Organization).filter(
        Organization.id == integration.organization_id,
        Organization.is_active == True
    ).first()
    
    if not org:
        logger.warning(f"Organization not found or inactive: {integration.organization_id}")
        return None
    
    return org, integration


def get_or_create_lead(
    db: Session,
    organization_id: UUID,
    phone: str,
    contact_name: Optional[str] = None
) -> Lead:
    """
    Get existing lead or create new one.
    """
    lead = db.query(Lead).filter(
        Lead.organization_id == organization_id,
        Lead.phone == phone
    ).first()
    
    if not lead:
        lead = Lead(
            organization_id=organization_id,
            phone=phone,
            name=contact_name,
            conversation_stage=ConversationStage.GREETING,
            intent_level=IntentLevel.UNKNOWN,
            user_sentiment=UserSentiment.NEUTRAL,
        )
        db.add(lead)
        db.flush()
        logger.info(f"Created new lead: {lead.id} for phone {phone}")
    elif contact_name and not lead.name:
        lead.name = contact_name
        db.flush()
    
    return lead


def get_or_create_conversation(
    db: Session,
    organization_id: UUID,
    lead_id: UUID,
) -> Tuple[Conversation, bool]:
    """
    Get existing conversation or create new one.
    
    Returns:
        Tuple of (Conversation, is_new)
    """
    conv = db.query(Conversation).filter(
        Conversation.organization_id == organization_id,
        Conversation.lead_id == lead_id,
    ).order_by(Conversation.created_at.desc()).first()
    
    is_new = False
    
    if not conv:
        is_new = True
        conv = Conversation(
            organization_id=organization_id,
            lead_id=lead_id,
            stage=ConversationStage.GREETING,
            mode=ConversationMode.BOT,
            intent_level=IntentLevel.UNKNOWN,
            user_sentiment=UserSentiment.NEUTRAL,
            rolling_summary="",
            followup_count_24h=0,
            total_nudges=0,
        )
        db.add(conv)
        db.flush()
        logger.info(f"Created new conversation: {conv.id}")
    
    return conv, is_new


def get_last_messages(
    db: Session,
    conversation_id: UUID,
    limit: int = 3
) -> List[MessageContext]:
    """
    Get last N messages for context.
    """
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.desc()).limit(limit).all()
    
    # Reverse to get chronological order
    messages = list(reversed(messages))
    
    result = []
    for msg in messages:
        sender = "lead" if msg.message_from == MessageFrom.LEAD else (
            "bot" if msg.message_from == MessageFrom.BOT else "human"
        )
        result.append(MessageContext(
            sender=sender,
            text=msg.content[:500],  # Limit text for token efficiency
            timestamp=msg.created_at.isoformat() if msg.created_at else "",
        ))
    
    return result


def calculate_whatsapp_window(last_user_message_at: Optional[datetime]) -> bool:
    """
    Check if WhatsApp 24-hour messaging window is open.
    
    WhatsApp Business API allows sending messages without templates
    only within 24 hours of the last user message.
    """
    if not last_user_message_at:
        return False  # No user message = no window
    
    # Ensure timezone-aware comparison
    now = datetime.now(timezone.utc)
    if last_user_message_at.tzinfo is None:
        # Assume UTC if no timezone
        last_user_message_at = last_user_message_at.replace(tzinfo=timezone.utc)
    
    window_end = last_user_message_at + timedelta(hours=24)
    
    return now < window_end


def build_pipeline_context(
    db: Session,
    organization: Organization,
    conversation: Conversation,
    lead: Lead,
) -> PipelineInput:
    """
    Build complete pipeline context from database state.
    """
    # Get last messages
    last_messages = get_last_messages(db, conversation.id, limit=3)
    
    # Get current time in ISO format
    now = datetime.now(timezone.utc)
    now_local = now.isoformat()
    
    # Calculate WhatsApp window
    whatsapp_window = calculate_whatsapp_window(conversation.last_user_message_at)
    
    # Build timing context
    timing = TimingContext(
        now_local=now_local,
        last_user_message_at=conversation.last_user_message_at.isoformat() if conversation.last_user_message_at else None,
        last_bot_message_at=conversation.last_bot_message_at.isoformat() if conversation.last_bot_message_at else None,
        whatsapp_window_open=whatsapp_window,
    )
    
    # Build nudge context
    nudges = NudgeContext(
        followup_count_24h=conversation.followup_count_24h or 0,
        total_nudges=conversation.total_nudges or 0,
    )
    
    # Build pipeline input
    context = PipelineInput(
        # Business context
        business_name=organization.name,
        business_description="",  # TODO: Add from BusinessConfig when implemented
        
        # Conversation context
        rolling_summary=conversation.rolling_summary or "",
        last_3_messages=last_messages,
        
        # Current state
        conversation_stage=conversation.stage,
        conversation_mode=conversation.mode.value,
        intent_level=conversation.intent_level or IntentLevel.UNKNOWN,
        user_sentiment=conversation.user_sentiment or UserSentiment.NEUTRAL,
        active_cta=None,  # TODO: Get active CTA if any
        
        # Timing
        timing=timing,
        nudges=nudges,
        
        # Constraints (defaults for now)
        max_words=80,
        questions_per_message=1,
        language_pref="en",
    )
    
    return context


def store_incoming_message(
    db: Session,
    conversation: Conversation,
    lead: Lead,
    message_text: str,
) -> Message:
    """
    Store incoming user message and update conversation timestamps.
    """
    now = datetime.now(timezone.utc)
    
    # Create message record
    message = Message(
        organization_id=conversation.organization_id,
        conversation_id=conversation.id,
        lead_id=lead.id,
        message_from=MessageFrom.LEAD,
        content=message_text,
        status="received",
    )
    db.add(message)
    
    # Update conversation timestamps
    conversation.last_message = message_text[:500]
    conversation.last_message_at = now
    conversation.last_user_message_at = now
    
    db.flush()
    
    return message
