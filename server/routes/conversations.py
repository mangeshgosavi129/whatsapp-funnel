from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from server.dependencies import get_db, get_auth_context
from server.schemas import ConversationOut, MessageOut, AuthContext
from server.models import Conversation, Message
from server.enums import ConversationMode
from uuid import UUID
from datetime import datetime

router = APIRouter()

@router.get("", response_model=List[ConversationOut])
def get_conversations(
    mode: str = None,
    needs_human_attention: bool = None,
    actionable: bool = None,
    attended_only: bool = False,
    dismissed: bool = False,
    start_date: datetime = None,
    end_date: datetime = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    query = db.query(Conversation).filter(Conversation.organization_id == auth.organization_id)
    
    if mode:
        query = query.filter(Conversation.mode == mode)
        
    if needs_human_attention is not None:
        query = query.filter(Conversation.needs_human_attention == needs_human_attention)

    # Date filtering (e.g. for dismissed view)
    if start_date:
        query = query.filter(Conversation.updated_at >= start_date)
    if end_date:
        query = query.filter(Conversation.updated_at <= end_date)
        
    if dismissed:
        # Show only dismissed CTAs
        query = query.filter(
            Conversation.cta_id.isnot(None),
            Conversation.cta_dismissed == True
        )
    else:
        # Default behavior: hide dismissed CTAs unless specifically asked
        query = query.filter(Conversation.cta_dismissed == False)

        if actionable is True:
            from sqlalchemy import or_
            query = query.filter(or_(
                Conversation.needs_human_attention == True,
                Conversation.cta_id.isnot(None)
            ))
        
    if attended_only:
        query = query.filter(Conversation.human_attention_resolved_at.isnot(None))\
                     .order_by(Conversation.human_attention_resolved_at.desc())

    if not attended_only and needs_human_attention is None and actionable is None and mode is None:
         # Default ordering if no specific filters
         query = query.order_by(Conversation.updated_at.desc())
        
    return query.all()

@router.patch("/{conversation_id}", response_model=ConversationOut)
def update_conversation(
    conversation_id: UUID,
    payload: dict,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Generic patch for conversation fields.
    For now, explicitly allowed fields: 'needs_human_attention', 'user_sentiment', 'intent_level', 'stage'.
    """
    db_conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == auth.organization_id
    ).first()
    
    if not db_conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    allowed_fields = ['needs_human_attention', 'user_sentiment', 'intent_level', 'stage', 'cta_dismissed']
    
    for key, value in payload.items():
        if key in allowed_fields:
            if hasattr(db_conv, key):
                # If marking as attended (False), set the resolved timestamp
                if key == 'needs_human_attention' and value is False and db_conv.needs_human_attention is True:
                     from datetime import datetime
                     db_conv.human_attention_resolved_at = datetime.utcnow()
                
                # If dismissing CTA, set timestamp
                if key == 'cta_dismissed' and value is True and db_conv.cta_dismissed is False:
                    from datetime import datetime
                    db_conv.cta_dismissed_at = datetime.utcnow()
                     
                setattr(db_conv, key, value)
                
    db.commit()
    db.refresh(db_conv)
    return db_conv

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
    # Clear human attention flag since human is now handling it
    db_conv.needs_human_attention = False
    db_conv.human_attention_resolved_at = datetime.utcnow()
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


