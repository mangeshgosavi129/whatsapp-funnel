from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from server.dependencies import get_db
from server.dependencies import get_auth_context
from server.schemas import CTAOut, CTACreate, CTAUpdate, AuthContext
from server.models import CTA
from uuid import UUID

router = APIRouter()

@router.get("", response_model=List[CTAOut])
def get_ctas(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    return db.query(CTA).filter(CTA.organization_id == auth.organization_id).all()

@router.post("", response_model=CTAOut)
def create_cta(
    cta: CTACreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    db_cta = CTA(
        **cta.model_dump(),
        organization_id=auth.organization_id
    )
    db.add(db_cta)
    db.commit()
    db.refresh(db_cta)
    return db_cta

@router.patch("/{cta_id}", response_model=CTAOut)
def update_cta(
    cta_id: UUID,
    cta: CTAUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    db_cta = db.query(CTA).filter(
        CTA.id == cta_id, 
        CTA.organization_id == auth.organization_id
    ).first()
    
    if not db_cta:
        raise HTTPException(status_code=404, detail="CTA not found")
    
    update_data = cta.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_cta, key, value)
    
    db.commit()
    db.refresh(db_cta)
    return db_cta

@router.delete("/{cta_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cta(
    cta_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    db_cta = db.query(CTA).filter(
        CTA.id == cta_id, 
        CTA.organization_id == auth.organization_id
    ).first()
    
    if not db_cta:
        raise HTTPException(status_code=404, detail="CTA not found")
    
    db.delete(db_cta)
    db.commit()
    return None
