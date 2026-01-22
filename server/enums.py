from enum import Enum

class ConversationStage(str, Enum):
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    PRICING = "pricing"
    CTA = "cta"
    FOLLOWUP = "followup"
    CLOSED = "closed"
    LOST = "lost"
    GHOSTED = "ghosted"

class IntentLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    UNKNOWN = "unknown"

class CTAType(str, Enum):
    BOOK_CALL = "book_call"
    BOOK_DEMO = "book_demo"
    BOOK_MEETING = "book_meeting"
    

class ConversationMode(str, Enum):
    BOT = "bot"
    HUMAN = "human"


class DecisionAction(str, Enum):
    """Pipeline Step 2 output: what action to take."""
    SEND_NOW = "send_now"
    WAIT_SCHEDULE = "wait_schedule"
    HANDOFF_HUMAN = "handoff_human"


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


class ScheduledActionStatus(str, Enum):
    """Status of scheduled follow-up actions."""
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"

class UserSentiment(str, Enum):
    ANNOYED = "annoyed"
    DISTRUSTFUL = "distrustful"
    CONFUSED = "confused"
    CURIOUS = "curious"
    DISAPPOINTED = "disappointed"
    NEUTRAL = "neutral"
    UNINTERESTED = "uninterested"

class TemplateStatus(str, Enum):
    PENDING = "pending"
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

    # System
    ACK = "ack"
    ERROR = "error"
    SERVER_HELLO = "server:hello"
    CLIENT_HEARTBEAT = "client:heartbeat"