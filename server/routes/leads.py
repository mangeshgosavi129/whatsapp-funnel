from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..dependencies import get_auth_context
from ..models import Lead
from ..schemas import LeadOut, LeadUpdate, AuthContext
from uuid import UUID

router = APIRouter()

@router.get("/", response_model=List[LeadOut])
def get_leads(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    return db.query(Lead).filter(Lead.organization_id == auth.organization_id).all()

@router.put("/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: UUID,
    lead: LeadUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    db_lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == auth.organization_id
    ).first()
    
    if not db_lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    update_data = lead.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_lead, key, value)
    
    db.commit()
    db.refresh(db_lead)
    return db_lead

@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    db_lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == auth.organization_id
    ).first()
    
    if not db_lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    db.delete(db_lead)
    db.commit()
    return None
