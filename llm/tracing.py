"""
Pipeline Tracing and Observability Module.
Handles structured logging, cost estimation, and latency tracking.
"""
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Pricing (approximate as of early 2025)
# $/1M tokens
PRICING = {
    # Groq Llama 3 70B
    "llama3-70b-8192": {"input": 0.59, "output": 0.79},
    # Groq Llama 3 8B
    "llama3-8b-8192": {"input": 0.05, "output": 0.10},
    # Fallback / OpenAI
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}

DEFAULT_PRICING = {"input": 1.0, "output": 1.0}  # Placeholder if unknown

class PipelineTracer:
    """
    Tracks a single pipeline execution execution.
    Logs steps, latency, tokens, and cost.
    """
    
    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or str(uuid4())
        self.start_time = time.time()
        self.steps: list[Dict[str, Any]] = []
        self.total_cost = 0.0
        self.total_tokens = 0
        
        # Ensure logs directory exists
        self.log_dir = Path("logs/traces")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"trace_{datetime.now().strftime('%Y-%m-%d')}.jsonl"

    def log_step(
        self, 
        step_name: str, 
        input_data: Any, 
        output_data: Any, 
        latency_ms: int,
        model: str,
        token_usage: Dict[str, int],  # {"prompt": x, "completion": y}
    ):
        """Log a completed step."""
        
        # Calculate cost
        price_rates = PRICING.get(model, DEFAULT_PRICING)
        input_cost = (token_usage.get("prompt", 0) / 1_000_000) * price_rates.get("input", 0)
        output_cost = (token_usage.get("completion", 0) / 1_000_000) * price_rates.get("output", 0)
        step_cost = input_cost + output_cost
        
        self.total_cost += step_cost
        self.total_tokens += (token_usage.get("prompt", 0) + token_usage.get("completion", 0))

        step_record = {
            "step": step_name,
            "timestamp": datetime.now().isoformat(),
            "latency_ms": latency_ms,
            "model": model,
            "tokens": token_usage,
            "cost_usd": round(step_cost, 6),
            "input_preview": str(input_data)[:200],  # Truncate for log preview
            "output_preview": str(output_data)[:200],
            # Full data could be logged if needed, but keeping it light for now
        }
        
        self.steps.append(step_record)
        
        # Log to file immediately (append)
        self._write_to_log(step_record)
        
        logger.info(f"[{step_name}] {latency_ms}ms | ${step_cost:.6f} | {model}")

    def end_trace(self, final_output: Any):
        """End the trace and log summary."""
        duration_ms = int((time.time() - self.start_time) * 1000)
        
        summary = {
            "trace_id": self.trace_id,
            "event": "pipeline_complete",
            "timestamp": datetime.now().isoformat(),
            "duration_ms": duration_ms,
            "total_cost_usd": round(self.total_cost, 6),
            "total_tokens": self.total_tokens,
            "steps_count": len(self.steps),
            "final_result": str(final_output)[:500]
        }
        
        self._write_to_log(summary)
        logger.info(f"Trace {self.trace_id} complete: {duration_ms}ms, ${self.total_cost:.6f}")

    def _write_to_log(self, data: Dict[str, Any]):
        """Write a record to the daily JSONL log."""
        try:
            entry = {"trace_id": self.trace_id, **data}
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write trace log: {e}")
