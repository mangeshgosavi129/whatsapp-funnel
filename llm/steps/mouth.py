"""
Step 3: MOUTH - Communicator.
Translates Brain's implementation plan into a message.
"""
import logging
import time
from typing import Tuple, Optional
from llm.api_helpers import make_api_call
from llm.schemas import PipelineInput, BrainOutput, MouthOutput
from llm.prompts import MOUTH_SYSTEM_PROMPT, MOUTH_USER_TEMPLATE
from llm.utils import format_ctas

logger = logging.getLogger(__name__)


# JSON Schema for Mouth output (inline)
MOUTH_SCHEMA = {
    "name": "mouth_output",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "message_text": {
                "type": "string",
                "description": "The message to send"
            },
            "message_language": {
                "type": "string",
                "description": "Language code"
            },
            "self_check_passed": {
                "type": "boolean"
            },
            "violations": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["message_text", "message_language", "self_check_passed", "violations"],
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


def _build_system_prompt(context: PipelineInput) -> str:
    """Build system prompt with business context."""
    return MOUTH_SYSTEM_PROMPT.format(
        business_name=context.business_name,
        business_description=context.business_description,
        max_words=context.max_words,
        questions_per_message=context.questions_per_message,
    )


def _build_user_prompt(context: PipelineInput, brain_output: BrainOutput) -> str:
    """Build the user prompt with Brain's implementation plan."""
    return MOUTH_USER_TEMPLATE.format(
        implementation_plan=brain_output.implementation_plan,
        business_name=context.business_name,
        available_ctas=format_ctas(context.available_ctas),
        last_messages=_format_messages(context.last_messages),
    )


def _validate_and_build_output(data: dict, context: PipelineInput) -> MouthOutput:
    """Validate and build typed output from raw JSON."""
    return MouthOutput(
        message_text=data.get("message_text") or "",
        message_language=data.get("message_language") or context.language_pref,
        self_check_passed=bool(data.get("self_check_passed", True)),
        violations=data.get("violations") or [],
    )


async def run_mouth(context: PipelineInput, brain_output: BrainOutput, tracer: Optional[object] = None) -> Tuple[Optional[MouthOutput], int, int]:
    """
    Run the Mouth step (Async).
    Only runs if brain_output.should_respond is True.
    """
    if not brain_output.should_respond:
        return None, 0, 0
    
    system_prompt = _build_system_prompt(context)
    user_prompt = _build_user_prompt(context, brain_output)
    
    start_time = time.time()
    
    try:
        data, usage = await make_api_call(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_schema", "json_schema": MOUTH_SCHEMA},
            step_name="Mouth",
            strict=True
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        output = _validate_and_build_output(data, context)
        
        # Log to Tracer
        if tracer:
            tracer.log_step(
                step_name="Mouth",
                input_data={"user_prompt_preview": user_prompt[:200]},
                output_data=data,
                latency_ms=latency_ms,
                model="llama3-70b-8192",
                token_usage=usage
            )

        logger.info(f"Mouth: {len(output.message_text)} chars")
        total_tokens = usage.get("prompt", 0) + usage.get("completion", 0)
        return output, latency_ms, total_tokens
        
    except Exception as e:
        logger.error(f"Mouth failed: {e}", exc_info=True)
        fallback_output = MouthOutput(
            message_text="I'm sorry, I'm having a bit of trouble connecting. Could you please try again in a moment?",
            message_language="en",
        )
        return fallback_output, int((time.time() - start_time) * 1000), 0
