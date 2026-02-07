import sys
import os

# Force UTF-8 encoding on Windows to prevent UnicodeEncodeError in logging
os.environ['PYTHONIOENCODING'] = 'utf-8'

import asyncio
import logging
import time
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

# === CUSTOM LOGGING FOR SIMULATION ===
class ColorFormatter(logging.Formatter):
    """Custom formatter to highlight pipeline steps."""
    
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    cyan = "\x1b[36;20m"
    green = "\x1b[32;20m"
    purple = "\x1b[35;20m"
    blue = "\x1b[34;20m"
    reset = "\x1b[0m"
    format_str = "%(message)s" 

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: grey + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        msg = record.msg
        if isinstance(msg, str):
            if "👁️" in msg:
                log_fmt = self.blue + "%(message)s" + self.reset
            elif "🧠" in msg:
                log_fmt = self.purple + "%(message)s" + self.reset
            elif "🗣️" in msg:
                log_fmt = self.cyan + "%(message)s" + self.reset
            elif "⏱️" in msg:
                log_fmt = self.green + "%(message)s" + self.reset
            elif "Bot:" in msg:
                log_fmt = self.yellow + "%(message)s" + self.reset
        
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# Configure logging with UTF-8 encoding for Windows
import io
if sys.platform == 'win32':
    # Wrap stdout/stderr with UTF-8 encoding, replacing unencodable chars
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Clear any existing handlers from root logger
root_logger = logging.getLogger()
for h in root_logger.handlers[:]:
    root_logger.removeHandler(h)

# Create handler AFTER stdout is reconfigured
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColorFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)

# Quiet down some loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("whatsapp_worker.main").setLevel(logging.CRITICAL)
logging.getLogger("whatsapp_worker.processors.actions").setLevel(logging.DEBUG)

# Disable LLM logger completely to prevent encoding errors
llm_log = logging.getLogger("llm")
llm_log.setLevel(logging.CRITICAL)  # Only log critical errors
llm_log.handlers.clear()
llm_log.propagate = False 

from whatsapp_worker import main as worker_main
from whatsapp_worker.processors.api_client import api_client
from llm.schemas import EyesOutput, BrainOutput, MouthOutput
from llm import pipeline
from llm.steps import eyes, brain, mouth, memory
from llm.prompts import (
    EYES_SYSTEM_PROMPT, EYES_USER_TEMPLATE,
    BRAIN_SYSTEM_PROMPT, BRAIN_USER_TEMPLATE,
    MOUTH_SYSTEM_PROMPT, MOUTH_USER_TEMPLATE
)

# ==========================================
# MONKEY PATCHING FOR TRACING (ASYNC)
# ==========================================

VERBOSE = True

def _safe_slice(text: str, max_len: int) -> str:
    """Safely slice text with ellipsis if needed (only when not VERBOSE)."""
    if not text:
        return "(empty)"
    if VERBOSE:
        return text
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


original_run_eyes = eyes.run_eyes
original_run_brain = brain.run_brain
original_run_mouth = mouth.run_mouth
original_run_memory = memory.run_memory


async def traced_run_eyes(context, tracer=None):
    start = time.time()
    
    print(f"\n[EYES] (INPUT)")
    print(f"   > Stage: {context.conversation_stage.value}")
    print(f"   > Intent: {context.intent_level.value} | Sentiment: {context.user_sentiment.value}")
    print(f"   > Messages: {len(context.last_messages)}")
    if context.last_messages:
        for msg in context.last_messages[-5:]:  # Last 5 messages when verbose
            print(f"      [{msg.sender}] {_safe_slice(msg.text, 100)}")
        
    result, lat, tokens = await original_run_eyes(context, tracer=tracer)
    duration = (time.time() - start) * 1000
    
    print(f"\n[EYES] (OUTPUT) - {duration:.1f}ms")
    print(f"   - Observation: {_safe_slice(result.observation, 200)}")
    print(f"   - Intent: {result.intent_level.value} | Sentiment: {result.user_sentiment.value}")
    print(f"   - Risks: Spam={result.risk_flags.spam_risk.value} | Policy={result.risk_flags.policy_risk.value}")
    print(f"   - Confidence: {result.confidence}")
    
    return result, lat, tokens


async def traced_run_brain(context, eyes_output, tracer=None):
    start = time.time()
    
    print(f"\n[BRAIN] (INPUT)")
    print(f"   > Observation: {_safe_slice(eyes_output.observation, 150)}")
    print(f"   > Available CTAs: {len(context.available_ctas)}")
    
    result, lat, tokens = await original_run_brain(context, eyes_output, tracer=tracer)
    duration = (time.time() - start) * 1000
    
    print(f"\n[BRAIN] (OUTPUT) - {duration:.1f}ms")
    print(f"   - Implementation Plan: {_safe_slice(result.implementation_plan, 150)}")
    print(f"   - Action: {result.action.value} | Should Respond: {result.should_respond}")
    print(f"   - Stage -> {result.new_stage.value.upper()}")
    print(f"   - Followup: {result.followup_in_minutes}m | Reason: {_safe_slice(result.followup_reason, 50) if result.followup_reason else 'N/A'}")
    print(f"   - Human Attention: {result.needs_human_attention}")
    
    return result, lat, tokens


async def traced_run_mouth(context, brain_output, tracer=None):
    start = time.time()
    
    print(f"\n[MOUTH] (INPUT)")
    print(f"   > Implementation Plan: {_safe_slice(brain_output.implementation_plan, 150)}")
    print(f"   > Max Words: {context.max_words}")
    
    result, lat, tokens = await original_run_mouth(context, brain_output, tracer=tracer)
    duration = (time.time() - start) * 1000
    
    print(f"\n[MOUTH] (OUTPUT) - {duration:.1f}ms")
    if result and result.message_text:
        print(f"   - Generated: \"{result.message_text}\"")
    else:
        print(f"   - Generated: (No Text)")
    
    return result, lat, tokens


async def traced_run_memory(context, user_message, mouth_output, brain_output, tracer=None):
    """Traced version of run_memory for simulation visibility."""
    start = time.time()
    
    print(f"\n[MEMORY] (INPUT)")
    print(f"   > Context Summary Len: {len(context.rolling_summary)} chars")
    
    result_summary = await original_run_memory(context, user_message, mouth_output, brain_output, tracer=tracer)
    duration = (time.time() - start) * 1000
    
    print(f"\n[MEMORY] (OUTPUT) - {duration:.1f}ms")
    if result_summary:
        print(f"   - New Summary: {_safe_slice(result_summary, 150)}")
    else:
        print(f"   - No new summary generated")
    
    return result_summary


# Apply patches to pipeline module
pipeline.run_eyes = traced_run_eyes
pipeline.run_brain = traced_run_brain
pipeline.run_mouth = traced_run_mouth

# Patch memory in the llm.steps.memory module AND whatsapp_worker.main
memory.run_memory = traced_run_memory
worker_main.run_memory = traced_run_memory


# ==========================================
# MOCK / PATCH SETTINGS
# ==========================================

TEST_STATE = {
    "human_attention_triggered": False,
    "last_bot_message": None
}

original_send_bot_message = api_client.send_bot_message
original_emit_human_attention = api_client.emit_human_attention


def mocked_send_bot_message(organization_id, conversation_id, content, *args, **kwargs):
    """Isolated mock: logs and stores message in DB, but does NOT call real WhatsApp API."""
    print(f"\n[BOT]: \"{content}\"")
    TEST_STATE["last_bot_message"] = content
    
    try:
        conv = api_client.get_conversation(conversation_id)
        if conv:
            lead_id = conv['lead_id']
            api_client.store_outgoing_message(
                conversation_id=conversation_id,
                lead_id=lead_id,
                content=content,
                message_from="bot"
            )
    except Exception as e:
        print(f"[ERROR] Failed to store bot message in DB: {e}")

    return {"status": "simulated_success"}


def mocked_emit_human_attention(conversation_id, organization_id):
    """Calls REAL internal API to trigger WebSocket event for frontend visibility."""
    print(f"\n[ALERT] Human Attention Event for Conv {conversation_id}!")
    TEST_STATE["human_attention_triggered"] = True
    
    try:
        return original_emit_human_attention(conversation_id, organization_id)
    except Exception as e:
        print(f"[ERROR] emit_human_attention failed: {e}")
        return {"status": "error", "error": str(e)}


# Patch the api_client instances
import whatsapp_worker.processors.actions as actions_module
actions_module.api_client.emit_human_attention = mocked_emit_human_attention
actions_module.api_client.send_bot_message = mocked_send_bot_message
api_client.emit_human_attention = mocked_emit_human_attention
api_client.send_bot_message = mocked_send_bot_message

# ==========================================
# TEST SCENARIOS
# ==========================================

TEST_SCENARIOS = [
    {
        "name": "Greeting (Happy Path)",
        "input": "Hi",
        "expected": {
            "should_respond": True
        }
    }
]

# ==========================================
# SIMULATION LOOP & TEST RUNNER
# ==========================================

async def run_test_scenarios_async(phone_id, user_phone, user_name):
    print(f"\n[TEST] Running {len(TEST_SCENARIOS)} Test Scenarios...")
    print("===========================================")
    
    passed = 0
    loop = asyncio.get_running_loop()
    
    for i, scenario in enumerate(TEST_SCENARIOS):
        print(f"\n[{i+1}] Scenario: {scenario['name']}")
        print(f"   Input: \"{scenario['input']}\"")
        
        TEST_STATE["human_attention_triggered"] = False
        TEST_STATE["last_bot_message"] = None
        
        start_t = time.time()
        
        # Call Async Process Message
        result, status_code = await worker_main.process_message(
            phone_number_id=phone_id,
            sender_phone=user_phone,
            sender_name=user_name,
            message_text=scenario['input'],
            loop=loop
        )
        duration = (time.time() - start_t) * 1000
        
        failures = []
        if status_code != 200:
            failures.append(f"Status Code: Got {status_code}, Expected 200")
        
        expected = scenario.get("expected", {})
        if "should_respond" in expected:
            was_sent = result.get("send", False)
            if was_sent != expected["should_respond"]:
                 failures.append(f"Response Sent: Got {was_sent}, Expected {expected['should_respond']}")

        if not failures:
            print(f"   [PASS] ({duration:.1f}ms)")
            passed += 1
        else:
            print(f"   [FAIL] ({duration:.1f}ms)")
            for f in failures:
                print(f"      - {f}")
                
    print(f"\n{'-'*30}")
    print(f"Results: {passed}/{len(TEST_SCENARIOS)} Passed")
    print(f"{'-'*30}\n")


async def interactive_session(phone_id, sender_phone, sender_name):
    print(f"\n[OK] Session: {sender_name} ({sender_phone})")
    print("Type 'quit' to exit.\n")
    
    loop = asyncio.get_running_loop()
    
    while True:
        try:
            print("-" * 60)
            user_input = await asyncio.to_thread(input, f"{sender_name}: ")
            user_input = user_input.strip()
            
            if user_input.lower() in ['quit', 'exit']:
                break
            
            if not user_input:
                continue
                
            print("\nProcessing...")
            start_total = time.time()
            
            TEST_STATE["human_attention_triggered"] = False
            
            result, status_code = await worker_main.process_message(
                phone_number_id=phone_id,
                sender_phone=sender_phone,
                sender_name=sender_name,
                message_text=user_input,
                loop=loop
            )
            
            total_duration = (time.time() - start_total) * 1000
            print(f"\nTotal End-to-End Latency: {total_duration:.1f}ms")
            
            if status_code != 200:
                print(f"[WARNING] Error {status_code}: {result}")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[ERROR] Exception: {e}")
            import traceback
            traceback.print_exc()


def run_simulation(args):
    print("\n=== Eyes -> Brain -> Mouth Pipeline Simulator (Async) ===")
    print("=========================================================")
    
    phone_id = "123123"
    sender_phone = "919999999999" 
    sender_name = "Test User"
    
    if args.test:
        asyncio.run(run_test_scenarios_async(phone_id, sender_phone, sender_name))
    else:
        # Interactive
        phone_number_id = input(f"Enter Phone ID [Default: {phone_id}]: ").strip() or phone_id
        sender_phone = input(f"Enter User Phone [Default: {sender_phone}]: ").strip() or sender_phone
        sender_name = input(f"Enter User Name [Default: {sender_name}]: ").strip() or sender_name
        
        asyncio.run(interactive_session(phone_number_id, sender_phone, sender_name))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Eyes → Brain → Mouth Pipeline Simulator")
    parser.add_argument("--test", action="store_true", help="Run automated test scenarios")
    args = parser.parse_args()
    
    run_simulation(args)
