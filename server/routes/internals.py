"""
Internal API Endpoints for WhatsApp Worker.

This module provides the single authorized layer for database access
from the whatsapp_worker module. All database operations should go
through these endpoints.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from server.services.websocket_events import emit_conversation_updated
from server.schemas import ConversationOut
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session
from server.dependencies import require_internal_secret, get_db
import logging
from server.models import (
    Conversation, ConversationEvent, Lead, Message, Organization,
    ScheduledAction, WhatsAppIntegration, CTA
)
from server.enums import (
    ConversationMode, ConversationStage, IntentLevel, MessageFrom,
    ScheduledActionStatus, UserSentiment
)
from server.schemas import (
    InternalConversationCreate, InternalConversationOut, InternalConversationUpdate,
    InternalFollowupContext, InternalIncomingMessageCreate, InternalIntegrationWithOrgOut,
    InternalLeadCreate, InternalLeadOut, InternalMessageContext, InternalMessageOut,
    InternalOutgoingMessageCreate, InternalPipelineEventCreate, InternalPipelineEventOut,
    InternalScheduledActionCreate, InternalScheduledActionOut, InternalScheduledActionUpdate, 
    CTAOut
)

router = APIRouter()

# ========================================
# WhatsApp Integration Endpoints
# ========================================

def _integration_to_payload(integration: WhatsAppIntegration) -> dict:
    return {
        "id": str(integration.id),
        "organization_id": str(integration.organization_id),
        "access_token": integration.access_token,
        "version": integration.version,
        "app_secret": integration.app_secret,
        "phone_number_id": integration.phone_number_id,
        "is_connected": integration.is_connected,
    }


@router.get("/whatsapp/by-phone-number-id/{phone_number_id}")
def get_whatsapp_integration_by_phone_number_id(
    phone_number_id: str,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    integration = (
        db.query(WhatsAppIntegration)
        .filter(WhatsAppIntegration.phone_number_id == phone_number_id)
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="WhatsApp integration not found")
    if not integration.is_connected:
        raise HTTPException(status_code=409, detail="WhatsApp integration not connected")
    return _integration_to_payload(integration)


@router.get("/whatsapp/by-organization-id/{organization_id}")
def get_whatsapp_integration_by_organization_id(
    organization_id: str,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    integration = (
        db.query(WhatsAppIntegration)
        .filter(WhatsAppIntegration.organization_id == organization_id)
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="WhatsApp integration not found")
    if not integration.is_connected:
        raise HTTPException(status_code=409, detail="WhatsApp integration not connected")
    return _integration_to_payload(integration)


@router.get(
    "/whatsapp/by-phone-number-id/{phone_number_id}/with-org",
    response_model=InternalIntegrationWithOrgOut
)
def get_integration_with_org(
    phone_number_id: str,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Get WhatsApp integration along with organization data."""
    integration = (
        db.query(WhatsAppIntegration)
        .filter(
            WhatsAppIntegration.phone_number_id == phone_number_id,
            WhatsAppIntegration.is_connected == True
        )
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="WhatsApp integration not found")

    org = (
        db.query(Organization)
        .filter(
            Organization.id == integration.organization_id,
            Organization.is_active == True
        )
        .first()
    )
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found or inactive")

    return InternalIntegrationWithOrgOut(
        integration_id=integration.id,
        access_token=integration.access_token,
        version=integration.version,
        app_secret=integration.app_secret,
        phone_number_id=integration.phone_number_id,
        is_connected=integration.is_connected,
        organization_id=org.id,
        organization_name=org.name,
        is_active=org.is_active,
        business_name=org.business_name,
        business_description=org.business_description,
        flow_prompt=org.flow_prompt,
    )


@router.get("/organizations/{organization_id}/ctas", response_model=List[CTAOut])
def get_organization_ctas(
    organization_id: UUID,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Get active CTAs for an organization."""
    return (
        db.query(CTA)
        .filter(CTA.organization_id == organization_id, CTA.is_active == True)
        .all()
    )


# ========================================
# Lead Endpoints
# ========================================

def _lead_to_schema(lead: Lead) -> InternalLeadOut:
    return InternalLeadOut(
        id=lead.id,
        organization_id=lead.organization_id,
        phone=lead.phone,
        name=lead.name,
        email=lead.email,
        company=lead.company,
        conversation_stage=lead.conversation_stage,
        intent_level=lead.intent_level,
        user_sentiment=lead.user_sentiment,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


@router.get("/leads/by-phone", response_model=Optional[InternalLeadOut])
def get_lead_by_phone(
    organization_id: UUID,
    phone: str,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Get lead by organization ID and phone number."""
    lead = (
        db.query(Lead)
        .filter(Lead.organization_id == organization_id, Lead.phone == phone)
        .first()
    )
    if not lead:
        return None
    return _lead_to_schema(lead)


@router.post("/leads", response_model=InternalLeadOut, status_code=201)
def create_lead(
    payload: InternalLeadCreate,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Create a new lead."""
    lead = Lead(
        organization_id=payload.organization_id,
        phone=payload.phone,
        name=payload.name,
        conversation_stage=ConversationStage.GREETING,
        intent_level=IntentLevel.UNKNOWN,
        user_sentiment=UserSentiment.NEUTRAL,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return _lead_to_schema(lead)


@router.patch("/leads/{lead_id}", response_model=InternalLeadOut)
def update_lead(
    lead_id: UUID,
    name: Optional[str] = None,
    conversation_stage: Optional[ConversationStage] = None,
    intent_level: Optional[IntentLevel] = None,
    user_sentiment: Optional[UserSentiment] = None,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Update lead details."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if name is not None:
        lead.name = name
    if conversation_stage is not None:
        lead.conversation_stage = conversation_stage
    if intent_level is not None:
        lead.intent_level = intent_level
    if user_sentiment is not None:
        lead.user_sentiment = user_sentiment

    db.commit()
    db.refresh(lead)
    return _lead_to_schema(lead)


# ========================================
# Conversation Endpoints
# ========================================

def _conversation_to_schema(conv: Conversation) -> InternalConversationOut:
    return InternalConversationOut(
        id=conv.id,
        organization_id=conv.organization_id,
        lead_id=conv.lead_id,
        cta_id=conv.cta_id,
        cta_scheduled_at=conv.cta_scheduled_at,
        stage=conv.stage,
        intent_level=conv.intent_level,
        mode=conv.mode,
        user_sentiment=conv.user_sentiment,
        rolling_summary=conv.rolling_summary,
        last_message=conv.last_message,
        last_message_at=conv.last_message_at,
        last_user_message_at=conv.last_user_message_at,
        last_bot_message_at=conv.last_bot_message_at,
        followup_count_24h=conv.followup_count_24h or 0,
        total_nudges=conv.total_nudges or 0,
        needs_human_attention=conv.needs_human_attention or False,
        scheduled_followup_at=conv.scheduled_followup_at,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.get("/conversations/by-lead", response_model=Optional[InternalConversationOut])
def get_conversation_by_lead(
    organization_id: UUID,
    lead_id: UUID,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Get the most recent conversation for a lead."""
    conv = (
        db.query(Conversation)
        .filter(
            Conversation.organization_id == organization_id,
            Conversation.lead_id == lead_id,
        )
        .order_by(Conversation.created_at.desc())
        .first()
    )
    if not conv:
        return None
    return _conversation_to_schema(conv)


@router.post("/conversations", response_model=InternalConversationOut, status_code=201)
async def create_conversation(
    payload: InternalConversationCreate,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Create a new conversation."""
    conv = Conversation(
        organization_id=payload.organization_id,
        lead_id=payload.lead_id,
        stage=ConversationStage.GREETING,
        mode=ConversationMode.BOT,
        intent_level=IntentLevel.UNKNOWN,
        user_sentiment=UserSentiment.NEUTRAL,
        rolling_summary="",
        followup_count_24h=0,
        total_nudges=0,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    # Emit WebSocket event for real-time frontend updates (new conversation)
    try:
        from server.services.websocket_events import emit_conversation_updated
        from server.schemas import ConversationOut
        conv_out = ConversationOut.model_validate(conv, from_attributes=True)
        await emit_conversation_updated(conv.organization_id, conv_out)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to emit websocket for new conversation: {e}")

    return _conversation_to_schema(conv)


@router.get("/conversations/{conversation_id}", response_model=InternalConversationOut)
def get_conversation(
    conversation_id: UUID,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Get conversation by ID."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return _conversation_to_schema(conv)


@router.patch("/conversations/{conversation_id}", response_model=InternalConversationOut)
async def update_conversation(
    conversation_id: UUID,
    payload: InternalConversationUpdate,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Update conversation state."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(conv, field):
            setattr(conv, field, value)

    db.commit()
    db.refresh(conv)

    # Emit WebSocket event for real-time frontend updates
    try:
        conv_out = ConversationOut.model_validate(conv, from_attributes=True)
        await emit_conversation_updated(conv.organization_id, conv_out)
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to emit websocket for updated conversation: {e}")

    return _conversation_to_schema(conv)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=List[InternalMessageContext]
)
def get_conversation_messages(
    conversation_id: UUID,
    limit: int = Query(default=3, le=20),
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Get last N messages for a conversation formatted for pipeline context."""
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    # Reverse to get chronological order
    messages = list(reversed(messages))

    result = []
    for msg in messages:
        sender = "lead" if msg.message_from == MessageFrom.LEAD else (
            "bot" if msg.message_from == MessageFrom.BOT else "human"
        )
        result.append(InternalMessageContext(
            sender=sender,
            text=msg.content[:500],
            timestamp=msg.created_at.isoformat() if msg.created_at else "",
        ))
    return result


# ========================================
# Message Endpoints
# ========================================

def _message_to_schema(msg: Message) -> InternalMessageOut:
    return InternalMessageOut(
        id=msg.id,
        organization_id=msg.organization_id,
        conversation_id=msg.conversation_id,
        lead_id=msg.lead_id,
        message_from=msg.message_from,
        content=msg.content,
        status=msg.status,
        created_at=msg.created_at,
    )


@router.post("/messages/incoming", response_model=InternalMessageOut, status_code=201)
async def store_incoming_message(
    payload: InternalIncomingMessageCreate,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Store incoming lead message and update conversation timestamps."""
    conv = db.query(Conversation).filter(Conversation.id == payload.conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    now = datetime.now(timezone.utc)

    message = Message(
        organization_id=conv.organization_id,
        conversation_id=payload.conversation_id,
        lead_id=payload.lead_id or conv.lead_id,
        message_from=MessageFrom.LEAD,
        content=payload.content,
        status="received",
    )
    db.add(message)

    # Update conversation timestamps
    conv.last_message = payload.content[:500]
    conv.last_message_at = now
    conv.last_user_message_at = now

    db.commit()
    db.refresh(message)
    db.refresh(conv)

    # Emit WebSocket event for real-time frontend updates
    try:
        from server.services.websocket_events import emit_conversation_updated
        from server.schemas import ConversationOut, MessageOut
        conv_out = ConversationOut.model_validate(conv, from_attributes=True)
        msg_out = MessageOut.model_validate(message, from_attributes=True)
        await emit_conversation_updated(conv.organization_id, conv_out, msg_out)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to emit websocket for incoming message: {e}")

    return _message_to_schema(message)


@router.post("/messages/outgoing", response_model=InternalMessageOut, status_code=201)
async def store_outgoing_message(
    payload: InternalOutgoingMessageCreate,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Store outgoing bot/human message and update conversation timestamps."""
    conv = db.query(Conversation).filter(Conversation.id == payload.conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    now = datetime.now(timezone.utc)

    message = Message(
        organization_id=conv.organization_id,
        conversation_id=payload.conversation_id,
        lead_id=payload.lead_id or conv.lead_id,
        message_from=payload.message_from,
        content=payload.content,
        status="sent",
    )
    db.add(message)

    # Update conversation timestamps
    conv.last_message = payload.content[:500]
    conv.last_message_at = now
    conv.last_bot_message_at = now

    db.commit()
    db.refresh(message)
    db.refresh(conv)

    # Emit WebSocket event for real-time frontend updates
    try:
        from server.services.websocket_events import emit_conversation_updated
        from server.schemas import ConversationOut, MessageOut
        conv_out = ConversationOut.model_validate(conv, from_attributes=True)
        msg_out = MessageOut.model_validate(message, from_attributes=True)
        await emit_conversation_updated(conv.organization_id, conv_out, msg_out)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to emit websocket for outgoing message: {e}")

    return _message_to_schema(message)


# ========================================
# Scheduled Action Endpoints
# ========================================

def _action_to_schema(action: ScheduledAction) -> InternalScheduledActionOut:
    return InternalScheduledActionOut(
        id=action.id,
        conversation_id=action.conversation_id,
        organization_id=action.organization_id,
        scheduled_at=action.scheduled_at,
        status=action.status.value,
        action_type=action.action_type,
        action_context=action.action_context,
        executed_at=action.executed_at,
        created_at=action.created_at,
    )


@router.get("/scheduled-actions/due", response_model=List[InternalScheduledActionOut])
def get_due_actions(
    limit: int = Query(default=50, le=100),
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Get pending scheduled actions that are due for execution."""
    now = datetime.now(timezone.utc)
    actions = (
        db.query(ScheduledAction)
        .filter(
            ScheduledAction.status == ScheduledActionStatus.PENDING,
            ScheduledAction.scheduled_at <= now
        )
        .limit(limit)
        .all()
    )
    return [_action_to_schema(a) for a in actions]


@router.post("/scheduled-actions", response_model=InternalScheduledActionOut, status_code=201)
def create_scheduled_action(
    payload: InternalScheduledActionCreate,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Create a new scheduled action."""
    action = ScheduledAction(
        conversation_id=payload.conversation_id,
        organization_id=payload.organization_id,
        scheduled_at=payload.scheduled_at,
        status=ScheduledActionStatus.PENDING,
        action_type=payload.action_type,
        action_context=payload.action_context,
    )
    db.add(action)

    # Update conversation scheduled_followup_at
    conv = db.query(Conversation).filter(Conversation.id == payload.conversation_id).first()
    if conv:
        conv.scheduled_followup_at = payload.scheduled_at
        conv.total_nudges = (conv.total_nudges or 0) + 1
        conv.followup_count_24h = (conv.followup_count_24h or 0) + 1

    db.commit()
    db.refresh(action)
    return _action_to_schema(action)


@router.get("/scheduled-actions/{action_id}", response_model=InternalScheduledActionOut)
def get_scheduled_action(
    action_id: UUID,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Get scheduled action by ID."""
    action = db.query(ScheduledAction).filter(ScheduledAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Scheduled action not found")
    return _action_to_schema(action)


@router.patch("/scheduled-actions/{action_id}", response_model=InternalScheduledActionOut)
def update_scheduled_action(
    action_id: UUID,
    payload: InternalScheduledActionUpdate,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Update scheduled action status."""
    action = db.query(ScheduledAction).filter(ScheduledAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Scheduled action not found")

    # Convert string status to enum
    try:
        action.status = ScheduledActionStatus(payload.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {payload.status}")

    if payload.executed_at:
        action.executed_at = payload.executed_at

    db.commit()
    db.refresh(action)
    return _action_to_schema(action)


@router.post("/scheduled-actions/cancel-pending")
def cancel_pending_actions(
    conversation_id: UUID,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Cancel all pending scheduled actions for a conversation."""
    result = (
        db.query(ScheduledAction)
        .filter(
            ScheduledAction.conversation_id == conversation_id,
            ScheduledAction.status == ScheduledActionStatus.PENDING
        )
        .update({"status": ScheduledActionStatus.CANCELLED})
    )
    db.commit()
    return {"cancelled": result}


# ========================================
# Followup Processing Endpoints
# ========================================

@router.get(
    "/scheduled-actions/{action_id}/context",
    response_model=InternalFollowupContext
)
def get_followup_context(
    action_id: UUID,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Get full context needed to process a scheduled followup."""
    action = db.query(ScheduledAction).filter(ScheduledAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Scheduled action not found")

    conv = db.query(Conversation).filter(Conversation.id == action.conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    lead = db.query(Lead).filter(Lead.id == conv.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    org = db.query(Organization).filter(Organization.id == conv.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    integration = (
        db.query(WhatsAppIntegration)
        .filter(
            WhatsAppIntegration.organization_id == org.id,
            WhatsAppIntegration.is_connected == True
        )
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="WhatsApp integration not found")

    return InternalFollowupContext(
        action=_action_to_schema(action),
        conversation=_conversation_to_schema(conv),
        lead=_lead_to_schema(lead),
        organization_id=org.id,
        organization_name=org.name,
        access_token=integration.access_token,
        phone_number_id=integration.phone_number_id,
        version=integration.version,
        business_name=org.business_name,
        business_description=org.business_description,
        flow_prompt=org.flow_prompt,
    )


# ========================================
# Pipeline Event Endpoints
# ========================================

@router.post("/conversation-events", response_model=InternalPipelineEventOut, status_code=201)
def create_pipeline_event(
    payload: InternalPipelineEventCreate,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Log a pipeline execution event."""
    event = ConversationEvent(
        conversation_id=payload.conversation_id,
        event_type=payload.event_type,
        pipeline_step=payload.pipeline_step,
        input_summary=payload.input_summary,
        output_summary=payload.output_summary,
        latency_ms=payload.latency_ms,
        tokens_used=payload.tokens_used,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return InternalPipelineEventOut(
        id=event.id,
        conversation_id=event.conversation_id,
        event_type=event.event_type,
        pipeline_step=event.pipeline_step,
        input_summary=event.input_summary,
        output_summary=event.output_summary,
        latency_ms=event.latency_ms,
        tokens_used=event.tokens_used,
        created_at=event.created_at,
    )


# ========================================
# Utility Endpoints
# ========================================

@router.post("/conversations/reset-followup-counts")
def reset_followup_counts(
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    """Reset followup_count_24h for all conversations. Called daily."""
    result = (
        db.query(Conversation)
        .filter(Conversation.followup_count_24h > 0)
        .update({"followup_count_24h": 0})
    )
    db.commit()
    return {"reset": result}


# ========================================
# WebSocket Event Endpoints
# ========================================

@router.post("/emit-cta-initiated")
async def emit_cta_initiated_event(
    conversation_id: UUID,
    organization_id: UUID,
    cta_type: str,
    cta_name: Optional[str] = None,
    scheduled_time: Optional[str] = None,
    _: None = Depends(require_internal_secret),
):
    """Emit CTA initiated WebSocket event to frontend."""
    from server.services.websocket_events import emit_action_cta_initiated
    
    await emit_action_cta_initiated(
        org_id=organization_id,
        conversation_id=conversation_id,
        cta_type=cta_type,
        cta_name=cta_name,
        scheduled_time=scheduled_time,
    )
    return {"status": "emitted"}


@router.post("/emit-human-attention")
async def emit_human_attention_event(
    conversation_id: UUID,
    organization_id: UUID,
    _: None = Depends(require_internal_secret),
):
    """Emit human attention required WebSocket event to frontend."""
    from server.services.websocket_events import emit_action_human_attention_required
    
    await emit_action_human_attention_required(
        org_id=organization_id,
        conversation_ids=[conversation_id],
    )
    return {"status": "emitted"}
