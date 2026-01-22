
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from server.config import config
from server.dependencies import get_db
from server.models import WhatsAppIntegration

router = APIRouter()


def require_internal_secret(
    x_internal_secret: str | None = Header(default=None),
) -> None:
    if not x_internal_secret or x_internal_secret != config.SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )


def _integration_to_payload(integration: WhatsAppIntegration) -> dict:
    return {
        "id": str(integration.id),
        "organization_id": str(integration.organization_id),
        "access_token": integration.access_token,
        "version": integration.version,
        "verify_token": integration.verify_token,
        "app_secret": integration.app_secret,
        "phone_number_id": integration.phone_number_id,
        "is_connected": integration.is_connected,
    }


@router.get("/whatsapp/by-verify-token")
def get_whatsapp_integration_by_verify_token(
    verify_token: str,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    integration = (
        db.query(WhatsAppIntegration)
        .filter(WhatsAppIntegration.verify_token == verify_token)
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="WhatsApp integration not found")
    if not integration.is_connected:
        raise HTTPException(status_code=409, detail="WhatsApp integration not connected")
    return _integration_to_payload(integration)


@router.get("/whatsapp/by-phone-number-id/{phone_number_id}")
def get_whatsapp_integration_by_phone_number_id(
    phone_number_id: str,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    integration = (
        db.query(WhatsAppIntegration)
        .filter(WhatsAppIntegration.phone_number_id == phone_number_id)
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="WhatsApp integration not found")
    if not integration.is_connected:
        raise HTTPException(status_code=409, detail="WhatsApp integration not connected")
    return _integration_to_payload(integration)


@router.get("/whatsapp/by-organization-id/{organization_id}")
def get_whatsapp_integration_by_organization_id(
    organization_id: str,
    _: None = Depends(require_internal_secret),
    db: Session = Depends(get_db),
):
    integration = (
        db.query(WhatsAppIntegration)
        .filter(WhatsAppIntegration.organization_id == organization_id)
        .first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="WhatsApp integration not found")
    if not integration.is_connected:
        raise HTTPException(status_code=409, detail="WhatsApp integration not connected")
    return _integration_to_payload(integration)
