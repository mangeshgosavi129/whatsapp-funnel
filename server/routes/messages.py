from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from server.dependencies import get_db
from server.dependencies import get_auth_context
from server.schemas import MessageOut, MessageCreate, AuthContext
from server.models import Message, Conversation
from server.enums import MessageFrom

router = APIRouter()

@router.post("/send", response_model=MessageOut)
def send_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
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
        message_from=MessageFrom.HUMAN, # When sent via API, it's typically a human agent
        assigned_user_id=auth.user_id,
        status="sent"
    )
    db.add(db_message)
    
    # Update conversation's last message info
    conv.last_message = payload.content
    conv.last_message_at = db_message.created_at # Note: created_at might be None until commit, but we can set it
    
    db.commit()
    db.refresh(db_message)
    return db_message
