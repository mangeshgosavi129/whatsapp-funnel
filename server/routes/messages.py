from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from server.dependencies import get_db
from server.dependencies import get_auth_context
from server.schemas import MessageOut, MessageCreate, AuthContext
from server.models import Message, Conversation
from server.enums import MessageFrom

router = APIRouter()

@router.post("/send_bot", response_model=MessageOut)
def send_message_bot(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    return _send_msg(payload, db, auth, MessageFrom.BOT)

@router.post("/send_human", response_model=MessageOut)
def send_message_human(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    return _send_msg(payload, db, auth, MessageFrom.HUMAN)

def _send_msg(payload, db, auth, sender_type):
    # Verify conversation belongs to org
    conv = db.query(Conversation).filter(
        Conversation.id == payload.conversation_id,
        Conversation.organization_id == auth.organization_id
    ).first()
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db_message = Message(
        organization_id=auth.organization_id,
        conversation_id=payload.conversation_id,
        content=payload.content,
        message_from=sender_type,
        assigned_user_id=auth.user_id if sender_type == MessageFrom.HUMAN else None,
        status="sent"
    )
    db.add(db_message)
    
    # Update conversation's last message info
    conv.last_message = payload.content
    conv.last_message_at = func.now() # Better to use DB func for consistency
    
    db.commit()
    db.refresh(db_message)
    return db_message
