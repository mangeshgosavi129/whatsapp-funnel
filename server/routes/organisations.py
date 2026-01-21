from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from server.schemas import OrganizationOut, AuthContext
from server.models import Organization
from server.dependencies import get_db, get_auth_context

router = APIRouter()

# =========================================================
# ORGANISATION ENDPOINTS
# =========================================================
@router.get("/{org_id}", response_model=OrganizationOut)
def get_organisation(
    org_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    # Verify user belongs to this org
    if auth.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied: not a member of this organisation")
    
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    
    return org
