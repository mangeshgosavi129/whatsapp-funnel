import json
import re
import logging
from typing import Dict, Any, Optional, List, Tuple

from openai import AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from llm.config import llm_config

logger = logging.getLogger(__name__)
# Keep these disabled to reduce noise
logging.getLogger("llm").disabled = True
logging.getLogger("llm.api_helpers").disabled = True

# Initialize Async Client
client = AsyncOpenAI(
    api_key=llm_config.api_key,
    base_url=llm_config.base_url,
)

def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON object from text that may contain thinking/reasoning before JSON.
    """
    if not text:
        return None
    
    text = text.strip()
    
    # If it's already valid JSON, parse it directly
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON object in the text
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # Try markdown code block extraction
    code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass
    
    return None

@retry(
    retry=retry_if_exception_type((RateLimitError, APIConnectionError, APIStatusError)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
async def make_api_call(
    messages: List[Dict[str, str]],
    response_format: Optional[Dict[str, Any]] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    step_name: str = "LLM",
    strict: bool = False
) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """
    Execute LLM API call with retries and async support.
    
    Args:
        messages: List of message dicts
        response_format: JSON schema for output
        temperature: Sampling temperature
        max_tokens: Max tokens to generate
        step_name: Name of step for logging
        strict: If True, enforces strict JSON schema adherence (Groq specific)
    
    Returns:
        Tuple[Dict, Dict]: (Parsed JSON response dict, Token usage dict)
    """
    # Debug flag (can be moved to config or env)
    DEBUG_PROMPTS = True

    try:
        if DEBUG_PROMPTS:
            print(f"\n{'='*60}")
            print(f"[{step_name}] REQUEST (Async)")
            print(f"{'='*60}")
            for msg in messages:
                print(f"--- {msg['role'].upper()} ---")
                print(msg['content'])
            print(f"{'='*60}\n")

        kwargs = {
            "model": llm_config.model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if response_format:
            # GROQ SPECIFIC: Enable key ordering and strict mode if requested
            if strict:
                 if "json_schema" in response_format:
                     response_format["json_schema"]["strict"] = True
            
            kwargs["response_format"] = response_format
            
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        # Async API Call
        response = await client.chat.completions.create(**kwargs)
        
        content = response.choices[0].message.content
        usage = response.usage
        
        usage_dict = {
            "prompt": usage.prompt_tokens if usage else 0,
            "completion": usage.completion_tokens if usage else 0
        }

        if DEBUG_PROMPTS:
            print(f"\n{'='*60}")
            print(f"[{step_name}] RESPONSE")
            print(f"{'='*60}")
            print(content)
            print(f"{'='*60}\n")
        
        # Parse JSON
        parsed_data = None
        
        # If strict mode, trust JSON
        if strict:
            parsed_data = json.loads(content)
        else:
            try:
                parsed_data = json.loads(content)
            except json.JSONDecodeError:
                parsed_data = extract_json_from_text(content)
                if parsed_data:
                    logger.warning(f"{step_name}: Invalid JSON, but extracted from text.")
                else:
                     raise ValueError(f"{step_name}: Could not parse JSON: {content[:100]}...")

        return parsed_data, usage_dict
            
    except Exception as e:
        logger.error(f"{step_name} API call failed: {e}")
        # Tenacity will handle retries for specific exceptions.
        # Other exceptions will propagate.
        raise
