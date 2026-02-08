from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from uuid import UUID
from pydantic import BaseModel, Field
from server.enums import (
    ConversationStage,
    IntentLevel,
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
    high_intent_leads: int = 0
    action_items: List[Dict[str, Any]] = []


# ======================================================
# User / Org
# ======================================================

class OrganizationOut(BaseModel):
    id: UUID
    name: str
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    flow_prompt: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]


class OrganizationUpdate(BaseModel):
    """Update organization configuration."""
    name: Optional[str] = None
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    flow_prompt: Optional[str] = None


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
    needs_human_attention: bool = False

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
    status: Literal["sent", "delivered", "read", "failed", "received"]
    created_at: datetime


# ======================================================
# CTAs
# ======================================================

class CTACreate(BaseModel):
    name: str

class CTAUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class CTAOut(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]


# ======================================================
# Templates
# ======================================================

class TemplateCreate(BaseModel):
    name: str
    category: str
    language: str
    components: List[Dict[str, Any]]


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    components: Optional[List[Dict[str, Any]]] = None


class TemplateStatusOut(BaseModel):
    status: TemplateStatus
    approved_at: Optional[datetime]
    rejection_reason: Optional[str]


class TemplateOut(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    category: Optional[str]
    language: Optional[str]
    components: Optional[List[Dict[str, Any]]]
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
    daily_activity: Dict[str, int]
    stage_breakdown: Dict[str, int]


# ======================================================
# WhatsApp Settings
# ======================================================

class WhatsAppIntegrationCreate(BaseModel):
    access_token: str
    version: str
    app_secret: str
    phone_number_id: str


class WhatsAppIntegrationUpdate(BaseModel):
    access_token: Optional[str]
    version: Optional[str]
    app_secret: Optional[str]
    phone_number_id: Optional[str]


class WhatsAppIntegrationOut(BaseModel):
    id: UUID
    organization_id: UUID
    phone_number_id: str
    access_token: str
    app_secret: str
    version: str
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


# ======================================================
# Internal API Schemas (for whatsapp_worker)
# ======================================================

class InternalIntegrationWithOrgOut(BaseModel):
    """Combined WhatsApp integration and organization data."""
    # Integration fields
    integration_id: UUID
    access_token: str
    version: str
    app_secret: str
    phone_number_id: str
    is_connected: bool
    # Organization fields
    organization_id: UUID
    organization_name: str
    is_active: bool
    # Business configuration
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    flow_prompt: Optional[str] = None


class InternalLeadCreate(BaseModel):
    """Create a new lead via internal API."""
    organization_id: UUID
    phone: str
    name: Optional[str] = None


class InternalLeadOut(BaseModel):
    """Lead data returned from internal API."""
    id: UUID
    organization_id: UUID
    phone: str
    name: Optional[str]
    email: Optional[str]
    company: Optional[str]
    conversation_stage: Optional[ConversationStage]
    intent_level: Optional[IntentLevel]
    user_sentiment: Optional[UserSentiment]
    created_at: datetime
    updated_at: Optional[datetime]


class InternalConversationCreate(BaseModel):
    """Create a new conversation via internal API."""
    organization_id: UUID
    lead_id: UUID


class InternalConversationOut(BaseModel):
    """Full conversation data for internal API."""
    id: UUID
    organization_id: UUID
    lead_id: UUID
    cta_id: Optional[UUID]
    cta_scheduled_at: Optional[datetime]
    stage: ConversationStage
    intent_level: Optional[IntentLevel]
    mode: ConversationMode
    user_sentiment: Optional[UserSentiment]
    needs_human_attention: bool = False
    rolling_summary: Optional[str]
    last_message: Optional[str]
    last_message_at: Optional[datetime]
    last_user_message_at: Optional[datetime]
    last_bot_message_at: Optional[datetime]
    followup_count_24h: int
    total_nudges: int
    scheduled_followup_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]


class InternalConversationUpdate(BaseModel):
    """Update conversation state via internal API."""
    stage: Optional[ConversationStage] = None
    mode: Optional[ConversationMode] = None
    intent_level: Optional[IntentLevel] = None
    user_sentiment: Optional[UserSentiment] = None
    needs_human_attention: Optional[bool] = None
    rolling_summary: Optional[str] = None
    last_message: Optional[str] = None
    followup_count_24h: Optional[int] = None
    total_nudges: Optional[int] = None
    scheduled_followup_at: Optional[datetime] = None
    cta_id: Optional[UUID] = None
    cta_scheduled_at: Optional[datetime] = None


class InternalMessageContext(BaseModel):
    """Message context for pipeline input."""
    sender: str  # "lead", "bot", or "human"
    text: str
    timestamp: str


class InternalIncomingMessageCreate(BaseModel):
    """Store incoming lead message."""
    conversation_id: UUID
    lead_id: Optional[UUID] = None
    content: str


class InternalOutgoingMessageCreate(BaseModel):
    """Store outgoing bot/human message."""
    conversation_id: UUID
    lead_id: Optional[UUID] = None
    content: str
    message_from: MessageFrom


class InternalMessageOut(BaseModel):
    """Message data returned from internal API."""
    id: UUID
    organization_id: UUID
    conversation_id: UUID
    lead_id: UUID
    message_from: MessageFrom
    content: str
    status: str
    created_at: datetime


class InternalDueFollowupOut(BaseModel):
    """Details for a conversation that is due for a followup."""
    followup_type: ConversationStage  # FOLLOWUP_10M, FOLLOWUP_3H, or FOLLOWUP_6H
    conversation: InternalConversationOut
    lead: InternalLeadOut
    organization_id: UUID
    organization_name: str
    access_token: str
    phone_number_id: str
    version: str
    # Business configuration
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    flow_prompt: Optional[str] = None


class InternalPipelineEventCreate(BaseModel):
    """Log a pipeline execution event."""
    conversation_id: UUID
    event_type: str
    pipeline_step: Optional[str] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    latency_ms: Optional[int] = None
    tokens_used: Optional[int] = None


class InternalPipelineEventOut(BaseModel):
    """Pipeline event data."""
    id: UUID
    conversation_id: UUID
    event_type: str
    pipeline_step: Optional[str]
    input_summary: Optional[str]
    output_summary: Optional[str]
    latency_ms: Optional[int]
    tokens_used: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# --------------------
# Knowledge (RAG)
# --------------------

class KnowledgeIngestRequest(BaseModel):
    content: str  # Markdown content
    title_prefix: Optional[str] = None # e.g. "Refund Policy"

class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = 5

class KnowledgeItemOut(BaseModel):
    id: UUID
    title: str
    content: str
    score: Optional[float] = None
    
    class Config:
        from_attributes = True


class KnowledgeMetadataOut(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    
    class Config:
        from_attributes = True