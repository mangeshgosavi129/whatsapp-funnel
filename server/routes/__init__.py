from fastapi import APIRouter
from . import (
    auth, 
    leads, 
    conversations, 
    templates, 
    analytics, 
    credits, 
    dashboard, 
    ctas, 
    settings, 
    messages,
    websockets
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
router.include_router(credits.router, prefix="/credits", tags=["Credits"])
router.include_router(websockets.router, tags=["WebSockets"])
