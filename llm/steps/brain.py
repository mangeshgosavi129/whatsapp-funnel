"""
Step 2: BRAIN - Strategist.
Makes decisions based on Eyes observation.
"""
import logging
import time
from typing import Tuple
from llm.api_helpers import make_api_call
from llm.schemas import PipelineInput, EyesOutput, BrainOutput
from llm.prompts import BRAIN_SYSTEM_PROMPT, BRAIN_USER_TEMPLATE
from llm.utils import normalize_enum, format_ctas
from server.enums import ConversationStage, DecisionAction

logger = logging.getLogger(__name__)


# JSON Schema for Brain output (inline)
BRAIN_SCHEMA_NOT_USED = {
    "name": "brain_output",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "implementation_plan": {
                "type": "string",
                "description": "Concise instruction for Mouth on what to say"
            },
            "action": {
                "type": "string",
                "enum": ["send_now", "wait_schedule", "initiate_cta"]
            },
            "new_stage": {
                "type": "string",
                "enum": ["greeting", "qualification", "pricing", "cta", "followup", "closed", "lost", "ghosted"]
            },
            "should_respond": {
                "type": "boolean"
            },
            "selected_cta_id": {
                "type": ["string", "null"]
            },
            "cta_scheduled_at": {
                "type": ["string", "null"]
            },
            "followup_in_minutes": {
                "type": "integer"
            },
            "followup_reason": {
                "type": "string"
            },
            "confidence": {
                "type": "number"
            },
            "needs_human_attention": {
                "type": "boolean"
            }
        },
        "required": [
            "implementation_plan", "action", "new_stage", "should_respond",
            "selected_cta_id", "cta_scheduled_at", "followup_in_minutes",
            "followup_reason", "confidence", "needs_human_attention"
        ],
        "additionalProperties": False
    }
}


def _build_user_prompt(context: PipelineInput, eyes_output: EyesOutput) -> str:
    """Build the user prompt with Eyes observation."""
    return BRAIN_USER_TEMPLATE.format(
        observation=eyes_output.observation,
        available_ctas=format_ctas(context.available_ctas),
        followup_count_24h=context.nudges.followup_count_24h,
        total_nudges=context.nudges.total_nudges,
        business_description=context.business_description,
        flow_prompt=context.flow_prompt,
        now_local=context.timing.now_local,
        whatsapp_window_open=context.timing.whatsapp_window_open,
    )


def _validate_and_build_output(data: dict, context: PipelineInput) -> BrainOutput:
    """Validate and build typed output from raw JSON."""
    # Stage transition logic
    llm_stage = normalize_enum(data.get("new_stage"), ConversationStage, context.conversation_stage)
    confidence = float(data.get("confidence", 0.5))
    
    # Prevent low-confidence stage jumps
    if confidence < 0.4 and llm_stage != context.conversation_stage:
        logger.warning(f"Low confidence stage jump blocked: {context.conversation_stage} -> {llm_stage}")
        llm_stage = context.conversation_stage
    
    action = normalize_enum(data.get("action"), DecisionAction, DecisionAction.WAIT_SCHEDULE)
    
    return BrainOutput(
        implementation_plan=data.get("implementation_plan", ""),
        action=action,
        new_stage=llm_stage,
        should_respond=data.get("should_respond", False),
        selected_cta_id=data.get("selected_cta_id"),
        cta_scheduled_at=data.get("cta_scheduled_at"),
        followup_in_minutes=max(0, data.get("followup_in_minutes", 0)),
        followup_reason=data.get("followup_reason", ""),
        confidence=confidence,
        needs_human_attention=bool(data.get("needs_human_attention", False)),
    )


def run_brain(context: PipelineInput, eyes_output: EyesOutput) -> Tuple[BrainOutput, int, int]:
    """
    Run the Brain step.
    Makes strategic decisions based on Eyes observation.
    """
    user_prompt = _build_user_prompt(context, eyes_output)
    
    start_time = time.time()
    
    try:
        data = make_api_call(
            messages=[
                {"role": "system", "content": BRAIN_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_schema", "json_schema": BrainOutput.model_json_schema()},
            temperature=0.3,
            step_name="Brain"
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        output = _validate_and_build_output(data, context)
        
        logger.info(f"Brain: {output.action.value} -> {output.new_stage.value} (Conf: {output.confidence})")
        if output.needs_human_attention:
            logger.info(f"Human attention flagged")
        
        return output, latency_ms, 0
        
    except Exception as e:
        logger.error(f"Brain failed: {e}")
        fallback_output = BrainOutput(
            implementation_plan="System error. Send a polite acknowledgment.",
            action=DecisionAction.WAIT_SCHEDULE,
            new_stage=context.conversation_stage,
            should_respond=False,
            confidence=0.0,
        )
        return fallback_output, int((time.time() - start_time) * 1000), 0
