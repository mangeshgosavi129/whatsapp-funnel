import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from server.enums import (
    ConversationStage,
    IntentLevel,
    ConversationMode,
    UserSentiment,
    TemplateStatus,
    MessageFrom,
)
from server.database import Base

# --------------------
# Core
# --------------------

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Business configuration for chatbot
    business_name = Column(Text, nullable=True)  # Chatbot persona name
    business_description = Column(Text, nullable=True)  # Business context for LLM
    flow_prompt = Column(Text, nullable=True)  # Conversation flow instructions
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    users = relationship("User", back_populates="organization")
    conversations = relationship("Conversation", back_populates="organization")

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization", back_populates="users")
    messages = relationship("Message", back_populates="assigned_user")

# --------------------
# Inbox / Conversations
# --------------------

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    cta_id = Column(UUID(as_uuid=True), ForeignKey("ctas.id"), nullable=True)

    # === Sales State ===
    cta_scheduled_at = Column(DateTime(timezone=True), nullable=True)
    stage = Column(SQLEnum(ConversationStage, native_enum=False), nullable=False)
    intent_level = Column(SQLEnum(IntentLevel, native_enum=False), nullable=True)
    mode = Column(SQLEnum(ConversationMode, native_enum=False), nullable=False)
    user_sentiment = Column(SQLEnum(UserSentiment, native_enum=False), nullable=True)
    needs_human_attention = Column(Boolean, default=False)
    human_attention_resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # === Context ===
    rolling_summary = Column(Text, nullable=True)
    last_message = Column(Text, nullable=True)
    
    # === Timing (for WhatsApp window & decisions) ===
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    last_user_message_at = Column(DateTime(timezone=True), nullable=True)
    last_bot_message_at = Column(DateTime(timezone=True), nullable=True)
    
    # === Anti-spam tracking ===
    followup_count_24h = Column(Integer, default=0)
    total_nudges = Column(Integer, default=0)
    scheduled_followup_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization", back_populates="conversations")
    lead = relationship("Lead", back_populates="conversations")
    cta = relationship("CTA", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    message_from = Column(SQLEnum(MessageFrom, native_enum=False), nullable=False)
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    content = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="sent")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")
    lead = relationship("Lead", back_populates="messages")
    assigned_user = relationship("User", back_populates="messages")
# --------------------
# CTAs / Actions
# --------------------

class CTA(Base):
    __tablename__ = "ctas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    conversations = relationship("Conversation", back_populates="cta")

# --------------------
# Templates
# --------------------

class Template(Base):
    __tablename__ = "templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=True)  # MARKETING, UTILITY, AUTHENTICATION
    language = Column(String(20), nullable=True)  # e.g., 'en_US'
    components = Column(JSON, nullable=True)      # List of components (header, body, footer, buttons)
    
    content = Column(Text, nullable=True)         # Legacy field, keeping for compatibility but primary content is in components

    status = Column(SQLEnum(TemplateStatus, native_enum=False), default=TemplateStatus.DRAFT)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# -------------------
# Followup Strategy
# -------------------

class Followup(Base):
    __tablename__ = "followups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=False)

    delay_hours = Column(Integer, nullable=False)
    sequence_order = Column(Integer, nullable=False)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# --------------------
# Leads
# --------------------

class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=False)
    email = Column(String, nullable=True)
    company = Column(String, nullable=True)

    conversation_stage = Column(SQLEnum(ConversationStage, native_enum=False), nullable=True)
    intent_level = Column(SQLEnum(IntentLevel, native_enum=False), nullable=True)
    user_sentiment = Column(SQLEnum(UserSentiment, native_enum=False), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    conversations = relationship("Conversation", back_populates="lead")
    messages = relationship("Message", back_populates="lead")

# --------------------
# Analytics
# --------------------
class Analytics(Base):
    __tablename__ = "analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    metric_date = Column(DateTime(timezone=True), nullable=False)
    total_conversations = Column(Integer, nullable=False)
    total_messages = Column(Integer, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# --------------------
# Settings / Integrations
# --------------------

class WhatsAppIntegration(Base):
    __tablename__ = "whatsapp_integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    access_token = Column(Text, nullable=False)
    version = Column(String(20), nullable=False)
    app_secret = Column(String(255), nullable=False)
    phone_number_id = Column(String(255), nullable=False)
    is_connected = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# --------------------
# System / Infra
# --------------------

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    entity_type = Column(String(100), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(100), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# --------------------
# HTL Pipeline
# --------------------



class ConversationEvent(Base):
    """
    Audit log for pipeline execution and conversation events.
    Useful for debugging and analytics.
    """
    __tablename__ = "conversation_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    
    event_type = Column(String(50), nullable=False)  # message_received, pipeline_run, stage_change, etc.
    pipeline_step = Column(String(20), nullable=True)  # analyze, decide, generate, summarize
    
    input_summary = Column(Text, nullable=True)  # Compact input summary (not full JSON to save space)
    output_summary = Column(Text, nullable=True)  # Compact output summary
    
    latency_ms = Column(Integer, nullable=True)  # For performance tracking
    tokens_used = Column(Integer, nullable=True)  # For cost tracking
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# --------------------
# Knowledge Base (RAG)
# --------------------

class KnowledgeItem(Base):
    """
    RAG Knowledge Base Item.
    Stores chunks of policies, FAQs, and facts.
    Uses Hybrid Search: Vector (Semantic) + TSVector (Keyword).
    """
    __tablename__ = "knowledge_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    
    # 1536 dimensions for text-embedding-3-small
    embedding = Column(Vector(1536), nullable=True)
    
    # Full-text search vector (auto-updated via trigger or app logic)
    search_vector = Column(TSVECTOR, nullable=True)
    
    metadata_ = Column("metadata", JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization", back_populates="knowledge_items")

Organization.knowledge_items = relationship("KnowledgeItem", order_by=KnowledgeItem.id, back_populates="organization")