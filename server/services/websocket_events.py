from typing import List, Dict, Any, Callable, Awaitable
from uuid import UUID
import time
from server.services.websocket_manager import manager
from server.schemas import (
    WebSocketEnvelope,
    WSConversationUpdated,
    WSTakeoverStarted,
    WSTakeoverEnded,
    WSActionConversationsFlagged,
    WSActionHumanAttentionRequired,
    MessageOut,
    ConversationOut,
)
from server.enums import WSEvents, ConversationMode
from server.database import SessionLocal
from server.models import Conversation, User

# In-memory last seen for active users (for heartbeat)
last_seen: Dict[UUID, float] = {}

async def handle_heartbeat(user_id: UUID, payload: Dict[str, Any]):
    last_seen[user_id] = time.time()

async def handle_takeover_started(user_id: UUID, payload: Dict[str, Any]):
    conversation_id = payload.get("conversation_id")
    if not conversation_id:
        await emit_error(user_id, "Missing conversation_id in takeover_started payload")
        return

    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await emit_error(user_id, "User not found")
            return

        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.organization_id == user.organization_id
        ).first()

        if not conversation:
            await emit_error(user_id, "Conversation not found")
            return

        # Update mode to HUMAN
        conversation.mode = ConversationMode.HUMAN
        db.commit()
        db.refresh(conversation)

        # Broadcast update
        conv_out = ConversationOut.model_validate(conversation, from_attributes=True)
        await emit_conversation_updated(user.organization_id, conv_out)
        await emit_ack(user_id, "takeover_started")


async def handle_takeover_ended(user_id: UUID, payload: Dict[str, Any]):
    conversation_id = payload.get("conversation_id")
    if not conversation_id:
        await emit_error(user_id, "Missing conversation_id in takeover_ended payload")
        return

    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await emit_error(user_id, "User not found")
            return

        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.organization_id == user.organization_id
        ).first()

        if not conversation:
            await emit_error(user_id, "Conversation not found")
            return

        # Update mode back to BOT
        conversation.mode = ConversationMode.BOT
        db.commit()
        db.refresh(conversation)

        # Broadcast update
        conv_out = ConversationOut.model_validate(conversation, from_attributes=True)
        await emit_conversation_updated(user.organization_id, conv_out)
        await emit_ack(user_id, "takeover_ended")

# Event Handler User Mapping
HANDLER_MAP: Dict[str, Callable[[UUID, Dict[str, Any]], Awaitable[None]]] = {
    WSEvents.CLIENT_HEARTBEAT: handle_heartbeat,
    WSEvents.TAKEOVER_STARTED: handle_takeover_started,
    WSEvents.TAKEOVER_ENDED: handle_takeover_ended,
}

async def handle_event(user_id: UUID, data: Dict[str, Any]):
    event_type = data.get("event")
    payload = data.get("payload", {})
    
    try:
        if event_type in HANDLER_MAP:
            await HANDLER_MAP[event_type](user_id, payload)
        else:
            await emit_error(user_id, f"Unknown event: {event_type}")
    except Exception as e:
        await emit_error(user_id, f"Error handling {event_type}: {str(e)}")

# Outbound Emitters
async def emit_ack(user_id: UUID, event_acknowledged: str):
    envelope = WebSocketEnvelope(event=WSEvents.ACK, payload={"event": event_acknowledged})
    await manager.send_to_user(user_id, envelope.model_dump(mode='json'))

async def emit_error(user_id: UUID, error_message: str):
    envelope = WebSocketEnvelope(event=WSEvents.ERROR, payload={"message": error_message})
    await manager.send_to_user(user_id, envelope.model_dump(mode='json'))

async def emit_conversation_updated(org_id: UUID, conversation: ConversationOut, message: MessageOut | None = None):
    payload = WSConversationUpdated(conversation=conversation, message=message)
    envelope = WebSocketEnvelope(event=WSEvents.CONVERSATION_UPDATED, payload=payload.model_dump(mode='json'))
    await manager.broadcast_to_org(org_id, envelope.model_dump(mode='json'))

async def emit_action_conversations_flagged(org_id: UUID, cta_id: UUID, conversation_ids: List[UUID]):
    payload = WSActionConversationsFlagged(cta_id=cta_id, conversation_ids=conversation_ids)
    envelope = WebSocketEnvelope(event=WSEvents.ACTION_CONVERSATIONS_FLAGGED, payload=payload.model_dump(mode='json'))
    await manager.broadcast_to_org(org_id, envelope.model_dump(mode='json'))

async def emit_action_human_attention_required(org_id: UUID, conversation_ids: List[UUID]):
    payload = WSActionHumanAttentionRequired(conversation_ids=conversation_ids)
    envelope = WebSocketEnvelope(event=WSEvents.ACTION_HUMAN_ATTENTION_REQUIRED, payload=payload.model_dump(mode='json'))
    await manager.broadcast_to_org(org_id, envelope.model_dump(mode='json'))


async def emit_action_cta_initiated(
    org_id: UUID,
    conversation_id: UUID,
    cta_type: str,
    cta_name: str | None = None,
    scheduled_time: str | None = None
):
    """Emit CTA initiated event to frontend Actions page."""
    payload = {
        "conversation_id": str(conversation_id),
        "cta_type": cta_type,
        "cta_name": cta_name,
        "scheduled_time": scheduled_time,
    }
    envelope = WebSocketEnvelope(event=WSEvents.ACTION_CTA_INITIATED, payload=payload)
    await manager.broadcast_to_org(org_id, envelope.model_dump(mode='json'))