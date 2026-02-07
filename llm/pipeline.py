"""
Eyes → Brain → Mouth → Memory Pipeline.
Orchestrates the 4-stage LLM pipeline.
"""
import logging
from llm.schemas import PipelineInput, PipelineResult, BrainOutput, EyesOutput
from llm.steps.eyes import run_eyes
from llm.steps.brain import run_brain
from llm.steps.mouth import run_mouth
from server.enums import DecisionAction
from llm.tracing import PipelineTracer

logger = logging.getLogger(__name__)


async def run_pipeline(context: PipelineInput, user_message: str) -> PipelineResult:
    """
    Run the Eyes → Brain → Mouth → Memory pipeline (Async).
    
    Steps:
    1. EYES: Observe and analyze
    2. BRAIN: Decide and strategize
    3. MOUTH: Communicate (if Brain says so)
    4. MEMORY: Backgrounded (not in this call)
    """
    tracer = PipelineTracer()
    total_latency_ms = 0
    total_tokens = 0
    
    try:
        # ========================================
        # Step 1: EYES
        # ========================================
        logger.info("Running Step 1: Eyes")
        eyes_output, latency, tokens = await run_eyes(context, tracer=tracer)
        total_latency_ms += latency
        total_tokens += tokens
        
        # ========================================
        # Step 2: BRAIN
        # ========================================
        logger.info("Running Step 2: Brain")
        brain_output, latency, tokens = await run_brain(context, eyes_output, tracer=tracer)
        total_latency_ms += latency
        total_tokens += tokens
        
        # ========================================
        # Step 3: MOUTH
        # ========================================
        mouth_output = None
        
        if brain_output.should_respond:
            logger.info(f"Running Step 3: Mouth - Action: {brain_output.action.value}")
            mouth_output, latency, tokens = await run_mouth(context, brain_output, tracer=tracer)
            total_latency_ms += latency
            total_tokens += tokens
        else:
            logger.info("Skipping Mouth (Brain decided not to respond)")

        # ========================================
        # Build Result
        # ========================================
        result = PipelineResult(
            eyes=eyes_output,
            brain=brain_output,
            mouth=mouth_output,
            memory=None,  # To be filled by background worker
            pipeline_latency_ms=total_latency_ms,
            total_tokens_used=total_tokens,
            needs_background_summary=True,  # Signal to worker
        )
        
        logger.info(f"Pipeline Complete: {total_latency_ms}ms. Response: {bool(mouth_output)}")
        tracer.end_trace(final_output=result.model_dump_json(exclude={"eyes", "brain"})) # Summary log
        
        return result

    except Exception as e:
        logger.error(f"Pipeline Critical Error: {e}", exc_info=True)
        return _get_emergency_result(context)


def _get_emergency_result(context: PipelineInput) -> PipelineResult:
    """Catastrophic failure fallback."""
    from llm.schemas import RiskFlags
    from server.enums import IntentLevel, UserSentiment
    
    # Minimal valid Eyes output
    eyes_fallback = EyesOutput(
        observation="Critical Pipeline Failure",
        thought_process="System Error",
        situation_summary="Error",
        intent_level=IntentLevel.UNKNOWN,
        user_sentiment=UserSentiment.NEUTRAL,
        risk_flags=RiskFlags(),
        confidence=0.0,
    )
    
    # Minimal valid Brain output
    brain_fallback = BrainOutput(
        implementation_plan="System Error - Do not respond",
        action=DecisionAction.WAIT_SCHEDULE,
        new_stage=context.conversation_stage,
        should_respond=False,
        confidence=0.0,
    )
    
    return PipelineResult(
        eyes=eyes_fallback,
        brain=brain_fallback,
        needs_background_summary=False,  # Don't try to summarize garbage
    )


async def run_followup_pipeline(context: PipelineInput) -> PipelineResult:
    """
    Run pipeline for scheduled follow-ups (Async).
    """
    synthetic_message = "[System: Scheduled follow-up triggered]"
    return await run_pipeline(context, synthetic_message)
