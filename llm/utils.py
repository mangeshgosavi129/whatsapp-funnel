"""
LLM Utilities for Pipeline.
Provides enum normalization and prompt formatting.
"""
import logging
from typing import Type, TypeVar, Optional
from enum import Enum
from rapidfuzz import process, fuzz

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Enum)


# ============================================================
# Enum Normalization (Fuzzy Matching Fallback)
# ============================================================

# Explicit aliases for common LLM variations
ENUM_ALIASES = {
    # ConversationStage
    "qualifying": "qualification",
    "qualified": "qualification",
    "qualify": "qualification",
    "greet": "greeting",
    "price": "pricing",
    "close": "closed",
    "ghost": "ghosted",
    # DecisionAction
    "send": "send_now",
    "wait": "wait_schedule",
    "schedule": "wait_schedule",
    "handoff": "flag_attention",
    "escalate": "flag_attention",
    "handoff_human": "flag_attention",
    # IntentLevel
    "very-high": "very_high",
    "veryhigh": "very_high",
    # UserSentiment
    "positive": "curious",
    "negative": "annoyed",
    "frustrated": "annoyed",
}


def normalize_enum(
    value: Optional[str],
    enum_class: Type[T],
    default: Optional[T] = None,
    log_corrections: bool = True
) -> Optional[T]:
    """
    Safely convert a string to an enum with fuzzy matching (using rapidfuzz).
    
    Handles cases like:
    - "qualifying" -> ConversationStage.QUALIFICATION
    - "Greeting" -> ConversationStage.GREETING  
    - "send_now" or "SEND_NOW" -> DecisionAction.SEND_NOW
    """
    if value is None or value == "null" or value == "":
        return default
    
    # Normalize input
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    
    # Check explicit aliases first
    if normalized in ENUM_ALIASES:
        normalized = ENUM_ALIASES[normalized]
    
    # Get all valid enum values
    valid_values = {e.value.lower(): e for e in enum_class}
    
    # Direct match
    if normalized in valid_values:
        return valid_values[normalized]
    
    # Try fuzzy matching with rapidfuzz
    # score_cutoff=60 is roughly equivalent to difflib cutoff=0.6
    match = process.extractOne(
        normalized, 
        valid_values.keys(), 
        scorer=fuzz.WRatio, 
        score_cutoff=60
    )
    
    if match:
        matched_value, score, _ = match
        result = valid_values[matched_value]
        
        if log_corrections:
            logger.warning(
                f"Enum correction: '{value}' → '{result.value}' "
                f"(score={score:.1f}, class={enum_class.__name__})"
            )
        return result
    
    # No match found
    if log_corrections:
        logger.warning(
            f"Enum fallback: '{value}' not valid for {enum_class.__name__}, "
            f"using default={default.value if default else None}"
        )
    return default


# ============================================================
# Prompt Formatting Utilities
# ============================================================

def format_ctas(ctas: list) -> str:
    """Format available CTAs for prompt."""
    if not ctas:
        return "No CTAs defined in dashboard."
    
    lines = []
    for cta in ctas:
        lines.append(f"- ID: {cta.get('id')} | Name: {cta.get('name')}")
    return "\n".join(lines)
