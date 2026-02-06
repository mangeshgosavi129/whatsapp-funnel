"""
Step 1: EYES - Observer.
Analyzes conversation state and produces observation for Brain.
"""
import logging
import time
from typing import Tuple
from llm.api_helpers import make_api_call
from llm.schemas import PipelineInput, EyesOutput, RiskFlags
from llm.prompts import EYES_SYSTEM_PROMPT, EYES_USER_TEMPLATE
from server.enums import IntentLevel, UserSentiment, RiskLevel

logger = logging.getLogger(__name__)


# JSON Schema for Eyes output (inline, no get_schema function)
EYES_SCHEMA_NOT_USED = {
    "name": "eyes_output",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "observation": {
                "type": "string",
                "description": "Core situational analysis for Brain"
            },
            "thought_process": {
                "type": "string",
                "description": "Internal reasoning"
            },
            "situation_summary": {
                "type": "string",
                "description": "Brief summary of current state"
            },
            "intent_level": {
                "type": "string",
                "enum": ["low", "medium", "high", "very_high", "unknown"]
            },
            "user_sentiment": {
                "type": "string",
                "enum": ["neutral", "curious", "annoyed", "distrustful", "confused", "disappointed", "uninterested"]
            },
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
            "confidence": {
                "type": "number",
                "description": "Confidence 0.0-1.0"
            }
        },
        "required": [
            "observation", "thought_process", "situation_summary",
            "intent_level", "user_sentiment", "risk_flags", "confidence"
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
    return EYES_USER_TEMPLATE.format(
        rolling_summary=context.rolling_summary or "No summary yet",
        conversation_stage=context.conversation_stage.value,
        intent_level=context.intent_level.value,
        user_sentiment=context.user_sentiment.value,
        business_description=context.business_description,
        flow_prompt=context.flow_prompt,
        now_local=context.timing.now_local,
        whatsapp_window_open=context.timing.whatsapp_window_open,
        last_messages=_format_messages(context.last_messages),
    )


def _validate_and_build_output(data: dict) -> EyesOutput:
    """Validate and build typed output from raw JSON."""
    rf = data.get("risk_flags", {})
    risk_flags = RiskFlags(
        spam_risk=RiskLevel(rf.get("spam_risk", "low")),
        policy_risk=RiskLevel(rf.get("policy_risk", "low")),
        hallucination_risk=RiskLevel(rf.get("hallucination_risk", "low")),
    )
    
    return EyesOutput(
        observation=data.get("observation", ""),
        thought_process=data.get("thought_process", ""),
        situation_summary=data.get("situation_summary", ""),
        intent_level=IntentLevel(data.get("intent_level", "unknown")),
        user_sentiment=UserSentiment(data.get("user_sentiment", "neutral")),
        risk_flags=risk_flags,
        confidence=float(data.get("confidence", 0.5)),
    )


def run_eyes(context: PipelineInput) -> Tuple[EyesOutput, int, int]:
    """
    Run the Eyes step.
    Observes and analyzes conversation state.
    """
    user_prompt = _build_user_prompt(context)
    
    start_time = time.time()
    
    try:
        data = make_api_call(
            messages=[
                {"role": "system", "content": EYES_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_schema", "json_schema": EyesOutput.model_json_schema()},
            temperature=0.3,
            step_name="Eyes"
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        output = _validate_and_build_output(data)
        
        logger.info(f"Eyes: intent={output.intent_level.value}, sentiment={output.user_sentiment.value}")
        return output, latency_ms, 0
        
    except Exception as e:
        logger.error(f"Eyes failed: {e}")
        # Fallback: pass through input enums
        fallback_output = EyesOutput(
            observation="System error during observation. Falling back to safe state.",
            thought_process="Error fallback",
            situation_summary="Error",
            intent_level=context.intent_level,
            user_sentiment=context.user_sentiment,
            risk_flags=RiskFlags(),
            confidence=0.0,
        )
        return fallback_output, int((time.time() - start_time) * 1000), 0
