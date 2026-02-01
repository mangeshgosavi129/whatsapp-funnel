"""
Pydantic schemas for HTL Pipeline I/O.
Strict JSON schemas ensure LLM outputs are validated and typed.
"""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from server.enums import (
    ConversationStage,
    IntentLevel,
    UserSentiment,
    CTAType,
    DecisionAction,
    RiskLevel,
)


# ============================================================
# Pipeline Input Context
# ============================================================

class MessageContext(BaseModel):
    """A single message in conversation history."""
    sender: Literal["lead", "bot", "human"]
    text: str
    timestamp: str  # ISO format


class TimingContext(BaseModel):
    """Timing information for decisions."""
    now_local: str
    last_user_message_at: Optional[str] = None
    last_bot_message_at: Optional[str] = None
    whatsapp_window_open: bool = True


class NudgeContext(BaseModel):
    """Anti-spam tracking."""
    followup_count_24h: int = 0
    total_nudges: int = 0


class PipelineInput(BaseModel):
    """
    Complete input context for the HTL pipeline.
    Kept minimal for token efficiency.
    """
    # Business context
    business_name: str
    business_description: str = ""
    
    # Conversation context
    rolling_summary: str = ""
    last_3_messages: List[MessageContext] = []
    
    # Current state
    conversation_stage: ConversationStage
    conversation_mode: Literal["bot", "human"]
    intent_level: IntentLevel
    user_sentiment: UserSentiment
    active_cta: Optional[CTAType] = None
    
    # Timing
    timing: TimingContext
    nudges: NudgeContext
    
    # Constraints (from business config)
    max_words: int = 80
    questions_per_message: int = 1
    language_pref: str = "en"


# ============================================================
# Step 1: Analyze Output
# ============================================================

class RiskFlags(BaseModel):
    """Risk assessment for the conversation."""
    spam_risk: RiskLevel = RiskLevel.LOW
    policy_risk: RiskLevel = RiskLevel.LOW
    hallucination_risk: RiskLevel = RiskLevel.LOW


class KBRequirement(BaseModel):
    """Knowledge base lookup need."""
    required: bool = False
    query: str = ""
    reason: str = ""


class AnalyzeOutput(BaseModel):
    """
    Output from Step 1: Analyze.
    Understands the situation and detects signals.
    """
    situation_summary: str = Field(..., max_length=200)
    lead_goal_guess: str = Field(..., max_length=100)
    missing_info: List[str] = Field(default_factory=list, max_length=5)
    detected_objections: List[str] = Field(default_factory=list, max_length=3)
    stage_recommendation: ConversationStage
    intent_level: IntentLevel
    user_sentiment: UserSentiment
    risk_flags: RiskFlags
    need_kb: KBRequirement
    confidence: float = Field(..., ge=0.0, le=1.0)


# ============================================================
# Step 2: Decision Output
# ============================================================

class DecisionOutput(BaseModel):
    """
    Output from Step 2: Decide.
    Determines what action to take.
    """
    action: DecisionAction
    why: str = Field(..., max_length=150)
    next_stage: ConversationStage
    recommended_cta: Optional[CTAType] = None
    cta_scheduled_time: Optional[str] = None  # ISO datetime when CTA should occur
    cta_name: Optional[str] = None  # Human-readable label for the CTA
    followup_in_minutes: int = Field(default=0, ge=0)
    followup_reason: str = ""
    kb_used: bool = False
    template_required: bool = False


# ============================================================
# Step 3: Generate Output
# ============================================================

class StatePatch(BaseModel):
    """State updates to apply after message generation."""
    intent_level: Optional[IntentLevel] = None
    user_sentiment: Optional[UserSentiment] = None
    conversation_stage: Optional[ConversationStage] = None


class SelfCheck(BaseModel):
    """Guardrail self-check results."""
    guardrails_pass: bool = True
    violations: List[str] = Field(default_factory=list)


class GenerateOutput(BaseModel):
    """
    Output from Step 3: Generate.
    The actual message to send (if any).
    """
    message_text: str = ""  # Empty if not sending
    message_language: str = "en"
    cta_type: Optional[CTAType] = None
    next_stage: ConversationStage
    next_followup_in_minutes: int = 0
    state_patch: StatePatch
    self_check: SelfCheck


# ============================================================
# Step 4: Summary Output
# ============================================================

class SummaryOutput(BaseModel):
    """
    Output from Step 4: Summarize.
    Updated rolling summary of the conversation.
    """
    updated_rolling_summary: str = Field(..., max_length=500)  # 80-200 words typically


# ============================================================
# Complete Pipeline Result
# ============================================================

class PipelineResult(BaseModel):
    """
    Complete result from running the HTL pipeline.
    Contains outputs from all steps.
    """
    # Step outputs
    analysis: AnalyzeOutput
    decision: DecisionOutput
    response: Optional[GenerateOutput] = None  # None if not sending
    summary: SummaryOutput
    
    # Metadata
    pipeline_latency_ms: int = 0
    total_tokens_used: int = 0
    
    # Computed actions
    should_send_message: bool = False
    should_schedule_followup: bool = False
    should_escalate: bool = False
    should_initiate_cta: bool = False
