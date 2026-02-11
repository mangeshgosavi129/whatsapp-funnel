from enum import Enum

class ConversationStage(str, Enum):
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    PRICING = "pricing"
    CTA = "cta"
    LOST = "lost"
    GHOSTED = "ghosted"

class IntentLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    UNKNOWN = "unknown"


class ConversationMode(str, Enum):
    BOT = "bot"
    HUMAN = "human"


class DecisionAction(str, Enum):
    """Pipeline Step 2 output: what action to take."""
    SEND_NOW = "send_now"
    WAIT_SCHEDULE = "wait_schedule"
    FLAG_ATTENTION = "flag_attention"
    INITIATE_CTA = "initiate_cta"


class RiskLevel(str, Enum):
    """Risk assessment levels for spam/policy/hallucination."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PipelineStep(str, Enum):
    """Tracking which pipeline step is executing."""
    ANALYZE = "analyze"
    DECIDE = "decide"
    GENERATE = "generate"
    SUMMARIZE = "summarize"


class UserSentiment(str, Enum):
    ANNOYED = "annoyed"
    DISTRUSTFUL = "distrustful"
    CONFUSED = "confused"
    CURIOUS = "curious"
    DISAPPOINTED = "disappointed"
    NEUTRAL = "neutral"
    UNINTERESTED = "uninterested"

class TemplateStatus(str, Enum):
    # Legacy compatibility: keep PENDING to avoid enum lookup errors on existing rows
    PENDING = "pending"
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"

class MessageFrom(str, Enum):
    LEAD = "lead"
    BOT = "bot"
    HUMAN = "human"

class WSEvents:
    # Inbox
    CONVERSATION_UPDATED = "conversation:updated"
    TAKEOVER_STARTED = "conversation:takeover_started"
    TAKEOVER_ENDED = "conversation:takeover_ended"

    # Action Center
    ACTION_CONVERSATIONS_FLAGGED = "action:conversations_flagged"
    ACTION_HUMAN_ATTENTION_REQUIRED = "action:human_attention_required"

    ACTION_CTA_INITIATED = "action:cta_initiated"
    # System
    ACK = "ack"
    ERROR = "error"
    SERVER_HELLO = "server:hello"
    CLIENT_HEARTBEAT = "client:heartbeat"