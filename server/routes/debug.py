from fastapi import APIRouter
from sqlalchemy.orm import Session
from server.database import SessionLocal
from server.models import Lead, Conversation, Message
from server.enums import (
    ConversationStage,
    ConversationMode,
    IntentLevel,
    UserSentiment,
    MessageFrom,
)
from server.schemas import MessageOut, ConversationOut
from server.services.websocket_events import emit_conversation_updated

router = APIRouter(prefix="/debug", tags=["debug"])

@router.post("/message")
async def debug_send_message():
    print("🧪 DEBUG MESSAGE ENDPOINT HIT")

    db: Session = SessionLocal()

    # Get the first lead and use ITS organization (not a random org)
    lead = db.query(Lead).first()

    if not lead:
        return {"error": "No leads found in the database"}

    # Use the lead's organization_id - this is the key fix!
    org_id = lead.organization_id
    print(f"🔍 Using lead's organization_id: {org_id}")

    conversation = (
        db.query(Conversation)
        .filter(Conversation.lead_id == lead.id)
        .first()
    )

    if not conversation:
        conversation = Conversation(
            organization_id=org_id,
            lead_id=lead.id,
            stage=ConversationStage.GREETING,
            intent_level=IntentLevel.MEDIUM,
            mode=ConversationMode.BOT,
            user_sentiment=UserSentiment.NEUTRAL,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    message = Message(
        organization_id=org_id,
        conversation_id=conversation.id,
        lead_id=lead.id,
        message_from=MessageFrom.LEAD,
        content="Hello from DEBUG endpoint 👋",
        status="sent",
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    print("🚀 EMITTING WS MESSAGE")

    message_out = MessageOut(
        id=message.id,
        organization_id=message.organization_id,
        conversation_id=message.conversation_id,
        message_from=message.message_from,
        assigned_user_id=None,
        content=message.content,
        status=message.status,
        created_at=message.created_at,
    )
    print(f"emitting right now with org_id={org_id} & {message_out}")

    # Build conversation payload and include the exact message
    conv_out = ConversationOut.model_validate(conversation, from_attributes=True)
    await emit_conversation_updated(org_id, conv_out, message_out)

    return {"ok": True, "message_id": str(message.id), "org_id": str(org_id)}