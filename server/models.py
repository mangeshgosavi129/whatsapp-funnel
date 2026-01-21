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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from server.enums import (
    ConversationStage,
    IntentLevel,
    CTAType,
    ConversationMode,
    UserSentiment,
    TemplateStatus,
    MessageFrom,
)

Base = declarative_base()

# --------------------
# Core
# --------------------

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
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

# --------------------
# Inbox / Conversations
# --------------------

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    cta_id = Column(UUID(as_uuid=True), ForeignKey("ctas.id"), nullable=True) # Litle bit confusiing

    stage = Column(SQLEnum(ConversationStage), nullable=False)
    intent_level = Column(SQLEnum(IntentLevel), nullable=True)
    mode = Column(SQLEnum(ConversationMode), nullable=False)
    user_sentiment = Column(SQLEnum(UserSentiment), nullable=True)
    rolling_summary = Column(Text, nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    last_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization", back_populates="conversations")
    lead = relationship("Lead", back_populates="conversations")
    cta = relationship("CTA", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id = Column(UUID(as_uuid=True),ForeignKey("organizations.id"),nullable=False)
    conversation_id = Column(UUID(as_uuid=True),ForeignKey("conversations.id"),nullable=False)
    
    message_from = Column(SQLEnum(MessageFrom), nullable=False)
    assigned_user_id = Column(UUID(as_uuid=True),ForeignKey("users.id"),nullable=True)
    
    content = Column(Text, nullable=False)
    status = Column(String(30),nullable=False,default="sent") 
    created_at = Column(DateTime(timezone=True),server_default=func.now())

    conversation = relationship("Conversation",back_populates="messages")
    assigned_user = relationship("User",back_populates="messages")
# --------------------
# CTAs / Actions
# --------------------

class CTA(Base):
    __tablename__ = "ctas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False) # book a call
    cta_type = Column(SQLEnum(CTAType), nullable=False) #
    is_active = Column(Boolean, default=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    
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
    content = Column(Text, nullable=False)

    status = Column(SQLEnum(TemplateStatus), default=TemplateStatus.PENDING)
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

    conversation_stage = Column(SQLEnum(ConversationStage), nullable=True)
    intent_level = Column(SQLEnum(IntentLevel), nullable=True)
    user_sentiment = Column(SQLEnum(UserSentiment), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    conversations = relationship("Conversation", back_populates="lead")

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

    access_token = Column(String(255), nullable=False)
    version = Column(String(20), nullable=False)
    verify_token = Column(String(255), nullable=False) 
    app_secret = Column(String(255), nullable=False)
    phone_number_id = Column(String(255), nullable=False)
    business_account_id = Column(String(255), nullable=False)
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