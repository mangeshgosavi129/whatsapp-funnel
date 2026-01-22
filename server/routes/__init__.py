from fastapi import APIRouter
from . import (
    auth, 
    leads, 
    conversations, 
    templates, 
    analytics, 
    dashboard, 
    ctas, 
    settings, 
    messages,
    websockets,
    users,
    organisations,
    internals
)

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
router.include_router(leads.router, prefix="/leads", tags=["Leads"])
router.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])
router.include_router(messages.router, prefix="/messages", tags=["Messages"])
router.include_router(ctas.router, prefix="/ctas", tags=["CTAs"])
router.include_router(templates.router, prefix="/templates", tags=["Templates"])
router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
router.include_router(settings.router, prefix="/settings", tags=["Settings"])
router.include_router(users.router, prefix="/users", tags=["Users"])
router.include_router(organisations.router, prefix="/organisations", tags=["Organisations"])
router.include_router(websockets.router, tags=["WebSockets"])
router.include_router(internals.router, prefix="/internals", tags=["Internals"])
