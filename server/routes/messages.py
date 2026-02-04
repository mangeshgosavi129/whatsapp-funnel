import json
import logging
from datetime import datetime, timezone
from typing import Mapping, Tuple, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func

from server.dependencies import get_db, get_auth_context, require_internal_secret
from server.schemas import MessageOut, AuthContext, ConversationOut
from server.models import Message, Conversation, WhatsAppIntegration, Lead
from server.enums import MessageFrom
from server.services.websocket_events import emit_conversation_updated
from uuid import UUID

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------
# WhatsApp send helpers (merged from send.py)
# ---------------------------
def _wa_api_url(version: str, phone_number_id: str) -> str:
    return f"https://graph.facebook.com/{version}/{phone_number_id}/messages"


def _wa_text_payload(recipient: str, text: str) -> str:
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )


def _send_whatsapp_text(
    *,
    to: str,
    message: str,
    access_token: str,
    phone_number_id: str,
    version: str = "v18.0",
) -> Tuple[Mapping, int]:
    """
    Sends WhatsApp text message using runtime credentials passed in payload.
    """
    # Debug logging
    logger.info(f"[WA Send] to={to}, message_len={len(message) if message else 0}, "
                f"access_token={'set' if access_token else 'MISSING'}, "
                f"phone_number_id={phone_number_id or 'MISSING'}")
    
    # Validation
    if not (access_token and phone_number_id and to and message):
        missing = []
        if not access_token: missing.append("access_token")
        if not phone_number_id: missing.append("phone_number_id")
        if not to: missing.append("to (recipient)")
        if not message: missing.append("message")
        logger.error(f"Missing WhatsApp configuration or recipient. Missing: {missing}")
        return {"status": "error", "message": f"Missing configuration: {', '.join(missing)}"}, 500

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        resp = requests.post(
            _wa_api_url(version, phone_number_id),
            data=_wa_text_payload(to, message),
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json(), resp.status_code

    except requests.Timeout:
        logger.error("WhatsApp request timed out")
        return {"status": "error", "message": "Request timed out"}, 408

    except requests.RequestException as e:
        logger.error(f"WhatsApp send error: {e}")

        # Return WA response if possible
        try:
            return resp.json(), resp.status_code  # type: ignore
        except Exception:
            return {"status": "error", "message": "Failed to send message"}, 500


# ---------------------------
# NOTE: We need a schema that includes runtime WA credentials.
# If you already have MessageCreate, extend it to include these fields.
# ---------------------------
# Expected payload fields:
# - conversation_id: int
# - content: str
# - access_token: str
# - phone_number_id: str
# - version: Optional[str]
#
# Recipient ("to") is derived from Conversation (recommended).
# If you want "to" also in payload, you can add it and override.
# ---------------------------


@router.post("/send_bot", response_model=MessageOut)
async def send_message_bot(
    payload: dict,
    db: Session = Depends(get_db),
    _: None = Depends(require_internal_secret),
):
    org_id = payload.get("organization_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="organization_id is required")
    
    return await _send_msg(payload, db, UUID(str(org_id)), MessageFrom.BOT, payload.get("assigned_user_id"))


@router.post("/send_human", response_model=MessageOut)
async def send_message_human(
    payload: dict,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return await _send_msg(payload, db, auth.organization_id, MessageFrom.HUMAN, auth.user_id)


async def _send_msg(
    payload: dict, 
    db: Session, 
    organization_id: UUID, 
    sender_type: MessageFrom, 
    user_id: Optional[UUID] = None
):
    """
    Store -> Send on WhatsApp -> Websocket emission
    """

    # 0) Validate required payload fields (runtime creds)
    conversation_id = payload.get("conversation_id")
    content = payload.get("content")

    access_token = payload.get("access_token")
    phone_number_id = payload.get("phone_number_id")
    version = payload.get("version") or "v18.0"

    if not conversation_id or not content:
        raise HTTPException(status_code=400, detail="conversation_id and content are required")

    # If creds missing, fetch from WhatsAppIntegration table
    if not access_token or not phone_number_id:
        integration = (
            db.query(WhatsAppIntegration)
            .filter(WhatsAppIntegration.organization_id == organization_id)
            .first()
        )
        if not integration or not integration.is_connected:
            raise HTTPException(
                status_code=400, 
                detail="access_token and phone_number_id are required or WhatsApp integration must be connected"
            )
        
        access_token = access_token or integration.access_token
        phone_number_id = phone_number_id or integration.phone_number_id
        version = version or integration.version

    # 1) Verify conversation belongs to org (with eager loading of Lead)
    conv = (
        db.query(Conversation)
        .options(joinedload(Conversation.lead))
        .filter(
            Conversation.id == conversation_id,
            Conversation.organization_id == organization_id,
        )
        .first()
    )

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Recipient should come from Lead's phone number (via relationship)
    recipient_phone = conv.lead.phone if conv.lead else None
    
    # Debug logging
    logger.info(f"[send_msg] conv.lead_id={conv.lead_id}, conv.lead={conv.lead}, recipient_phone={recipient_phone}")

    # Optional override: allow payload.to
    recipient_phone = payload.get("to") or recipient_phone

    if not recipient_phone:
        raise HTTPException(status_code=400, detail="Conversation has no associated lead phone number")

    # 2) Store message in DB
    db_message = Message(
        organization_id=organization_id,
        conversation_id=conversation_id,
        lead_id=conv.lead_id,
        content=content,
        message_from=sender_type,
        assigned_user_id=user_id if sender_type == MessageFrom.HUMAN else None,
        status="sending",
    )
    db.add(db_message)

    # Update conversation last message fields
    now = datetime.now(timezone.utc)
    conv.last_message = content[:500]
    conv.last_message_at = now
    if sender_type == MessageFrom.BOT:
        conv.last_bot_message_at = now
    elif sender_type == MessageFrom.HUMAN:
        # For simplicity, we can also treat HUMAN replies as bot replies for follow-up purposes
        conv.last_bot_message_at = now

    db.commit()
    db.refresh(db_message)

    # 3) Send on WhatsApp
    wa_resp, wa_status = _send_whatsapp_text(
        to=recipient_phone,
        message=content,
        access_token=access_token,
        phone_number_id=phone_number_id,
        version=version,
    )

    if 200 <= wa_status < 300:
        db_message.status = "sent"

        # Optional: store WA message id if your model supports it
        try:
            wa_msg_id = wa_resp.get("messages", [{}])[0].get("id")
            if wa_msg_id and hasattr(db_message, "external_message_id"):
                db_message.external_message_id = wa_msg_id
        except Exception:
            pass
    else:
        db_message.status = "failed"
        if hasattr(db_message, "error"):
            db_message.error = json.dumps(wa_resp)

    db.commit()
    db.refresh(db_message)

    # 4) Emit websocket event (before potential raise)
    try:
        conv_out = ConversationOut.model_validate(conv, from_attributes=True)
        msg_out = MessageOut.model_validate(db_message, from_attributes=True)
        await emit_conversation_updated(organization_id, conv_out, msg_out)
    except Exception as e:
        logger.error(f"Failed to emit websocket event: {e}")

    if not (200 <= wa_status < 300):
        raise HTTPException(
            status_code=502,
            detail={
                "message": "WhatsApp send failed",
                "wa_status": wa_status,
                "wa_response": wa_resp,
            },
        )

    return db_message