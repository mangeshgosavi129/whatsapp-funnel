from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from server.schemas import OrganizationOut, AuthContext
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
