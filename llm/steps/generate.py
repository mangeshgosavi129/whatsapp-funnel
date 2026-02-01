"""
Step 3: GENERATE - Write the message to send.
"""
import json
import logging
import time
from typing import Tuple, Optional

from openai import OpenAI

from llm.config import llm_config
from llm.schemas import (
    PipelineInput, DecisionOutput, GenerateOutput,
    StatePatch, SelfCheck
)
from llm.prompts import GENERATE_SYSTEM_PROMPT, GENERATE_USER_TEMPLATE
from llm.utils import normalize_enum
from llm.api_helpers import llm_call_with_retry
from server.enums import ConversationStage, IntentLevel, UserSentiment, CTAType, DecisionAction

logger = logging.getLogger(__name__)


def _format_messages(messages: list) -> str:
    """Format messages for prompt."""
    if not messages:
        return "No messages yet"
    
    lines = []
    for msg in messages[-3:]:
        lines.append(f"[{msg.sender}] {msg.text}")
    return "\n".join(lines)


def _build_system_prompt(context: PipelineInput) -> str:
    """Build system prompt with constraints."""
    flow_guidance = context.flow_prompt if context.flow_prompt else "Follow standard sales conversation flow."
    return GENERATE_SYSTEM_PROMPT.format(
        max_words=context.max_words,
        questions_per_message=context.questions_per_message,
        language_pref=context.language_pref,
        flow_prompt=flow_guidance,
    )


def _build_user_prompt(context: PipelineInput, decision: DecisionOutput) -> str:
    """Build the user prompt with decision context."""
    decision_compact = {
        "action": decision.action.value,
        "why": decision.why,
        "stage": decision.next_stage.value,
        "cta": decision.recommended_cta.value if decision.recommended_cta else None,
    }
    
    return GENERATE_USER_TEMPLATE.format(
        business_name=context.business_name,
        business_description=context.business_description or "",
        rolling_summary=context.rolling_summary or "No summary yet",
        last_3_messages=_format_messages(context.last_3_messages),
        decision_json=json.dumps(decision_compact, separators=(",", ":")),
        conversation_stage=context.conversation_stage.value,
        intent_level=context.intent_level.value,
        user_sentiment=context.user_sentiment.value,
        whatsapp_window_open=context.timing.whatsapp_window_open,
    )


def _parse_response(content: str) -> dict:
    """Parse JSON from LLM response."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    return json.loads(content)


def _validate_and_build_output(data: dict, context: PipelineInput, decision: DecisionOutput) -> GenerateOutput:
    """Validate and build typed output from raw JSON."""
    # Map stage string to enum with fuzzy matching
    next_stage = normalize_enum(
        data.get("next_stage"),
        ConversationStage,
        decision.next_stage
    )
    
    # Map CTA type with fuzzy matching
    cta_type = normalize_enum(
        data.get("cta_type"),
        CTAType,
        None
    )
    
    # Build state patch with defensive enum parsing
    sp = data.get("state_patch", {})
    state_patch = StatePatch(
        intent_level=normalize_enum(sp.get("intent_level"), IntentLevel, None),
        user_sentiment=normalize_enum(sp.get("user_sentiment"), UserSentiment, None),
        conversation_stage=normalize_enum(sp.get("conversation_stage"), ConversationStage, None),
    )
    
    # Build self check
    sc = data.get("self_check", {})
    self_check = SelfCheck(
        guardrails_pass=sc.get("guardrails_pass", True),
        violations=sc.get("violations", []),
    )
    
    # If decision was not SEND_NOW, message should be empty
    message_text = data.get("message_text", "")
    if decision.action != DecisionAction.SEND_NOW:
        message_text = ""
    
    return GenerateOutput(
        message_text=message_text,
        message_language=data.get("message_language", context.language_pref),
        cta_type=cta_type,
        next_stage=next_stage,
        next_followup_in_minutes=max(0, data.get("next_followup_in_minutes", 0)),
        state_patch=state_patch,
        self_check=self_check,
    )


def run_generate(context: PipelineInput, decision: DecisionOutput) -> Tuple[Optional[GenerateOutput], int, int]:
    """
    Run the Generate step.
    
    Only runs if decision.action == SEND_NOW.
    
    Returns:
        Tuple of (GenerateOutput or None, latency_ms, tokens_used)
    """
    # Skip if not sending now
    if decision.action != DecisionAction.SEND_NOW:
        logger.info(f"Skipping generate: action={decision.action.value}")
        return None, 0, 0
    
    client = OpenAI(
        api_key=llm_config.api_key,
        base_url=llm_config.base_url,
    )
    
    system_prompt = _build_system_prompt(context)
    user_prompt = _build_user_prompt(context, decision)
    
    start_time = time.time()
    tokens_used = 0
    
    def make_api_call():
        return client.chat.completions.create(
            model=llm_config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},  # More reliable than strict schema
        )
    
    try:
        data = llm_call_with_retry(
            api_call=make_api_call,
            max_retries=2,
            step_name="Generate"
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        output = _validate_and_build_output(data, context, decision)
        
        # Check guardrails
        if not output.self_check.guardrails_pass:
            logger.warning(f"Guardrail violations: {output.self_check.violations}")
        
        logger.info(f"Generate step completed: {len(output.message_text)} chars, stage={output.next_stage.value}")
        
        return output, latency_ms, tokens_used
        
    except Exception as e:
        logger.error(f"Generate step failed: {e}", exc_info=True)
        return _get_fallback_output(context, decision), int((time.time() - start_time) * 1000), 0


def _get_fallback_output(context: PipelineInput, decision: DecisionOutput) -> GenerateOutput:
    """Return safe fallback output on error."""
    return GenerateOutput(
        message_text="",  # Don't send anything on error
        message_language=context.language_pref,
        cta_type=None,
        next_stage=decision.next_stage,
        next_followup_in_minutes=60,  # Try again in an hour
        state_patch=StatePatch(),
        self_check=SelfCheck(
            guardrails_pass=False,
            violations=["generation_failed"],
        ),
    )
