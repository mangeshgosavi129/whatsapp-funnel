"""
Step 4: SUMMARIZE - Update the rolling summary.
"""
import json
import logging
import time
from typing import Tuple

from openai import OpenAI

from llm.config import get_config
from llm.schemas import PipelineInput, SummaryOutput, GenerateOutput
from llm.prompts import SUMMARIZE_SYSTEM_PROMPT, SUMMARIZE_USER_TEMPLATE
from server.enums import ConversationStage

logger = logging.getLogger(__name__)


def _build_user_prompt(
    context: PipelineInput,
    user_message: str,
    bot_message: str,
    new_stage: ConversationStage,
    new_intent: str,
    new_sentiment: str,
) -> str:
    """Build the user prompt for summary update."""
    return SUMMARIZE_USER_TEMPLATE.format(
        rolling_summary=context.rolling_summary or "No prior summary",
        user_message=user_message,
        bot_message=bot_message or "(No response sent)",
        conversation_stage=new_stage.value,
        intent_level=new_intent,
        user_sentiment=new_sentiment,
    )


def _parse_response(content: str) -> dict:
    """Parse JSON from LLM response."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    return json.loads(content)


def run_summarize(
    context: PipelineInput,
    user_message: str,
    bot_message: str,
    response_output: GenerateOutput = None,
) -> Tuple[SummaryOutput, int, int]:
    """
    Run the Summarize step.
    
    Always runs, even if no message was sent.
    
    Returns:
        Tuple of (SummaryOutput, latency_ms, tokens_used)
    """
    config = get_config()
    client = OpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.timeout,
    )
    
    # Get updated state from response output if available
    if response_output and response_output.state_patch:
        new_stage = response_output.state_patch.conversation_stage or context.conversation_stage
        new_intent = response_output.state_patch.intent_level.value if response_output.state_patch.intent_level else context.intent_level.value
        new_sentiment = response_output.state_patch.user_sentiment.value if response_output.state_patch.user_sentiment else context.user_sentiment.value
    else:
        new_stage = context.conversation_stage
        new_intent = context.intent_level.value
        new_sentiment = context.user_sentiment.value
    
    user_prompt = _build_user_prompt(
        context, user_message, bot_message, new_stage, new_intent, new_sentiment
    )
    
    start_time = time.time()
    
    try:
        response = client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=300,  # Summaries are short
            temperature=0.2,  # Very consistent
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        tokens_used = response.usage.total_tokens if response.usage else 0
        
        content = response.choices[0].message.content
        data = _parse_response(content)
        
        summary = data.get("updated_rolling_summary", "")[:500]  # Hard limit
        
        output = SummaryOutput(updated_rolling_summary=summary)
        
        logger.info(f"Summarize step completed: {len(summary)} chars")
        
        return output, latency_ms, tokens_used
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Summarize response: {e}")
        return _get_fallback_output(context, user_message, bot_message), int((time.time() - start_time) * 1000), 0
        
    except Exception as e:
        logger.error(f"Summarize step failed: {e}", exc_info=True)
        return _get_fallback_output(context, user_message, bot_message), int((time.time() - start_time) * 1000), 0


def _get_fallback_output(context: PipelineInput, user_message: str, bot_message: str) -> SummaryOutput:
    """Return simple fallback summary on error."""
    # Just append to existing summary
    existing = context.rolling_summary or ""
    new_exchange = f"\nUser: {user_message[:100]}"
    if bot_message:
        new_exchange += f"\nBot: {bot_message[:100]}"
    
    # Truncate if too long
    combined = existing + new_exchange
    if len(combined) > 500:
        combined = combined[-500:]  # Keep most recent
    
    return SummaryOutput(updated_rolling_summary=combined)
