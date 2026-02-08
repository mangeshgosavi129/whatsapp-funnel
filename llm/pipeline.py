"""
Eyes → Brain → Mouth → Memory Pipeline.
Orchestrates the 4-stage LLM pipeline.
"""
import logging
from llm.schemas import PipelineInput, PipelineResult, BrainOutput, EyesOutput
from llm.steps.eyes import run_eyes
from llm.steps.brain import run_brain
from llm.steps.mouth import run_mouth
from llm.knowledge import search_knowledge
from server.enums import DecisionAction

logger = logging.getLogger(__name__)


def run_pipeline(context: PipelineInput, user_message: str) -> PipelineResult:
    """
    Run the Eyes → Brain → Mouth → Memory pipeline.
    
    Steps:
    1. EYES: Observe and analyze
    2. BRAIN: Decide and strategize
    3. MOUTH: Communicate (if Brain says so)
    4. MEMORY: Backgrounded (not in this call)
    """
    total_latency_ms = 0
    total_tokens = 0
    
    try:
        # ========================================
        # Step 1: EYES
        # ========================================
        logger.info("Running Step 1: Eyes")
        eyes_output, latency, tokens = run_eyes(context)
        total_latency_ms += latency
        total_tokens += tokens
        
        total_tokens += tokens

        # ========================================
        # Step 1.5: KNOWLEDGE RETRIEVAL (Conditional)
        # ========================================
        if eyes_output.knowledge_needed:
            logger.info(f"Running Step 1.5: Knowledge Retrieval - Topic: {eyes_output.knowledge_topic}")
            try:
                # Construct query: User message + Context if needed
                # Ideally we use the raw user message for keywords
                query = user_message
                if eyes_output.knowledge_topic:
                    query = f"{eyes_output.knowledge_topic}: {query}"
                
                start_rag = 0 # timestamp usually, but let's just log
                # We reuse the organization_id from context
                results = search_knowledge(
                    query=query,
                    organization_id=context.organization_id
                )
                
                if results:
                    # Format results for Brain
                    knowledge_text = "\n\n".join([
                        f"Source: {r['title']} (Confidence: {r['score']:.2f})\nContent: {r['content']}"
                        for r in results
                    ])
                    context.dynamic_knowledge_context = knowledge_text
                    logger.info(f"RAG: Retrieved {len(results)} chunks.")
                else:
                    context.dynamic_knowledge_context = "No relevant knowledge found."
                    logger.info("RAG: No results found (filtered by threshold).")
                    
            except Exception as e:
                logger.error(f"RAG Failed: {e}")
                context.dynamic_knowledge_context = "Error retrieving knowledge."

        # ========================================
        # Step 2: BRAIN
        # ========================================
        logger.info("Running Step 2: Brain")
        # Brain now sees context.dynamic_knowledge_context populated
        brain_output, latency, tokens = run_brain(context, eyes_output)
        total_latency_ms += latency
        total_tokens += tokens
        
        # ========================================
        # Step 3: MOUTH
        # ========================================
        mouth_output = None
        
        if brain_output.should_respond:
            logger.info(f"Running Step 3: Mouth - Action: {brain_output.action.value}")
            mouth_output, latency, tokens = run_mouth(context, brain_output)
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


def run_followup_pipeline(context: PipelineInput) -> PipelineResult:
    """
    Run pipeline for scheduled follow-ups.
    """
    synthetic_message = "[System: Scheduled follow-up triggered]"
    return run_pipeline(context, synthetic_message)
