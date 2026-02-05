"""
Step 1: CLASSIFY (The Brain) - Analyze and Decide in one step.
"""
import logging
import time
from typing import Tuple
from llm.api_helpers import make_api_call
from llm.schemas import PipelineInput, ClassifyOutput, RiskFlags
from llm.prompts import CLASSIFY_USER_TEMPLATE, HISTORY_SECTION_TEMPLATE
from llm.prompts_registry import get_classify_system_prompt
from llm.utils import normalize_enum, get_classify_schema
from server.enums import (
    ConversationStage, DecisionAction, IntentLevel, 
    UserSentiment, RiskLevel
)

logger = logging.getLogger(__name__)


def _format_messages(messages: list) -> str:
    """Format messages for prompt."""
    if not messages:
        return "No messages yet"
    
    lines = []
    for msg in messages[-3:]:
        lines.append(f"[{msg.sender}] {msg.text}")
    return "\n".join(lines)


def _format_ctas(ctas: list) -> str:
    """Format available CTAs for prompt."""
    if not ctas:
        return "No CTAs defined in dashboard."
    
    lines = []
    for cta in ctas:
        lines.append(f"- ID: {cta.get('id')} | Name: {cta.get('name')}")
    return "\n".join(lines)


def _is_opening_message(context: PipelineInput) -> bool:
    """
    Check if this is an opening message (no relevant history).
    History is considered empty if last_3_messages has 0 or 1 message.
    """
    # If the list is empty or only contains the current message (if already added)
    # in some flows, the message is added to history before pipeline runs.
    # We check if context.rolling_summary is empty as a strong signal.
    return not context.last_3_messages or (len(context.last_3_messages) <= 1 and not context.rolling_summary)


def _build_user_prompt(context: PipelineInput, is_opening: bool) -> str:
    """Build the user prompt with context."""
    
    # 1. Format History Section (Only for replies)
    history_section = ""
    if not is_opening:
        history_section = HISTORY_SECTION_TEMPLATE.format(
            rolling_summary=context.rolling_summary or "No summary yet",
            last_3_messages=_format_messages(context.last_3_messages)
        )
    
    # 2. Build Full Prompt (Note: Business context removed per Brain-Mouth logic separation)
    return CLASSIFY_USER_TEMPLATE.format(
        history_section=history_section,
        available_ctas=_format_ctas(context.available_ctas),
        conversation_stage=context.conversation_stage.value,
        conversation_mode=context.conversation_mode,
        intent_level=context.intent_level.value,
        user_sentiment=context.user_sentiment.value,
        active_cta_id=context.active_cta_id or "None",
        now_local=context.timing.now_local,
        whatsapp_window_open=context.timing.whatsapp_window_open,
        followup_count_24h=context.nudges.followup_count_24h,
    )


def _validate_and_build_output(data: dict, context: PipelineInput) -> ClassifyOutput:
    """Validate and build typed output from raw JSON."""
    
    # 1. New Stage Logic (Stickiness)
    # Default to current if missing or invalid
    llm_stage = normalize_enum(data.get("new_stage"), ConversationStage, context.conversation_stage)
    
    # Prevent aggression/random jumps unless high confidence
    confidence = float(data.get("confidence", 0.5))
    if confidence < 0.7 and llm_stage != context.conversation_stage:
        logger.warning(f"Low confidence stage jump ({context.conversation_stage} -> {llm_stage}). Holding pos.")
        llm_stage = context.conversation_stage

    # 2. Risk Flags
    rf = data.get("risk_flags", {})
    risk_flags = RiskFlags(
        spam_risk=RiskLevel(rf.get("spam_risk", "low")),
        policy_risk=RiskLevel(rf.get("policy_risk", "low")),
        hallucination_risk=RiskLevel(rf.get("hallucination_risk", "low")),
    )
    
    # 3. Action Logic
    action = normalize_enum(data.get("action"), DecisionAction, DecisionAction.WAIT_SCHEDULE)
    
    result = ClassifyOutput(
        thought_process=data.get("thought_process", "No thought provided")[:300],
        situation_summary=data.get("situation_summary", "")[:200],
        intent_level=normalize_enum(data.get("intent_level"), IntentLevel, IntentLevel.UNKNOWN),
        user_sentiment=normalize_enum(data.get("user_sentiment"), UserSentiment, UserSentiment.NEUTRAL),
        risk_flags=risk_flags,
        
        action=action,
        new_stage=llm_stage,
        should_respond=data.get("should_respond", False),
        
        selected_cta_id=data.get("selected_cta_id"),
        cta_scheduled_at=data.get("cta_scheduled_at"),
        followup_in_minutes=max(0, data.get("followup_in_minutes", 0)),
        followup_reason=data.get("followup_reason", ""),
        
        confidence=confidence,
        needs_human_attention=bool(data.get("needs_human_attention", False))
    )
    # DEBUG: Log raw needs_human_attention value
    print(f"[DEBUG] Raw LLM needs_human_attention: {data.get('needs_human_attention', 'NOT_IN_OUTPUT')}")
    return result


def run_classify(context: PipelineInput) -> Tuple[ClassifyOutput, int, int]:
    """
    Run the Classify step (The Brain).
    """
    is_opening = _is_opening_message(context)
    user_prompt = _build_user_prompt(context, is_opening)
    system_prompt = get_classify_system_prompt(
        context.conversation_stage, 
        is_opening, 
        flow_prompt=context.flow_prompt
    )
    
    start_time = time.time()
    
    try:
        data = make_api_call(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_schema", "json_schema": get_classify_schema()},
            temperature=0.3,
            step_name="Classify"
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        output = _validate_and_build_output(data, context)
        
        logger.info(f"Classify: {output.action.value} -> {output.new_stage.value} (Conf: {output.confidence})")
        if output.needs_human_attention:
            print(f"🚨 [DEBUG] needs_human_attention=True detected!")
            logger.info(f"🚨 Human attention flagged for conversation")
        
        return output, latency_ms, 0 
        
    except Exception as e:
        logger.error(f"Classify failed: {e}")
        fallback_output = ClassifyOutput(
            thought_process="System error during classification. Falling back to safe state.",
            situation_summary="Error",
            intent_level=IntentLevel.UNKNOWN,
            user_sentiment=UserSentiment.NEUTRAL,
            risk_flags=RiskFlags(),
            action=DecisionAction.WAIT_SCHEDULE,
            new_stage=context.conversation_stage,
            should_respond=False,
            confidence=0.0
        )
        return fallback_output, int((time.time() - start_time) * 1000), 0
