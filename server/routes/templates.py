from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from server.dependencies import get_db
from server.dependencies import get_auth_context
from server.models import Template
from server.schemas import TemplateCreate, TemplateUpdate, TemplateOut, TemplateStatusOut, AuthContext
from server.enums import TemplateStatus
from uuid import UUID
from datetime import datetime

router = APIRouter()

@router.get("/", response_model=List[TemplateOut])
def get_templates(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    return db.query(Template).filter(Template.organization_id == auth.organization_id).all()

@router.post("/", response_model=TemplateOut)
def create_template(
    template: TemplateCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    db_template = Template(
        **template.model_dump(),
        organization_id=auth.organization_id,
        status=TemplateStatus.PENDING
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

@router.put("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: UUID,
    template: TemplateUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    db_template = db.query(Template).filter(
        Template.id == template_id,
        Template.organization_id == auth.organization_id
    ).first()
    
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    update_data = template.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_template, key, value)
    
    db.commit()
    db.refresh(db_template)
    return db_template

@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    db_template = db.query(Template).filter(
        Template.id == template_id,
        Template.organization_id == auth.organization_id
    ).first()
    
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db.delete(db_template)
    db.commit()
    return None

@router.post("/{template_id}/submit", response_model=TemplateOut)
def submit_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    db_template = db.query(Template).filter(
        Template.id == template_id,
        Template.organization_id == auth.organization_id
    ).first()
    
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db_template.status = TemplateStatus.APPROVED # Mock automatic approval for now
    db_template.approved_at = datetime.now()
    
    db.commit()
    db.refresh(db_template)
    return db_template

@router.get("/{template_id}/status", response_model=TemplateStatusOut)
def get_template_status(
    template_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    db_template = db.query(Template).filter(
        Template.id == template_id,
        Template.organization_id == auth.organization_id
    ).first()
    
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return TemplateStatusOut(
        status=db_template.status,
        approved_at=db_template.approved_at,
        rejection_reason=db_template.rejection_reason
    )
