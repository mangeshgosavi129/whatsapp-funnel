"""
LLM Utilities for HTL Pipeline.
Provides enum normalization, JSON schema generation, and defensive parsing.
"""
import logging
from typing import Type, TypeVar, Optional, Dict, Any, List
from enum import Enum
from difflib import get_close_matches

from server.enums import (
    ConversationStage,
    IntentLevel,
    UserSentiment,
    CTAType,
    DecisionAction,
    RiskLevel,
)

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
    "followups": "followup",
    "follow_up": "followup",
    "follow-up": "followup",
    "ghost": "ghosted",
    # DecisionAction
    "send": "send_now",
    "wait": "wait_schedule",
    "schedule": "wait_schedule",
    "handoff": "flag_attention",
    "escalate": "flag_attention",
    "handoff_human": "flag_attention",
    "cta": "initiate_cta",
    # IntentLevel
    "very-high": "very_high",
    "veryhigh": "very_high",
    # UserSentiment
    "positive": "curious",  # Map to closest
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
    Safely convert a string to an enum with fuzzy matching.
    
    Handles cases like:
    - "qualifying" -> ConversationStage.QUALIFICATION
    - "Greeting" -> ConversationStage.GREETING  
    - "send_now" or "SEND_NOW" -> DecisionAction.SEND_NOW
    
    Args:
        value: String value to convert
        enum_class: Target enum class
        default: Default value if conversion fails
        log_corrections: Whether to log when corrections are made
        
    Returns:
        Enum value or default
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
    
    # Try fuzzy matching with lower cutoff
    close_matches = get_close_matches(normalized, valid_values.keys(), n=1, cutoff=0.6)
    
    if close_matches:
        matched_value = close_matches[0]
        result = valid_values[matched_value]
        
        if log_corrections:
            logger.warning(
                f"Enum correction: '{value}' → '{result.value}' "
                f"(class={enum_class.__name__})"
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
# JSON Schema Definitions for Groq Structured Output
# ============================================================

def get_classify_schema() -> Dict[str, Any]:
    """JSON Schema for Classify (Brain) step output with strict enforcement."""
    return {
        "name": "classify_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "thought_process": {
                    "type": "string",
                    "description": "Analysis of the situation and reasoning"
                },
                "situation_summary": {
                    "type": "string",
                    "description": "Brief summary of current conversation state"
                },
                "intent_level": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "very_high", "unknown"],
                    "description": "User's intent level"
                },
                "user_sentiment": {
                    "type": "string",
                    "enum": ["neutral", "curious", "happy", "annoyed", "distrustful", "confused", "disappointed", "uninterested"],
                    "description": "User's sentiment"
                },
                "risk_flags": {
                    "type": "object",
                    "properties": {
                        "spam_risk": {"type": "string", "enum": ["low", "medium", "high"]},
                        "policy_risk": {"type": "string", "enum": ["low", "medium", "high"]},
                        "hallucination_risk": {"type": "string", "enum": ["low", "medium", "high"]}
                    },
                    "required": ["spam_risk", "policy_risk", "hallucination_risk"],
                    "additionalProperties": False
                },
                "action": {
                    "type": "string",
                    "enum": ["send_now", "wait_schedule", "initiate_cta"],
                    "description": "Action to take"
                },
                "new_stage": {
                    "type": "string",
                    "enum": ["greeting", "qualification", "pricing", "cta", "followup", "closed", "lost", "ghosted"],
                    "description": "Next conversation stage"
                },
                "should_respond": {
                    "type": "boolean",
                    "description": "Whether to send a response"
                },
                "needs_human_attention": {
                    "type": "boolean",
                    "description": "Set to true if user explicitly asks for human or query is too complex"
                },
                "recommended_cta": {
                    "type": ["string", "null"],
                    "enum": ["book_call", "book_demo", "book_meeting", None],
                    "description": "CTA type if applicable"
                },
                "followup_in_minutes": {
                    "type": "integer",
                    "description": "Minutes until followup"
                },
                "followup_reason": {
                    "type": "string",
                    "description": "Reason for followup timing"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score 0.0-1.0"
                }
            },
            "required": [
                "thought_process", "situation_summary", "intent_level", "user_sentiment",
                "risk_flags", "action", "new_stage", "should_respond", "needs_human_attention",
                "recommended_cta", "followup_in_minutes", "followup_reason", "confidence"
            ],
            "additionalProperties": False
        }
    }


def get_analyze_schema() -> Dict[str, Any]:
    """JSON Schema for Analyze step output."""
    return {
        "name": "analyze_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "situation_summary": {
                    "type": "string",
                    "description": "1-2 line summary of the current situation"
                },
                "lead_goal_guess": {
                    "type": "string",
                    "description": "Best guess of what the lead wants"
                },
                "missing_info": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Information needed to progress the sale"
                },
                "detected_objections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Objections detected in the conversation"
                },
                "stage_recommendation": {
                    "type": "string",
                    "enum": ["greeting", "qualification", "pricing", "cta", "followup", "closed", "lost", "ghosted"],
                    "description": "Recommended conversation stage"
                },
                "risk_flags": {
                    "type": "object",
                    "properties": {
                        "spam_risk": {"type": "string", "enum": ["low", "medium", "high"]},
                        "policy_risk": {"type": "string", "enum": ["low", "medium", "high"]},
                        "hallucination_risk": {"type": "string", "enum": ["low", "medium", "high"]}
                    },
                    "required": ["spam_risk", "policy_risk", "hallucination_risk"],
                    "additionalProperties": False
                },
                "need_kb": {
                    "type": "object",
                    "properties": {
                        "required": {"type": "boolean"},
                        "query": {"type": "string"},
                        "reason": {"type": "string"}
                    },
                    "required": ["required", "query", "reason"],
                    "additionalProperties": False
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score between 0.0 and 1.0"
                }
            },
            "required": [
                "situation_summary", "lead_goal_guess", "missing_info",
                "detected_objections", "stage_recommendation", "risk_flags",
                "need_kb", "confidence"
            ],
            "additionalProperties": False
        }
    }


def get_decision_schema() -> Dict[str, Any]:
    """JSON Schema for Decision step output."""
    return {
        "name": "decision_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["send_now", "wait_schedule", "flag_attention", "initiate_cta"],
                    "description": "Action to take"
                },
                "why": {
                    "type": "string",
                    "description": "Reason for the decision"
                },
                "next_stage": {
                    "type": "string",
                    "enum": ["greeting", "qualification", "pricing", "cta", "followup", "closed", "lost", "ghosted"],
                    "description": "Next conversation stage"
                },
                "recommended_cta": {
                    "type": ["string", "null"],
                    "enum": ["book_call", "book_demo", "book_meeting", None],
                    "description": "CTA type if applicable"
                },
                "cta_scheduled_time": {
                    "type": ["string", "null"],
                    "description": "ISO 8601 datetime for CTA"
                },
                "cta_name": {
                    "type": ["string", "null"],
                    "description": "Human-readable CTA label"
                },
                "followup_in_minutes": {
                    "type": "integer",
                    "description": "Minutes until followup"
                },
                "followup_reason": {
                    "type": "string",
                    "description": "Reason for followup timing"
                },
                "kb_used": {
                    "type": "boolean"
                },
                "template_required": {
                    "type": "boolean"
                }
            },
            "required": [
                "action", "why", "next_stage", "recommended_cta",
                "cta_scheduled_time", "cta_name", "followup_in_minutes",
                "followup_reason", "kb_used", "template_required"
            ],
            "additionalProperties": False
        }
    }


def get_generate_schema() -> Dict[str, Any]:
    """JSON Schema for Generate step output."""
    return {
        "name": "generate_output",
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
                "cta_type": {
                    "type": ["string", "null"],
                    "enum": ["book_call", "book_demo", "book_meeting", None],
                    "description": "CTA type if included"
                },
                "next_stage": {
                    "type": "string",
                    "enum": ["greeting", "qualification", "pricing", "cta", "followup", "closed", "lost", "ghosted"],
                    "description": "Next conversation stage"
                },
                "next_followup_in_minutes": {
                    "type": "integer",
                    "description": "Minutes until next followup"
                },
                "state_patch": {
                    "type": "object",
                    "properties": {
                        "intent_level": {
                            "type": ["string", "null"],
                            "enum": ["low", "medium", "high", "very_high", "unknown", None]
                        },
                        "user_sentiment": {
                            "type": ["string", "null"],
                            "enum": ["annoyed", "distrustful", "confused", "curious", "disappointed", "neutral", "uninterested", None]
                        },
                        "conversation_stage": {
                            "type": ["string", "null"],
                            "enum": ["greeting", "qualification", "pricing", "cta", "followup", "closed", "lost", "ghosted", None]
                        }
                    },
                    "required": ["intent_level", "user_sentiment", "conversation_stage"],
                    "additionalProperties": False
                },
                "self_check": {
                    "type": "object",
                    "properties": {
                        "guardrails_pass": {"type": "boolean"},
                        "violations": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["guardrails_pass", "violations"],
                    "additionalProperties": False
                }
            },
            "required": [
                "message_text", "message_language", "cta_type", "next_stage",
                "next_followup_in_minutes", "state_patch", "self_check"
            ],
            "additionalProperties": False
        }
    }


def get_summarize_schema() -> Dict[str, Any]:
    """JSON Schema for Summarize step output."""
    return {
        "name": "summarize_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "updated_rolling_summary": {
                    "type": "string",
                    "description": "Updated summary (80-200 words)"
                }
            },
            "required": ["updated_rolling_summary"],
            "additionalProperties": False
        }
    }
