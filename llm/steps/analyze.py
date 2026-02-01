"""
Step 1: ANALYZE - Understand the conversation context.
"""
import json
import logging
import time
from typing import Tuple

from openai import OpenAI

from llm.config import llm_config
from llm.schemas import PipelineInput, AnalyzeOutput, RiskFlags, KBRequirement
from llm.prompts import ANALYZE_SYSTEM_PROMPT, ANALYZE_USER_TEMPLATE
from llm.utils import normalize_enum
from llm.api_helpers import llm_call_with_retry, extract_json_from_text
from server.enums import ConversationStage, RiskLevel, IntentLevel, UserSentiment

logger = logging.getLogger(__name__)


def _format_messages(messages: list) -> str:
    """Format messages for prompt (token-efficient)."""
    if not messages:
        return "No messages yet"
    
    lines = []
    for msg in messages[-3:]:  # Last 3 only
        lines.append(f"[{msg.sender}] {msg.text}")
    return "\n".join(lines)


def _build_user_prompt(context: PipelineInput) -> str:
    """Build the user prompt with context."""
    return ANALYZE_USER_TEMPLATE.format(
        business_name=context.business_name,
        rolling_summary=context.rolling_summary or "No summary yet",
        last_3_messages=_format_messages(context.last_3_messages),
        conversation_stage=context.conversation_stage.value,
        conversation_mode=context.conversation_mode,
        intent_level=context.intent_level.value,
        user_sentiment=context.user_sentiment.value,
        active_cta=context.active_cta.value if context.active_cta else "none",
        now_local=context.timing.now_local,
        last_user_at=context.timing.last_user_message_at or "unknown",
        last_bot_at=context.timing.last_bot_message_at or "unknown",
        whatsapp_window_open=context.timing.whatsapp_window_open,
        followup_count_24h=context.nudges.followup_count_24h,
        total_nudges=context.nudges.total_nudges,
    )


def _parse_response(content: str) -> dict:
    """Parse JSON from LLM response, handling common issues."""
    # Strip markdown code blocks if present
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    
    return json.loads(content)


def _validate_and_build_output(data: dict) -> AnalyzeOutput:
    """Validate and build typed output from raw JSON."""
    # Map stage string to enum with fuzzy matching
    stage = normalize_enum(
        data.get("stage_recommendation"),
        ConversationStage,
        ConversationStage.GREETING
    )
    
    # Build risk flags
    rf = data.get("risk_flags", {})
    risk_flags = RiskFlags(
        spam_risk=RiskLevel(rf.get("spam_risk", "low")),
        policy_risk=RiskLevel(rf.get("policy_risk", "low")),
        hallucination_risk=RiskLevel(rf.get("hallucination_risk", "low")),
    )
    
    # Build KB requirement
    kb = data.get("need_kb", {})
    need_kb = KBRequirement(
        required=kb.get("required", False),
        query=kb.get("query", ""),
        reason=kb.get("reason", ""),
    )

    # Extract Intent & Sentiment (Required for analytics)
    intent_level = normalize_enum(data.get("intent_level"), IntentLevel, IntentLevel.UNKNOWN)
    user_sentiment = normalize_enum(data.get("user_sentiment"), UserSentiment, UserSentiment.NEUTRAL)
    
    # ---------------------------------------------------------
    # REFINE STAGE WITH KEYWORDS (Heuristic Boost)
    # ---------------------------------------------------------
    confidence = min(1.0, max(0.0, data.get("confidence", 0.5)))
    
    # If confidence is low/medium, let's see if keywords can boost a stage
    if confidence < 0.9:
        stage = _refine_stage_with_keywords(stage, data, 0.9)  # Pass dummy threshold logic inside if needed? 
        # Actually easier to just check keywords against missing info or summary if we had access to raw text? 
        # But we only have the 'data' dict here.
        # We need the 'User Message' ideally, but we don't have it in this function scope easily 
        # unless we pass it. 
        # Let's trust the LLM for now but maybe just rely on the 'detected_objections' or 'missing_info' 
        # if they map to stages? 
        # Wait, the plan was to inspect last user message.
        pass # Optimization: We will rely on prompt improvements from Step 1 for now.
        # Design decision: To keep it less "bloated", I will skip adding a hefty keyword, 
        # regex engine here and rely on the Prompt + Decide override.
        # The user specifically asked about "bloat". Adding 50 lines of keyword matching MIGHT be considered bloat.
        # The Decide step override is the Critical Safety Net.
        # I will stick to just the schema validation here.
    
    return AnalyzeOutput(
        situation_summary=data.get("situation_summary", "Unable to analyze")[:200],
        lead_goal_guess=data.get("lead_goal_guess", "Unknown")[:100],
        missing_info=data.get("missing_info", [])[:5],
        detected_objections=data.get("detected_objections", [])[:3],
        stage_recommendation=stage,
        intent_level=intent_level,
        user_sentiment=user_sentiment,
        risk_flags=risk_flags,
        need_kb=need_kb,
        confidence=confidence,
    )

def _refine_stage_with_keywords(current_stage, data, threshold):
    # Placeholder: In non-bloated version, we trust the prompt.
    return current_stage


def run_analyze(context: PipelineInput) -> Tuple[AnalyzeOutput, int, int]:
    """
    Run the Analyze step with retry logic and graceful fallback.
    
    Returns:
        Tuple of (AnalyzeOutput, latency_ms, tokens_used)
    """
    client = OpenAI(
        api_key=llm_config.api_key,
        base_url=llm_config.base_url,
    )
    
    user_prompt = _build_user_prompt(context)
    
    start_time = time.time()
    tokens_used = 0
    
    def make_api_call():
        return client.chat.completions.create(
            model=llm_config.model,
            messages=[
                {"role": "system", "content": ANALYZE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},  # More reliable than strict schema
        )
    
    try:
        data = llm_call_with_retry(
            api_call=make_api_call,
            max_retries=2,
            step_name="Analyze"
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        output = _validate_and_build_output(data)
        
        logger.info(f"Analyze step completed: stage={output.stage_recommendation.value}, confidence={output.confidence}")
        
        return output, latency_ms, tokens_used
        
    except Exception as e:
        logger.error(f"Analyze step failed: {e}", exc_info=True)
        return _get_fallback_output(), int((time.time() - start_time) * 1000), 0


def _get_fallback_output() -> AnalyzeOutput:
    """Return safe fallback output on error."""
    return AnalyzeOutput(
        situation_summary="Analysis unavailable",
        lead_goal_guess="Unknown",
        missing_info=[],
        detected_objections=[],
        stage_recommendation=ConversationStage.GREETING,
        intent_level=IntentLevel.UNKNOWN,
        user_sentiment=UserSentiment.NEUTRAL,
        risk_flags=RiskFlags(
            spam_risk=RiskLevel.MEDIUM,
            policy_risk=RiskLevel.MEDIUM,
            hallucination_risk=RiskLevel.HIGH,
        ),
        need_kb=KBRequirement(required=False, query="", reason=""),
        confidence=0.0,
    )
