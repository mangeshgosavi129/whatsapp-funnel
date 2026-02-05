import logging
from llm.schemas import PipelineInput, PipelineResult, ClassifyOutput
from llm.steps.classify import run_classify
from llm.steps.generate import run_generate
from server.enums import DecisionAction

logger = logging.getLogger(__name__)

def run_pipeline(context: PipelineInput, user_message: str) -> PipelineResult:
    """
    Run the Router-Agent pipeline.
    
    Steps:
    1. CLASSIFY (The Brain): Analyze & Decide
    2. GENERATE (The Mouth): Write Message (if Brain says so)
    3. Return Result (with needs_background_summary=True)
    """
    total_latency_ms = 0
    total_tokens = 0
    
    try:
        # ========================================
        # Step 1: CLASSIFY (The Brain)
        # ========================================
        logger.info("Running Step 1: Classify (Brain)")
        classification, latency, tokens = run_classify(context)
        total_latency_ms += latency
        total_tokens += tokens
        
        # ========================================
        # Step 2: GENERATE (The Mouth)
        # ========================================
        response_output = None
        
        if classification.should_respond:
            logger.info(f"Running Step 2: Generate (Mouth) - Action: {classification.action.value}")
            response_output, latency, tokens = run_generate(context, classification)
            total_latency_ms += latency
            total_tokens += tokens
        else:
            logger.info("Skipping Generate (Brain decided not to respond)")

        # ========================================
        # Build Result
        # ========================================
        result = PipelineResult(
            classification=classification,
            response=response_output,
            summary=None, # To be filled by background worker
            pipeline_latency_ms=total_latency_ms,
            total_tokens_used=total_tokens,
            needs_background_summary=True # Signal to worker
        )
        
        logger.info(f"Pipeline Complete: {total_latency_ms}ms. Response: {bool(response_output)}")
        return result

    except Exception as e:
        logger.error(f"Pipeline Critical Error: {e}", exc_info=True)
        return _get_emergency_result()


def _get_emergency_result() -> PipelineResult:
    """Catastrophic failure fallback."""
    from llm.schemas import RiskFlags
    from server.enums import ConversationStage, IntentLevel, UserSentiment
    
    # Return a safe, do-nothing result to keep worker alive
    # We can't easily construct a full ClassifyOutput without imports here being messy, 
    # but let's try to be clean.
    
    # Minimal valid classification
    # We need to construct valid objects.
    rf = RiskFlags()
    
    classify_fallback = ClassifyOutput(
        thought_process="Critical Pipeline Failure",
        situation_summary="System Error",
        intent_level=IntentLevel.UNKNOWN,
        user_sentiment=UserSentiment.NEUTRAL,
        risk_flags=rf,
        action=DecisionAction.WAIT_SCHEDULE, # Safety default
        new_stage=ConversationStage.GREETING, # We don't know the stage, but schema requires one. 
        # Ideally we'd pass original stage but we don't have context here easily without passing it down.
        # It's fine, the worker won't update DB if we handle it right.
        should_respond=False,
        confidence=0.0
    )
    
    return PipelineResult(
        classification=classify_fallback,
        needs_background_summary=False # Don't try to summarize garbage
    )


def run_followup_pipeline(context: PipelineInput) -> PipelineResult:
    """
    Run pipeline for scheduled follow-ups.
    """
    synthetic_message = "[System: Scheduled follow-up triggered]"
    return run_pipeline(context, synthetic_message)
