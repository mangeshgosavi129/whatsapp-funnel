"""
Unified LLM Pipeline.
Orchestrates the single-step generation process.
"""
import logging
import time

from llm.schemas import PipelineInput, PipelineResult, GenerateOutput, RiskFlags
from llm.steps.generate import run_generate
from llm.knowledge import search_knowledge
from server.enums import DecisionAction, IntentLevel, UserSentiment

logger = logging.getLogger(__name__)


def run_pipeline(context: PipelineInput, user_message: str) -> PipelineResult:
    """
    Run the Unified Pipeline.
    
    Steps:
    1. RAG: Retrieve knowledge (Using user_message or context).
    2. GENERATE: Observe, Decide, Respond in one step.
    3. Return result for background processing (Memory).
    """
    start_time = time.time()
    total_latency_ms = 0
    
    try:
        # ========================================
        # Step 1: ALWAYS-ON RAG
        # ========================================
        # Simple heuristic: Use the raw user message for now.
        # Future: We could use a small classifier or keywords, but "Always On" was requested.
        try:
            logger.info(f"Running Step 1: RAG Search (Query: {user_message[:50]}...)")
            results = search_knowledge(
                query=user_message,
                organization_id=context.organization_id
            )
            
            if results:
                # Format results specific to this Org
                knowledge_text = "\n\n".join([
                    f"Source: {r['title']} (Confidence: {r['score']:.2f})\nContent: {r['content']}"
                    for r in results
                ])
                context.dynamic_knowledge_context = knowledge_text
                logger.info(f"RAG: Retrieved {len(results)} chunks.")
            else:
                context.dynamic_knowledge_context = "No relevant knowledge found."
                logger.info("RAG: No results found.")
                
        except Exception as e:
            logger.error(f"RAG Failed: {e}")
            context.dynamic_knowledge_context = "Error retrieving knowledge."

        # ========================================
        # Step 2: GENERATE (One Step)
        # ========================================
        logger.info("Running Step 2: Generate")
        generate_output, latency, tokens = run_generate(context)
        total_latency_ms += latency
        
        # ========================================
        # Build Result
        # ========================================
        # Helper logs
        if generate_output.should_respond:
            logger.info(f"Response: {len(generate_output.message_text)} chars")
        else:
            logger.info("No response generated (should_respond=False)")

        result = PipelineResult(
            generate=generate_output,
            pipeline_latency_ms=int((time.time() - start_time) * 1000),
            total_tokens_used=tokens,
            needs_background_summary=True,  # Signal to worker to run Memory
        )
        
        return result

    except Exception as e:
        logger.error(f"Pipeline Critical Error: {e}", exc_info=True)
        return _get_emergency_result(context)


def _get_emergency_result(context: PipelineInput) -> PipelineResult:
    """Catastrophic failure fallback."""
    
    # minimal valid output
    fallback = GenerateOutput(
        thought_process="Critical System Failure",
        intent_level=IntentLevel.UNKNOWN,
        user_sentiment=UserSentiment.NEUTRAL,
        risk_flags=RiskFlags(),
        action=DecisionAction.WAIT_SCHEDULE,
        new_stage=context.conversation_stage,
        should_respond=False,
        confidence=0.0,
        needs_human_attention=True,
        message_text="",
    )
    
    return PipelineResult(
        generate=fallback,
        needs_background_summary=False,
    )


def run_followup_pipeline(context: PipelineInput) -> PipelineResult:
    """
    Run pipeline for scheduled follow-ups.
    """
    synthetic_message = "[System: Scheduled follow-up triggered]"
    # We still run RAG even for followups? 
    # Maybe not useful since the message is synthetic, but "Always On" implies consistency.
    # However, searching for "[System...]" is useless.
    # We can skip RAG for followups or use the last summary.
    # For now, let's just run it compliant with "Always On" but knowing it won't find much.
    # Or better, we can inject context manually.
    
    # Actually, for followups, we might want to search based on the *last user message* or just skip.
    # I'll stick to running it to keep code simple, unless it breaks.
    return run_pipeline(context, synthetic_message)
