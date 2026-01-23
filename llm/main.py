"""
LLM Module - Human Thinking Layer Pipeline.

This module provides the core HTL (Human Thinking Layer) pipeline
for processing WhatsApp sales conversations with AI.

Usage:
    from llm.pipeline import run_pipeline
    from llm.schemas import PipelineInput
    
    result = run_pipeline(context, user_message)
"""
from llm.pipeline import run_pipeline, run_followup_pipeline
from llm.schemas import (
    PipelineInput,
    PipelineResult,
    AnalyzeOutput,
    DecisionOutput,
    GenerateOutput,
    SummaryOutput,
)

__all__ = [
    "run_pipeline",
    "run_followup_pipeline",
    "PipelineInput",
    "PipelineResult",
    "AnalyzeOutput",
    "DecisionOutput",
    "GenerateOutput",
    "SummaryOutput",
]
