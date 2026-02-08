"""
Pydantic schemas for Eyes → Brain → Mouth → Memory Pipeline.
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
# Step 1: Eyes Output (Observer)
# ============================================================

class RiskFlags(BaseModel):
    """Risk assessment for the conversation."""
    spam_risk: RiskLevel = RiskLevel.LOW
    policy_risk: RiskLevel = RiskLevel.LOW
    hallucination_risk: RiskLevel = RiskLevel.LOW


class EyesOutput(BaseModel):
    """
    Output from Step 1: Eyes (Observer).
    Analyzes conversation state and produces observation for Brain.
    """
    # Core observation for downstream (Brain)
    observation: str = Field(..., max_length=1500)
    
    # Internal reasoning
    thought_process: str = Field(..., max_length=2000)
    situation_summary: str = Field(..., max_length=1000)
    
    # Updated enums
    intent_level: IntentLevel
    user_sentiment: UserSentiment
    risk_flags: RiskFlags
    
    # Confidence
    # Confidence
    confidence: float = Field(..., ge=0.0, le=1.0)
    
    # RAG Triggers
    knowledge_needed: bool = False
    knowledge_topic: Optional[str] = None


# ============================================================
# Step 2: Brain Output (Strategist)
# ============================================================

class BrainOutput(BaseModel):
    """
    Output from Step 2: Brain (Strategist).
    Makes decisions based on Eyes observation.
    """
    # Implementation plan for Mouth (THE KEY HANDOFF)
    implementation_plan: str = Field(..., max_length=1500)
    
    # Decision
    action: DecisionAction
    new_stage: ConversationStage
    should_respond: bool = False
    
    # Action Payload
    selected_cta_id: Optional[UUID] = None
    cta_scheduled_at: Optional[str] = None  # ISO format
    followup_in_minutes: int = 0
    followup_reason: str = ""
    
    # Metadata
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_human_attention: bool = False


# Backward compatibility alias
ClassifyOutput = BrainOutput


# ============================================================
# Step 3: Mouth Output (Communicator)
# ============================================================

class MouthOutput(BaseModel):
    """
    Output from Step 3: Mouth (Communicator).
    The actual message to send.
    """
    message_text: str = ""
    message_language: str = "en"
    
    # Self-check
    self_check_passed: bool = True
    violations: List[str] = Field(default_factory=list)


# Backward compatibility alias
GenerateOutput = MouthOutput


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
    # Step outputs
    eyes: Optional[EyesOutput] = None
    brain: BrainOutput
    mouth: Optional[MouthOutput] = None
    memory: Optional[MemoryOutput] = None
    
    # Backward compatibility aliases
    @property
    def classification(self) -> BrainOutput:
        return self.brain
    
    @property
    def response(self) -> Optional[MouthOutput]:
        return self.mouth
    
    @property
    def summary(self) -> Optional[MemoryOutput]:
        return self.memory
    
    # Metadata
    pipeline_latency_ms: int = 0
    total_tokens_used: int = 0
    
    # Async Flags
    needs_background_summary: bool = True
    
    # Computed action helpers
    @property
    def should_send_message(self) -> bool:
        return self.brain.should_respond and self.mouth is not None and bool(self.mouth.message_text)
    
    @property
    def should_schedule_followup(self) -> bool:
        return self.brain.action == DecisionAction.WAIT_SCHEDULE
    
    @property
    def should_escalate(self) -> bool:
        return self.brain.needs_human_attention
        
    @property
    def should_initiate_cta(self) -> bool:
        return self.brain.action == DecisionAction.INITIATE_CTA
