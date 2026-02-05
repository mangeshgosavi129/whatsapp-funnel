"""
Step 2: MOUTH - Write the response.
"""
import json
import logging
import time
from typing import Tuple, Optional
from llm.schemas import PipelineInput, ClassifyOutput, GenerateOutput
from llm.prompts import MOUTH_USER_TEMPLATE
from llm.prompts_registry import get_mouth_system_prompt
from llm.api_helpers import make_api_call

logger = logging.getLogger(__name__)


def _format_messages(messages: list) -> str:
    """Format messages for prompt."""
    if not messages:
        return "No messages yet"
    
    lines = []
    for msg in messages[-3:]:
        lines.append(f"[{msg.sender}] {msg.text}")
    return "\n".join(lines)


def _build_user_prompt(context: PipelineInput, classification: ClassifyOutput) -> str:
    """Build the user prompt with Brain decision."""
    decision_compact = {
        "action": classification.action.value,
        "new_stage": classification.new_stage.value,
        "thought": classification.thought_process[:100], # Context for mouth
        "selected_cta_id": str(classification.selected_cta_id) if classification.selected_cta_id else None,
        "cta_scheduled_at": classification.cta_scheduled_at
    }
    
    return MOUTH_USER_TEMPLATE.format(
        business_name=context.business_name,
        rolling_summary=context.rolling_summary or "No summary yet",
        last_messages=_format_messages(context.last_3_messages),
        decision_json=json.dumps(decision_compact),
        conversation_stage=context.conversation_stage.value,
    )


def _validate_and_build_output(data: dict, context: PipelineInput) -> GenerateOutput:
    """Validate and build typed output from raw JSON."""
    
    return GenerateOutput(
        message_text=data.get("message_text", ""),
        message_language=data.get("message_language", context.language_pref),
        selected_cta_id=data.get("selected_cta_id"),
        next_followup_in_minutes=max(0, data.get("next_followup_in_minutes", 0)),
        self_check_passed=True, # Pro-forma for now
        violations=[]
    )

def run_mouth(context: PipelineInput, classification: ClassifyOutput) -> Tuple[Optional[GenerateOutput], int, int]:
    """
    Run the Mouth step.
    Only runs if classification.should_respond is True.
    """
    if not classification.should_respond:
        return None, 0, 0
    
    system_prompt = get_mouth_system_prompt(
        stage=classification.new_stage, # Use the NEW stage
        business_name=context.business_name,
        business_description=context.business_description,
        flow_prompt=context.flow_prompt,
        max_words=context.max_words
    )
    
    user_prompt = _build_user_prompt(context, classification)
    
    start_time = time.time()
    
    try:
        data = make_api_call(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            step_name="Mouth"
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        output = _validate_and_build_output(data, context)
        
        logger.info(f"Mouth: {len(output.message_text)} chars")
        return output, latency_ms, 0
        
    except Exception as e:
        logger.error(f"Mouth failed: {e}")
        # SIMPLE FALLBACK: Maintain continuity without crashing
        fallback_output = GenerateOutput(
            message_text="I'm sorry, I'm having a bit of trouble connecting. Could you please try again in a moment?",
            message_language="en"
        )
        return fallback_output, int((time.time() - start_time) * 1000), 0
