from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from server.schemas import OrganizationOut, OrganizationUpdate, AuthContext
from server.models import Organization
from server.dependencies import get_db, get_auth_context

router = APIRouter()

# =========================================================
# ORGANISATION ENDPOINTS
# =========================================================
@router.get("", response_model=OrganizationOut)
def get_organisation(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    org = db.query(Organization).filter(Organization.id == auth.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
        
    return org


@router.patch("", response_model=OrganizationOut)
def update_organisation(
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    """Update organization settings including business configuration."""
    org = db.query(Organization).filter(Organization.id == auth.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(org, field):
            setattr(org, field, value)
    
    db.commit()
    db.refresh(org)
    return org
