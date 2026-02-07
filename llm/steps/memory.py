"""
Step 4: MEMORY - Archivist.
Updates the rolling summary after Mouth responds.
"""
import logging
import time
from typing import Tuple, Optional
from llm.schemas import PipelineInput, BrainOutput, MouthOutput, MemoryOutput
from llm.api_helpers import make_api_call
from llm.prompts import MEMORY_SYSTEM_PROMPT, MEMORY_USER_TEMPLATE

logger = logging.getLogger(__name__)


# JSON Schema for Memory output (inline)
MEMORY_SCHEMA = {
    "name": "memory_output",
    "strict": False,
    "schema": {
        "type": "object",
        "properties": {
            "updated_rolling_summary": {
                "type": "string",
                "description": "Updated summary (80-200 words)"
            },
            "needs_recursive_summary": {
                "type": "boolean"
            }
        },
        "required": ["updated_rolling_summary", "needs_recursive_summary"],
        "additionalProperties": False
    }
}


async def run_memory(
    context: PipelineInput,
    user_message: str,
    mouth_output: Optional[MouthOutput],
    brain_output: BrainOutput,
    tracer: Optional[object] = None
) -> Optional[str]:
    """
    Run the Memory step (Async).
    Returns the new summary string so the worker can save it.
    Runs AFTER Mouth output is available.
    """
    try:
        data, usage_dict, latency = await _run_memory_llm(
            context, user_message, mouth_output, brain_output
        )

        output = MemoryOutput(
            updated_rolling_summary=data.get("updated_rolling_summary", ""),
            needs_recursive_summary=data.get("needs_recursive_summary", False),
        )

        if tracer:
            tracer.log_step(
                step_name="Memory",
                input_data={"user_message": user_message[:50]},
                output_data=data,
                latency_ms=latency,
                model="llama3-70b-8192",
                token_usage=usage_dict
            )

        logger.info(f"Memory: {len(output.updated_rolling_summary)} chars")
        return output.updated_rolling_summary
        
    except Exception as e:
        logger.error(f"Memory failed: {e}", exc_info=True)
        return context.rolling_summary or "No summary available"


async def _run_memory_llm(
    context: PipelineInput,
    user_message: str,
    mouth_output: Optional[MouthOutput],
    brain_output: BrainOutput
) -> Tuple[dict, dict, int]:
    """Core LLM Logic."""
    bot_message = mouth_output.message_text if mouth_output else "(No response sent)"
    action_taken = f"Action: {brain_output.action.value}, Stage: {brain_output.new_stage.value}"
    
    user_prompt = MEMORY_USER_TEMPLATE.format(
        rolling_summary=context.rolling_summary or "No prior summary",
        user_message=user_message,
        bot_message=bot_message,
        action_taken=action_taken,
    )
    
    start_time = time.time()

    data, usage = await make_api_call(
        messages=[
            {"role": "system", "content": MEMORY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_schema", "json_schema": MEMORY_SCHEMA},
        max_tokens=2000,
        step_name="Memory",
        strict=False
    )
    
    latency = int((time.time() - start_time) * 1000)
    return data, usage, latency
