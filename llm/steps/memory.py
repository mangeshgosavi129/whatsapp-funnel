"""
Step 3: MEMORY - Background Process.
Updates the rolling summary.
"""

import logging
import time
from typing import Tuple, Optional
from llm.schemas import PipelineInput, SummaryOutput, ClassifyOutput
from llm.prompts import MEMORY_SYSTEM_PROMPT, MEMORY_USER_TEMPLATE
from llm.api_helpers import make_api_call

logger = logging.getLogger(__name__)


def run_memory(
    context: PipelineInput,
    user_message: str,
    bot_message: str,
    classification: ClassifyOutput
) -> Optional[str]:
    """
    Run the Memory step in "background".
    Returns the new summary string so the worker can save it.
    """
    try:
        # 1. Run LLM
        output, latency, tokens = _run_memory_llm(context, user_message, bot_message, classification)
        return output.updated_rolling_summary
        
    except Exception as e:
        logger.error(f"Memory failed: {e}")
        return context.rolling_summary or "No summary available"


def _run_memory_llm(
    context: PipelineInput,
    user_message: str,
    bot_message: str,
    classification: ClassifyOutput
) -> Tuple[SummaryOutput, int, int]:
    """Core LLM Logic"""
    user_prompt = MEMORY_USER_TEMPLATE.format(
        rolling_summary=context.rolling_summary or "No prior summary",
        user_message=user_message,
        bot_message=bot_message or "(No response sent)",
    )
    
    start_time = time.time()

    data = make_api_call(
        messages=[
            {"role": "system", "content": MEMORY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        max_tokens=1000,
        step_name="Memory"
    )
    
    summary_text = data.get("updated_rolling_summary", "")[:500]
    
    # Save to Schema
    output = SummaryOutput(
        updated_rolling_summary=summary_text,
        needs_recursive_summary=False
    )
    
    return output, int((time.time() - start_time) * 1000), 0
