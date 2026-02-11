"""
Unified Generate Step.
Combines Observation, Decision, and Response into a single LLM call.
"""
import logging
import time
from typing import Tuple

from llm.api_helpers import make_api_call
from llm.schemas import PipelineInput, GenerateOutput, RiskFlags
from llm.prompts import GENERATE_SYSTEM_PROMPT, GENERATE_USER_TEMPLATE
from llm.utils import normalize_enum, format_ctas
from server.enums import (
    ConversationStage,
    DecisionAction,
    IntentLevel,
    UserSentiment,
    RiskLevel
)

logger = logging.getLogger(__name__)


# JSON Schema for Generate output
GENERATE_SCHEMA = {
    "name": "generate_output",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
             # Reasoning
            "thought_process": {"type": "string"},
            
            # Observation
            "intent_level": {"type": "string", "enum": ["low", "medium", "high", "very_high", "unknown"]},
            "user_sentiment": {"type": "string", "enum": ["neutral", "curious", "annoyed", "distrustful", "confused", "disappointed", "uninterested"]},
            "risk_flags": {
                "type": "object",
                "properties": {
                    "spam_risk": {"type": "string", "enum": ["low", "medium", "high"]},
                    "policy_risk": {"type": "string", "enum": ["low", "medium", "high"]},
                    "hallucination_risk": {"type": "string", "enum": ["low", "medium", "high"]}
                },
                "required": ["spam_risk", "policy_risk", "hallucination_risk"],
                "additionalProperties": False
            },
            
            # Decision
            "action": {"type": "string", "enum": ["send_now", "wait_schedule", "flag_attention", "initiate_cta"]},
            "new_stage": {"type": "string", "enum": ["greeting", "qualification", "pricing", "cta", "followup", "closed", "lost", "ghosted"]},
            "should_respond": {"type": "boolean"},
            
            # Payload
            "selected_cta_id": {"type": ["string", "null"]},
            "cta_scheduled_at": {"type": ["string", "null"]},
            "followup_in_minutes": {"type": "integer"},
            "followup_reason": {"type": "string"},
            
            # Response
            "message_text": {"type": "string"},
            "message_language": {"type": "string"},
            
            # Metadata
            "confidence": {"type": "number"},
            "needs_human_attention": {"type": "boolean"}
        },
        "required": [
            "thought_process", 
            "intent_level", "user_sentiment", "risk_flags",
            "action", "new_stage", "should_respond",
            "selected_cta_id", "cta_scheduled_at", "followup_in_minutes", "followup_reason",
            "message_text", "message_language",
            "confidence", "needs_human_attention"
        ],
        "additionalProperties": False
    }
}


def _format_messages(messages: list) -> str:
    """Format messages for prompt."""
    if not messages:
        return "No messages yet"
    
    lines = []
    for msg in messages:
        lines.append(f"[{msg.sender}] {msg.text}")
    return "\n".join(lines)


def _build_user_prompt(context: PipelineInput) -> str:
    """Build the user prompt with context."""
    return GENERATE_USER_TEMPLATE.format(
        business_name=context.business_name,
        business_description=context.business_description,
        flow_prompt=context.flow_prompt,
        dynamic_knowledge_context=context.dynamic_knowledge_context or "No specific knowledge retrieved.",
        rolling_summary=context.rolling_summary or "No summary yet",
        conversation_stage=context.conversation_stage.value,
        total_nudges=context.nudges.total_nudges,
        now_local=context.timing.now_local,
        whatsapp_window_open=context.timing.whatsapp_window_open,
        available_ctas=format_ctas(context.available_ctas),
        last_messages=_format_messages(context.last_messages),
    )


def _validate_and_build_output(data: dict, context: PipelineInput) -> GenerateOutput:
    """Validate and build typed output from raw JSON."""
    
    # Safe Enum Conversion
    rf = data.get("risk_flags", {})
    risk_flags = RiskFlags(
        spam_risk=normalize_enum(rf.get("spam_risk"), RiskLevel, RiskLevel.LOW),
        policy_risk=normalize_enum(rf.get("policy_risk"), RiskLevel, RiskLevel.LOW),
        hallucination_risk=normalize_enum(rf.get("hallucination_risk"), RiskLevel, RiskLevel.LOW),
    )
    
    llm_stage = normalize_enum(data.get("new_stage"), ConversationStage, context.conversation_stage)
    action = normalize_enum(data.get("action"), DecisionAction, DecisionAction.WAIT_SCHEDULE)
    intent = normalize_enum(data.get("intent_level"), IntentLevel, IntentLevel.UNKNOWN)
    sentiment = normalize_enum(data.get("user_sentiment"), UserSentiment, UserSentiment.NEUTRAL)
    
    return GenerateOutput(
        thought_process=data.get("thought_process", "") or "",
        intent_level=intent,
        user_sentiment=sentiment,
        risk_flags=risk_flags,
        action=action,
        new_stage=llm_stage,
        should_respond=bool(data.get("should_respond", False)),
        selected_cta_id=data.get("selected_cta_id"),
        cta_scheduled_at=data.get("cta_scheduled_at"),
        followup_in_minutes=int(data.get("followup_in_minutes") or 0),
        followup_reason=data.get("followup_reason", "") or "",
        message_text=data.get("message_text", "") or "",
        message_language=data.get("message_language", "en"),
        confidence=float(data.get("confidence") or 0.5),
        needs_human_attention=bool(data.get("needs_human_attention", False)),
    )


def run_generate(context: PipelineInput) -> Tuple[GenerateOutput, int, int]:
    """
    Run the unified Generate step.
    One call to rule them all.
    """
    user_prompt = _build_user_prompt(context)
    
    start_time = time.time()
    
    try:
        data = make_api_call(
            messages=[
                {"role": "system", "content": GENERATE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_schema", "json_schema": GENERATE_SCHEMA},
            temperature=0.3,
            step_name="Generate",
            strict=True
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        output = _validate_and_build_output(data, context)
        
        logger.info(f"Generate: {output.action.value} -> {output.new_stage.value} (Conf: {output.confidence})")
        if output.message_text:
            logger.info(f"Generated Message: {output.message_text[:50]}...")
            
        return output, latency_ms, 0
        
    except Exception as e:
        logger.error(f"Generate failed: {e}", exc_info=True)
        
        # Emergency Fallback
        fallback_output = GenerateOutput(
            thought_process="System Error - Fallback triggered",
            intent_level=context.intent_level,
            user_sentiment=context.user_sentiment,
            risk_flags=RiskFlags(),
            action=DecisionAction.WAIT_SCHEDULE,
            new_stage=context.conversation_stage,
            should_respond=False,
            confidence=0.0,
            needs_human_attention=True,
            message_text="",
        )
        return fallback_output, int((time.time() - start_time) * 1000), 0
