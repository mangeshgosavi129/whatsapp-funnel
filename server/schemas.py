from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from uuid import UUID
from pydantic import BaseModel, Field
from server.enums import (
    ConversationStage,
    IntentLevel,
    CTAType,
    ConversationMode,
    UserSentiment,
    TemplateStatus,
    MessageFrom,
)
from pydantic import EmailStr


# ======================================================
# Auth Context
# ======================================================

class AuthContext(BaseModel):
    user_id: UUID
    organization_id: UUID
    email: str
    is_active: bool


# ======================================================
# Shared JWT Response
# ======================================================

class AuthTokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


# ======================================================
# Login
# ======================================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(AuthTokenOut):
    user_id: UUID
    organization_id: UUID


# ======================================================
# Signup – Create New Organization
# ======================================================

class SignupCreateOrgRequest(BaseModel):
    name: str                 # user's name
    email: EmailStr
    password: str

    organization_name: str


class SignupCreateOrgResponse(AuthTokenOut):
    user_id: UUID
    organization_id: UUID


# ======================================================
# Signup – Join Existing Organization
# ======================================================

class SignupJoinOrgRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

    organization_id: UUID


class SignupJoinOrgResponse(AuthTokenOut):
    user_id: UUID
    organization_id: UUID

# ======================================================
# Standard Responses
# ======================================================

class APIError(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: APIError


class SuccessResponse(BaseModel):
    success: bool = True


# ======================================================
# Dashboard
# ======================================================

class DashboardStatsOut(BaseModel):
    total_conversations: int
    total_messages: int
    active_leads: int
    peak_hours: Dict[str, int]         
    sentiment_breakdown: Dict[str, int]


# ======================================================
# User / Org
# ======================================================

class OrganizationOut(BaseModel):
    id: UUID
    name: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]


class UserOut(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    email: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


# ======================================================
# Conversations
# ======================================================

class ConversationOut(BaseModel):
    id: UUID
    organization_id: UUID
    lead_id: Optional[UUID]
    cta_id: Optional[UUID]
    cta_scheduled_at: Optional[datetime]
    stage: ConversationStage
    intent_level: Optional[IntentLevel]
    mode: ConversationMode
    user_sentiment: Optional[UserSentiment]

    rolling_summary: Optional[str]
    last_message: Optional[str]
    last_message_at: Optional[datetime]

    created_at: datetime
    updated_at: Optional[datetime]


class ConversationTakeoverOut(BaseModel):
    conversation_id: UUID
    assigned_user_id: UUID


# ======================================================
# Messages
# ======================================================

class MessageCreate(BaseModel):
    conversation_id: UUID
    content: str


class MessageOut(BaseModel):
    id: UUID
    organization_id: UUID
    conversation_id: UUID

    message_from: MessageFrom
    assigned_user_id: Optional[UUID]

    content: str
    status: Literal["sent", "delivered", "read", "failed"]
    created_at: datetime


# ======================================================
# CTAs
# ======================================================

class CTACreate(BaseModel):
    name: str
    cta_type: CTAType

class CTAUpdate(BaseModel):
    name: Optional[str]
    is_active: Optional[bool]


class CTAOut(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    cta_type: CTAType
    is_active: bool
    scheduled_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]


# ======================================================
# Templates
# ======================================================

class TemplateCreate(BaseModel):
    name: str
    content: str


class TemplateUpdate(BaseModel):
    name: Optional[str]
    content: Optional[str]


class TemplateStatusOut(BaseModel):
    status: TemplateStatus
    approved_at: Optional[datetime]
    rejection_reason: Optional[str]


class TemplateOut(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    content: str
    status: TemplateStatus
    approved_at: Optional[datetime]
    rejection_reason: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


# ======================================================
# Followups
# ======================================================

class FollowupCreate(BaseModel):
    template_id: UUID
    delay_hours: int = Field(..., gt=0)
    sequence_order: int = Field(..., gt=0)


class FollowupOut(BaseModel):
    id: UUID
    organization_id: UUID
    template_id: UUID
    delay_hours: int
    sequence_order: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]


# --------------------
# Leads
# --------------------

class LeadCreate(BaseModel):
    name: Optional[str] = None
    phone: str
    email: Optional[str] = None
    company: Optional[str] = None


class LeadUpdate(BaseModel):
    name: Optional[str]
    email: Optional[str]
    company: Optional[str]
    conversation_stage: Optional[ConversationStage]
    intent_level: Optional[IntentLevel]
    user_sentiment: Optional[UserSentiment]


class LeadOut(BaseModel):
    id: UUID
    organization_id: UUID
    name: Optional[str]
    phone: str
    email: Optional[str]
    company: Optional[str]

    conversation_stage: Optional[ConversationStage]
    intent_level: Optional[IntentLevel]
    user_sentiment: Optional[UserSentiment]

    created_at: datetime
    updated_at: Optional[datetime]


# ======================================================
# Analytics
# ======================================================

class AnalyticsOut(BaseModel):
    metric_date: datetime
    total_conversations: int
    total_messages: int


class AnalyticsReportOut(BaseModel):
    sentiment_breakdown: Dict[str, int]
    peak_activity_time: Dict[str, int]
    message_from_stats: Dict[str, int]
    intent_level_stats: Dict[str, int]


# ======================================================
# WhatsApp Settings
# ======================================================

class WhatsAppIntegrationCreate(BaseModel):
    access_token: str
    version: str
    verify_token: str
    app_secret: str
    phone_number_id: str


class WhatsAppIntegrationUpdate(BaseModel):
    access_token: Optional[str]
    version: Optional[str]
    verify_token: Optional[str]
    app_secret: Optional[str]
    phone_number_id: Optional[str]


class WhatsAppIntegrationOut(BaseModel):
    id: UUID
    organization_id: UUID
    phone_number_id: str
    is_connected: bool
    created_at: datetime
    updated_at: Optional[datetime]


class WhatsAppStatusOut(BaseModel):
    is_connected: bool = False


# ======================================================
# WebSocket (Unified Envelope)
# ======================================================

class WebSocketEnvelope(BaseModel):
    event: str
    payload: Dict[str, Any]


# ======================================================
# WebSocket Payloads
# ======================================================

class WSConversationUpdated(BaseModel):
    conversation: ConversationOut
    message: Optional[MessageOut]


class WSTakeoverStarted(BaseModel):
    conversation_id: UUID
    assigned_user_id: UUID


class WSTakeoverEnded(BaseModel):
    conversation_id: UUID


class WSActionConversationsFlagged(BaseModel):
    cta_id: UUID
    conversation_ids: List[UUID]


class WSActionHumanAttentionRequired(BaseModel):
    conversation_ids: List[UUID]