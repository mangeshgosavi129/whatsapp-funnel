"""
LLM Configuration for HTL Pipeline.
Uses Groq for fast, cost-effective inference.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""
    api_key: str
    model: str
    base_url: str
    max_tokens: int
    temperature: float
    timeout: int
    
    # Cost optimization
    max_input_tokens: int  # Limit context size
    max_retries: int


def get_llm_config() -> LLMConfig:
    """
    Get LLM configuration from environment.
    Optimized for Groq's fast inference.
    """
    return LLMConfig(
        api_key=os.getenv("GROQ_API_KEY", ""),
        model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),  # Fast, capable model
        base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "500")),  # Keep responses concise
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),  # Low for consistency
        timeout=int(os.getenv("LLM_TIMEOUT", "30")),
        max_input_tokens=int(os.getenv("LLM_MAX_INPUT_TOKENS", "2000")),  # Limit context
        max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
    )


# Singleton config instance
_config: Optional[LLMConfig] = None


def get_config() -> LLMConfig:
    """Get cached config instance."""
    global _config
    if _config is None:
        _config = get_llm_config()
    return _config
