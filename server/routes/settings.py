from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from server.dependencies import get_db
from server.dependencies import get_auth_context
from server.models import WhatsAppIntegration
from server.schemas import (
    WhatsAppIntegrationOut, 
    WhatsAppIntegrationCreate, 
    WhatsAppIntegrationUpdate, 
    WhatsAppStatusOut,
    AuthContext,
    SuccessResponse
)
from uuid import UUID

router = APIRouter()

@router.post("/whatsapp/connect", response_model=WhatsAppIntegrationOut)
def connect_whatsapp(
    payload: WhatsAppIntegrationCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    # Check if already exists
    integration = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.organization_id == auth.organization_id
    ).first()
    
    if integration:
        # Update existing
        update_data = payload.model_dump()
        for key, value in update_data.items():
            setattr(integration, key, value)
        integration.is_connected = True
    else:
        # Create new - explicitly exclude updated_at
        payload_data = payload.model_dump(exclude_unset=True)
        integration = WhatsAppIntegration(
            **payload_data,
            organization_id=auth.organization_id,
            is_connected=True
        )
        db.add(integration)
    
    db.commit()
    db.refresh(integration)
    return integration

@router.get("/whatsapp/status", response_model=WhatsAppStatusOut)
def get_whatsapp_status(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    integration = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.organization_id == auth.organization_id
    ).first()
    
    if not integration:
        # Return default "not connected" status
        return WhatsAppStatusOut(is_connected=False)
        
    # Return existing integration status
    return WhatsAppStatusOut(is_connected=integration.is_connected)

@router.get("/whatsapp/config", response_model=WhatsAppIntegrationOut)
def get_whatsapp_config(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    integration = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.organization_id == auth.organization_id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="WhatsApp integration not found")
        
    return integration

@router.patch("/whatsapp/update", response_model=WhatsAppIntegrationOut)
def update_whatsapp_config(
    payload: WhatsAppIntegrationUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    integration = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.organization_id == auth.organization_id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="WhatsApp integration not found")
    
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(integration, key, value)
        
    db.commit()
    db.refresh(integration)
    return integration

@router.delete("/whatsapp/disconnect", response_model=SuccessResponse)
def disconnect_whatsapp(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    integration = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.organization_id == auth.organization_id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="WhatsApp integration not found")
    
    db.delete(integration)
    db.commit()
    return SuccessResponse()
