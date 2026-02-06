import json
import re
import logging
from typing import Dict, Any, Optional, List

from openai import OpenAI, BadRequestError
from llm.config import llm_config

logger = logging.getLogger(__name__)
logging.getLogger("llm").disabled = True
logging.getLogger("llm.api_helpers").disabled = True

# Initialize single OpenAI client
client = OpenAI(
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

def make_api_call(
    messages: List[Dict[str, str]],
    response_format: Optional[Dict[str, Any]] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    step_name: str = "LLM"
) -> Dict[str, Any]:
    """
    Execute LLM API call without retries.
    
    Returns:
        Parsed JSON response dict
    """
    try:
        kwargs = {
            "model": llm_config.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        response = client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content

        # Try direct JSON parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try extraction from text
            extracted = extract_json_from_text(content)
            if extracted:
                print(f"{step_name}: Extracted JSON from text response")
                logger.info(f"{step_name}: Extracted JSON from text response")
                return extracted
            raise ValueError(f"{step_name}: Could not parse JSON from response: {content[:100]}...")
            
    except BadRequestError as e:
        # Check if this is a JSON validation failure with a partial result
        try:
            error_data = e.response.json()
            error_details = error_data.get("error", {})
            if error_details.get("code") == "json_validate_failed":
                failed_gen = error_details.get("failed_generation")
                if failed_gen:
                    print(f"[LLM ERROR] {step_name}: JSON validation failed, using failed_generation")
                    logger.error(f"{step_name} JSON validation failed: {error_details.get('message')}")
                    
                    # failed_gen is expected to be a JSON string, but if it's already a dict, return it
                    if isinstance(failed_gen, dict):
                        return failed_gen
                    
                    try:
                        parsed = json.loads(failed_gen)
                        return parsed
                    except json.JSONDecodeError:
                        # If it's not valid JSON, try our extractor
                        extracted = extract_json_from_text(failed_gen)
                        if extracted:
                            return extracted
                        # If all fails, re-raise original error
                        raise e
        except Exception as inner_e:
            logger.error(f"Error while parsing BadRequestError: {inner_e}")
            
        print(f"[LLM ERROR] {step_name}: {e}")
        logger.error(f"{step_name} API call failed: {e}")
        raise
    except Exception as e:
        print(f"[LLM ERROR] {step_name}: {e}")
        logger.error(f"{step_name} API call failed: {e}")
        raise

