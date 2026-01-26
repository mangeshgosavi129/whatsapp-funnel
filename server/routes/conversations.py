from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from server.dependencies import get_db, get_auth_context
from server.schemas import ConversationOut, MessageOut, AuthContext
from server.models import Conversation, Message
from server.enums import ConversationMode
from uuid import UUID

router = APIRouter()

@router.get("", response_model=List[ConversationOut])
def get_conversations(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    return db.query(Conversation).filter(Conversation.organization_id == auth.organization_id).all()

@router.get("/{conversation_id}/messages", response_model=List[MessageOut])
def get_conversation_messages(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    # Verify conversation belongs to org
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == auth.organization_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    return db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).all()

@router.post("/{conversation_id}/takeover", response_model=ConversationOut)
def takeover_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    db_conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == auth.organization_id
    ).first()
    
    if not db_conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db_conv.mode = ConversationMode.HUMAN
    db.commit()
    db.refresh(db_conv)
    return db_conv

@router.post("/{conversation_id}/release", response_model=ConversationOut)
def release_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    db_conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == auth.organization_id
    ).first()
    
    if not db_conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db_conv.mode = ConversationMode.BOT
    db.commit()
    db.refresh(db_conv)
    return db_conv
