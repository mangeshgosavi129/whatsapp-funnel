"""
HTL Pipeline Orchestrator.
Runs all 4 steps and returns a complete pipeline result.
"""
import logging
from typing import Optional

from llm.schemas import (
    PipelineInput, PipelineResult,
    AnalyzeOutput, DecisionOutput, GenerateOutput, SummaryOutput
)
from llm.steps.analyze import run_analyze
from llm.steps.decide import run_decision
from llm.steps.generate import run_generate
from llm.steps.summarize import run_summarize
from server.enums import DecisionAction

logger = logging.getLogger(__name__)


def run_pipeline(context: PipelineInput, user_message: str) -> PipelineResult:
    """
    Run the complete HTL pipeline.
    
    Steps:
    1. ANALYZE - Understand the conversation
    2. DECIDE - Choose action (send now, wait, escalate)
    3. GENERATE - Write message (only if SEND_NOW)
    4. SUMMARIZE - Update rolling summary
    
    Args:
        context: Complete pipeline input context
        user_message: The message that triggered this pipeline run
        
    Returns:
        PipelineResult with all step outputs and computed actions
    """
    total_latency_ms = 0
    total_tokens = 0
    
    # ========================================
    # Step 1: ANALYZE
    # ========================================
    logger.info("Running Step 1: Analyze")
    analysis, latency, tokens = run_analyze(context)
    total_latency_ms += latency
    total_tokens += tokens
    
    # ========================================
    # Step 2: DECIDE
    # ========================================
    logger.info("Running Step 2: Decide")
    decision, latency, tokens = run_decision(context, analysis)
    total_latency_ms += latency
    total_tokens += tokens
    
    # ========================================
    # Step 3: GENERATE (conditional)
    # ========================================
    response_output: Optional[GenerateOutput] = None
    bot_message = ""
    
    if decision.action == DecisionAction.SEND_NOW:
        logger.info("Running Step 3: Generate")
        response_output, latency, tokens = run_generate(context, decision)
        total_latency_ms += latency
        total_tokens += tokens
        
        if response_output:
            bot_message = response_output.message_text
    else:
        logger.info(f"Skipping Step 3: action={decision.action.value}")
    
    # ========================================
    # Step 4: SUMMARIZE (always)
    # ========================================
    logger.info("Running Step 4: Summarize")
    summary, latency, tokens = run_summarize(
        context, user_message, bot_message, response_output
    )
    total_latency_ms += latency
    total_tokens += tokens
    
    # ========================================
    # Build Final Result
    # ========================================
    result = PipelineResult(
        analysis=analysis,
        decision=decision,
        response=response_output,
        summary=summary,
        pipeline_latency_ms=total_latency_ms,
        total_tokens_used=total_tokens,
        should_send_message=decision.action == DecisionAction.SEND_NOW and bool(bot_message),
        should_schedule_followup=decision.action == DecisionAction.WAIT_SCHEDULE,
        should_escalate=decision.action == DecisionAction.HANDOFF_HUMAN,
    )
    
    logger.info(
        f"Pipeline complete: latency={total_latency_ms}ms, tokens={total_tokens}, "
        f"action={decision.action.value}, send={result.should_send_message}"
    )
    
    return result


def run_followup_pipeline(context: PipelineInput) -> PipelineResult:
    """
    Run pipeline for a scheduled follow-up.
    
    This is called by Celery beat when a follow-up is due.
    The main difference is we don't have a new user message - we're initiating.
    
    Args:
        context: Pipeline context (with latest conversation state)
        
    Returns:
        PipelineResult
    """
    # For follow-ups, we synthesize a "trigger" message
    synthetic_message = "[System: Scheduled follow-up triggered]"
    
    return run_pipeline(context, synthetic_message)
