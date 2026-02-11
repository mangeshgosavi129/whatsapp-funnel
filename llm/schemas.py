"""
Pydantic schemas for Unified Generation Pipeline.
Strict JSON schemas ensure LLM outputs are validated and typed.
"""
from typing import Optional, List, Literal, Dict
from uuid import UUID
from pydantic import BaseModel, Field
from server.enums import (
    ConversationStage,
    IntentLevel,
    UserSentiment,
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
    Complete input context for the pipeline.
    Kept minimal for token efficiency.
    """
    # Business context
    organization_id: UUID
    business_name: str
    business_description: str = ""
    flow_prompt: str = ""  # Conversation flow/sales script instructions
    
    # CTAs
    available_ctas: List[Dict[str, str]] = []  # [{id: UUID, name: str}]
    
    # Conversation context
    rolling_summary: str = ""
    last_messages: List[MessageContext] = []
    
    # Current state
    conversation_stage: ConversationStage
    conversation_mode: Literal["bot", "human"]
    intent_level: IntentLevel
    user_sentiment: UserSentiment
    active_cta_id: Optional[UUID] = None
    
    # Timing
    timing: TimingContext
    nudges: NudgeContext
    
    # Constraints (from business config)
    max_words: int = 80
    questions_per_message: int = 1
    language_pref: str = "en"
    
    # RAG Context (injected by Pipeline)
    dynamic_knowledge_context: Optional[str] = None


# ============================================================
# Unified Generation Step
# ============================================================

class RiskFlags(BaseModel):
    """Risk assessment for the conversation."""
    spam_risk: RiskLevel = RiskLevel.LOW
    policy_risk: RiskLevel = RiskLevel.LOW
    hallucination_risk: RiskLevel = RiskLevel.LOW


class GenerateOutput(BaseModel):
    """
    Unified output from the single LLM generation step.
    Combines reasoning, decision making, and response generation.
    """
    # Reasoning
    thought_process: str = Field(..., description="Chain of thought reasoning")
    
    # Observation / Classification
    intent_level: IntentLevel
    user_sentiment: UserSentiment
    risk_flags: RiskFlags
    
    # Decision
    action: DecisionAction
    new_stage: ConversationStage
    should_respond: bool = False
    
    # Action Payload
    selected_cta_id: Optional[UUID] = None
    cta_scheduled_at: Optional[str] = None
    followup_in_minutes: int = 0
    followup_reason: str = ""
    
    # Response
    message_text: str = ""
    message_language: str = "en"
    
    # Metadata
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_human_attention: bool = False


# ============================================================
# Step 4: Memory Output (Archivist)
# ============================================================

class MemoryOutput(BaseModel):
    """
    Output from Step 4: Memory (Archivist).
    Updated rolling summary.
    """
    updated_rolling_summary: str = Field(..., max_length=2000)
    needs_recursive_summary: bool = False


# Backward compatibility alias
SummaryOutput = MemoryOutput


# ============================================================
# Complete Pipeline Result
# ============================================================

class PipelineResult(BaseModel):
    """
    Complete result from running the pipeline.
    """
    # Unified output
    generate: GenerateOutput
    
    # Memory output (separate step)
    memory: Optional[MemoryOutput] = None
    
    # Metadata
    pipeline_latency_ms: int = 0
    total_tokens_used: int = 0
    
    # Async Flags
    needs_background_summary: bool = True
    
    # Computed action helpers
    @property
    def should_send_message(self) -> bool:
        return self.generate.should_respond and bool(self.generate.message_text)
    
    @property
    def should_schedule_followup(self) -> bool:
        return self.generate.action == DecisionAction.WAIT_SCHEDULE
    
    @property
    def should_escalate(self) -> bool:
        return self.generate.needs_human_attention
        
    @property
    def should_initiate_cta(self) -> bool:
        return self.generate.action == DecisionAction.INITIATE_CTA

