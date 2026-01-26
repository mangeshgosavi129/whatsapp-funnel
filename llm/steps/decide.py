"""
Step 2: DECIDE - Determine what action to take.
"""
import json
import logging
import time
from typing import Tuple

from openai import OpenAI

from llm.config import get_config
from llm.schemas import PipelineInput, AnalyzeOutput, DecisionOutput
from llm.prompts import DECISION_SYSTEM_PROMPT, DECISION_USER_TEMPLATE
from server.enums import ConversationStage, DecisionAction, CTAType

logger = logging.getLogger(__name__)


def _build_user_prompt(context: PipelineInput, analysis: AnalyzeOutput) -> str:
    """Build the user prompt with analysis results."""
    # Compact analysis JSON for token efficiency
    analysis_compact = {
        "summary": analysis.situation_summary,
        "goal": analysis.lead_goal_guess,
        "missing": analysis.missing_info,
        "objections": analysis.detected_objections,
        "stage_rec": analysis.stage_recommendation.value,
        "risks": {
            "spam": analysis.risk_flags.spam_risk.value,
            "policy": analysis.risk_flags.policy_risk.value,
        },
        "kb_needed": analysis.need_kb.required,
        "confidence": analysis.confidence,
    }
    
    return DECISION_USER_TEMPLATE.format(
        analysis_json=json.dumps(analysis_compact, separators=(",", ":")),
        conversation_stage=context.conversation_stage.value,
        conversation_mode=context.conversation_mode,
        intent_level=context.intent_level.value,
        user_sentiment=context.user_sentiment.value,
        now_local=context.timing.now_local,
        last_user_at=context.timing.last_user_message_at or "unknown",
        whatsapp_window_open=context.timing.whatsapp_window_open,
        followup_count_24h=context.nudges.followup_count_24h,
        total_nudges=context.nudges.total_nudges,
    )


def _parse_response(content: str) -> dict:
    """Parse JSON from LLM response."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    return json.loads(content)


def _validate_and_build_output(data: dict, context: PipelineInput) -> DecisionOutput:
    """Validate and build typed output from raw JSON."""
    # Map action string to enum
    action_str = data.get("action", "WAIT_SCHEDULE").upper()
    try:
        action = DecisionAction(action_str.lower())
    except ValueError:
        action = DecisionAction.WAIT_SCHEDULE
    
    # Map stage string to enum
    stage_str = data.get("next_stage", context.conversation_stage.value)
    try:
        next_stage = ConversationStage(stage_str)
    except ValueError:
        next_stage = context.conversation_stage
    
    # Map CTA type
    cta_str = data.get("recommended_cta")
    recommended_cta = None
    if cta_str and cta_str != "null":
        try:
            recommended_cta = CTAType(cta_str)
        except ValueError:
            pass
    
    # Parse CTA scheduling fields
    cta_scheduled_time = data.get("cta_scheduled_time")
    if cta_scheduled_time == "null" or cta_scheduled_time == "":
        cta_scheduled_time = None
    
    cta_name = data.get("cta_name")
    if cta_name == "null" or cta_name == "":
        cta_name = None
    
    # Ensure followup_in_minutes is reasonable
    followup = data.get("followup_in_minutes", 0)
    if action == DecisionAction.SEND_NOW:
        followup = 0  # No wait for immediate send
    elif action == DecisionAction.WAIT_SCHEDULE and followup <= 0:
        followup = 120  # Default 2 hours if not specified
    
    # If action is INITIATE_CTA but no recommended_cta, default to book_call
    if action == DecisionAction.INITIATE_CTA and recommended_cta is None:
        recommended_cta = CTAType.BOOK_CALL
    
    return DecisionOutput(
        action=action,
        why=data.get("why", "Decision made")[:150],
        next_stage=next_stage,
        recommended_cta=recommended_cta,
        cta_scheduled_time=cta_scheduled_time,
        cta_name=cta_name,
        followup_in_minutes=max(0, followup),
        followup_reason=data.get("followup_reason", "")[:100],
        kb_used=data.get("kb_used", False),
        template_required=data.get("template_required", False),
    )


def run_decision(context: PipelineInput, analysis: AnalyzeOutput) -> Tuple[DecisionOutput, int, int]:
    """
    Run the Decision step.
    
    Returns:
        Tuple of (DecisionOutput, latency_ms, tokens_used)
    """
    config = get_config()
    client = OpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
    )
    
    # Check if mode is human - must escalate
    if context.conversation_mode == "human":
        return DecisionOutput(
            action=DecisionAction.HANDOFF_HUMAN,
            why="Mode is already human, maintaining handoff",
            next_stage=context.conversation_stage,
            recommended_cta=None,
            followup_in_minutes=0,
            followup_reason="",
            kb_used=False,
            template_required=False,
        ), 0, 0
    
    user_prompt = _build_user_prompt(context, analysis)
    
    start_time = time.time()
    
    try:
        response = client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": DECISION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            # Removed config params per user request
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        tokens_used = response.usage.total_tokens if response.usage else 0
        
        content = response.choices[0].message.content
        data = _parse_response(content)
        output = _validate_and_build_output(data, context)
        
        logger.info(f"Decision step completed: action={output.action.value}, stage={output.next_stage.value}")
        
        return output, latency_ms, tokens_used
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Decision response: {e}")
        return _get_fallback_output(context, analysis), int((time.time() - start_time) * 1000), 0
        
    except Exception as e:
        logger.error(f"Decision step failed: {e}", exc_info=True)
        return _get_fallback_output(context, analysis), int((time.time() - start_time) * 1000), 0


def _get_fallback_output(context: PipelineInput, analysis: AnalyzeOutput) -> DecisionOutput:
    """Return safe fallback output on error."""
    # If high risk, escalate to human
    if (analysis.risk_flags.spam_risk.value == "high" or 
        analysis.risk_flags.policy_risk.value == "high" or
        analysis.confidence < 0.3):
        return DecisionOutput(
            action=DecisionAction.HANDOFF_HUMAN,
            why="Escalating due to uncertainty or high risk",
            next_stage=context.conversation_stage,
            recommended_cta=None,
            followup_in_minutes=0,
            followup_reason="",
            kb_used=False,
            template_required=False,
        )
    
    # Default: wait and schedule followup
    return DecisionOutput(
        action=DecisionAction.WAIT_SCHEDULE,
        why="Defaulting to wait due to processing error",
        next_stage=context.conversation_stage,
        recommended_cta=None,
        followup_in_minutes=120,
        followup_reason="System fallback",
        kb_used=False,
        template_required=False,
    )
