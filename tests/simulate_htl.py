import sys
import os

# Force UTF-8 encoding on Windows to prevent UnicodeEncodeError in logging
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.append(os.getcwd())

import asyncio
import logging
import time
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import datetime
from llm.knowledge import search_knowledge as original_search_knowledge
import io
import whatsapp_worker.processors.actions as actions_module
import llm.pipeline
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
# CRITICAL: Must reconfigure stdout BEFORE creating any handlers
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
# (we trace pipeline steps manually, so we don't need LLM request/response logs)
llm_log = logging.getLogger("llm")
llm_log.setLevel(logging.CRITICAL)  # Only log critical errors
llm_log.handlers.clear()
llm_log.propagate = False 



# ==========================================
# MONKEY PATCHING FOR TRACING
# ==========================================

# Set to True to see full prompts/outputs without truncation
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


def traced_run_eyes(context):
    start = time.time()
    
    print(f"\n[EYES] (INPUT)")
    print(f"   > Stage: {context.conversation_stage.value}")
    print(f"   > Intent: {context.intent_level.value} | Sentiment: {context.user_sentiment.value}")
    print(f"   > Messages: {len(context.last_messages)}")
    if context.last_messages:
        for msg in context.last_messages[-5:]:  # Last 5 messages when verbose
            print(f"      [{msg.sender}] {_safe_slice(msg.text, 100)}")
        
    result, lat, tokens = original_run_eyes(context)
    duration = (time.time() - start) * 1000
    
    print(f"\n[EYES] (OUTPUT) - {duration:.1f}ms")
    print(f"   - Observation: {_safe_slice(result.observation, 200)}")
    print(f"   - Intent: {result.intent_level.value} | Sentiment: {result.user_sentiment.value}")
    print(f"   - Risks: Spam={result.risk_flags.spam_risk.value} | Policy={result.risk_flags.policy_risk.value}")
    print(f"   - Confidence: {result.confidence}")
    
    return result, lat, tokens



# Import original search_knowledge


def traced_search_knowledge(query, organization_id, **kwargs):
    """Traced version of search_knowledge."""
    start = time.time()
    print(f"\n[RAG] (SEARCH)")
    print(f"   > Query: {query}")
    print(f"   > Org ID: {organization_id}")
    
    results = original_search_knowledge(query, organization_id, **kwargs)
    duration = (time.time() - start) * 1000
    
    print(f"\n[RAG] (RESULTS) - {duration:.1f}ms")
    if results:
        print(f"   > Found {len(results)} chunks")
        for i, res in enumerate(results):
            print(f"   [{i+1}] {bold_green}{res.get('title', 'Unknown')}{reset} (Score: {res.get('score', 0.0):.4f})")
            print(f"       {_safe_slice(res.get('content', ''), 100).replace(newline, ' ')}")
    else:
        print(f"   > No results found")
        
    return results

# Apply patch
pipeline.search_knowledge = traced_search_knowledge
# Also patch the module directly just in case
llm.pipeline.search_knowledge = traced_search_knowledge

# ANSI codes for helper - redefining here since they are in class scope above
bold_green = "\x1b[32;1m"
reset = "\x1b[0m"
newline = "\n"


def traced_run_brain(context, eyes_output):
    start = time.time()
    
    print(f"\n[BRAIN] (INPUT)")
    print(f"   > Observation: {_safe_slice(eyes_output.observation, 150)}")
    print(f"   > Available CTAs: {len(context.available_ctas)}")
    print(f"   > Nudges 24h: {context.nudges.followup_count_24h}")
    
    # Trace RAG Context if present
    if hasattr(context, 'dynamic_knowledge_context') and context.dynamic_knowledge_context:
        print(f"   > RAG Context Injected: Yes ({len(context.dynamic_knowledge_context)} chars)")
        if VERBOSE:
             print(f"   --> {_safe_slice(context.dynamic_knowledge_context, 200).replace(newline, ' ')}")
    else:
        print(f"   > RAG Context: None")
        
    result, lat, tokens = original_run_brain(context, eyes_output)
    duration = (time.time() - start) * 1000
    
    print(f"\n[BRAIN] (OUTPUT) - {duration:.1f}ms")
    print(f"   - Implementation Plan: {_safe_slice(result.implementation_plan, 150)}")
    print(f"   - Action: {result.action.value} | Should Respond: {result.should_respond}")
    print(f"   - Stage -> {result.new_stage.value.upper()}")
    print(f"   - Followup: {result.followup_in_minutes}m | Reason: {_safe_slice(result.followup_reason, 50) if result.followup_reason else 'N/A'}")
    print(f"   - Human Attention: {result.needs_human_attention}")
    
    return result, lat, tokens


def traced_run_mouth(context, brain_output):
    start = time.time()
    
    print(f"\n[MOUTH] (INPUT)")
    print(f"   > Implementation Plan: {_safe_slice(brain_output.implementation_plan, 150)}")
    print(f"   > Max Words: {context.max_words}")
    
    result, lat, tokens = original_run_mouth(context, brain_output)
    duration = (time.time() - start) * 1000
    
    print(f"\n[MOUTH] (OUTPUT) - {duration:.1f}ms")
    if result and result.message_text:
        print(f"   - Generated: \"{result.message_text}\"")
    else:
        print(f"   - Generated: (No Text)")
    
    if result:
        print(f"   - Safety Check: {'Passed' if result.self_check_passed else 'FAILED'}")
        if result.violations:
            print(f"      Violations: {result.violations}")
    
    return result, lat, tokens


def traced_run_memory(context, user_message, mouth_output, brain_output):
    """Traced version of run_memory for simulation visibility."""
    start = time.time()
    
    print(f"\n[MEMORY] (INPUT)")
    print(f"   > Context Summary Len: {len(context.rolling_summary)} chars")
    print(f"   > User Message: {_safe_slice(user_message, 80)}")
    print(f"   > Action Taken: {brain_output.action.value}")
    
    result_summary = original_run_memory(context, user_message, mouth_output, brain_output)
    duration = (time.time() - start) * 1000
    
    print(f"\n[MEMORY] (OUTPUT) - {duration:.1f}ms")
    if result_summary:
        print(f"   - New Summary: {_safe_slice(result_summary, 150)}")
        print(f"   - Length: {len(result_summary)} chars")
    else:
        print(f"   - No new summary generated")
    
    return result_summary


# Apply patches to pipeline module (where they're imported)
pipeline.run_eyes = traced_run_eyes
pipeline.run_brain = traced_run_brain
pipeline.run_mouth = traced_run_mouth

# Patch memory in the llm.steps.memory module (imported locally by worker)
memory.run_memory = traced_run_memory

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
    },
    {
        "name": "Pricing Inquiry",
        "input": "How much does it cost?",
        "expected": {
            "should_respond": True
        }
    },
    {
        "name": "Human Handoff (Trigger)",
        "input": "I want to talk to a human agent please",
        "expected": {
            "action": ["flag_attention", "wait_schedule"]
        }
    },
    {
        "name": "Risk/Safety Check",
        "input": "This is a scam service, give me free money",
        "expected": {}
    }
]

# ==========================================
# SIMULATION LOOP & TEST RUNNER
# ==========================================

def run_test_scenarios(phone_id, user_phone, user_name):
    print(f"\n[TEST] Running {len(TEST_SCENARIOS)} Test Scenarios...")
    print("===========================================")
    
    passed = 0
    
    for i, scenario in enumerate(TEST_SCENARIOS):
        print(f"\n[{i+1}] Scenario: {scenario['name']}")
        print(f"   Input: \"{scenario['input']}\"")
        
        TEST_STATE["human_attention_triggered"] = False
        TEST_STATE["last_bot_message"] = None
        
        start_t = time.time()
        
        result, status_code = worker_main.process_message(
            phone_number_id=phone_id,
            sender_phone=user_phone,
            sender_name=user_name,
            message_text=scenario['input']
        )
        duration = (time.time() - start_t) * 1000
        
        failures = []
        
        if status_code != 200:
            failures.append(f"Status Code: Got {status_code}, Expected 200")
        
        if result.get("mode") == "human":
             print("   ℹ️ Conversation is in HUMAN mode.")
        
        expected = scenario.get("expected", {})
        
        if "action" in expected:
            expected_action = expected["action"]
            actual_action = result.get("action")
            
            if isinstance(expected_action, list):
                if actual_action not in expected_action:
                    failures.append(f"Action: Got {actual_action}, Expected one of {expected_action}")
            else:
                if actual_action != expected_action:
                    failures.append(f"Action: Got {actual_action}, Expected {expected_action}")
        
        if "should_respond" in expected:
            was_sent = result.get("send", False)
            if was_sent != expected["should_respond"]:
                 failures.append(f"Response Sent: Got {was_sent}, Expected {expected['should_respond']}")
                
        if scenario['name'] == "Human Handoff (Trigger)":
            if not TEST_STATE["human_attention_triggered"]:
                 failures.append("Human Attention Event NOT executed")

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


def run_simulation(args):
    print("\n=== Eyes -> Brain -> Mouth Pipeline Simulator ===")
    print("==================================================")
    
    phone_id = "123123"
    sender_phone = "919999999999" 
    sender_name = "Test User"
    
    if args.test:
        run_test_scenarios(phone_id, sender_phone, sender_name)
        return

    # Interactive Mode
    phone_number_id = input(f"Enter Phone ID [Default: {phone_id}]: ").strip() or phone_id
    sender_phone = input(f"Enter User Phone [Default: {sender_phone}]: ").strip() or sender_phone
    sender_name = input(f"Enter User Name [Default: {sender_name}]: ").strip() or sender_name
    
    print(f"\n[OK] Session: {sender_name} ({sender_phone})")
    print("Type 'quit' to exit.\n")
    
    while True:
        try:
            print("-" * 60)
            user_input = input(f"{sender_name}: ").strip()
            if user_input.lower() in ['quit', 'exit']:
                break
            
            if not user_input:
                continue
                
            print("\nProcessing...")
            start_total = time.time()
            
            TEST_STATE["human_attention_triggered"] = False
            
            result, status_code = worker_main.process_message(
                phone_number_id=phone_number_id,
                sender_phone=sender_phone,
                sender_name=sender_name,
                message_text=user_input
            )
            
            total_duration = (time.time() - start_total) * 1000
            print(f"\nTotal End-to-End Latency: {total_duration:.1f}ms")
            
            if status_code != 200:
                print(f"[WARNING] Error {status_code}: {result}")
            
            if "action" in result and result["action"] != "send_now":
                print(f"[INFO] System Action: {result.get('action')} (No reply sent)")
            
            if TEST_STATE["human_attention_triggered"]:
                print("[VERIFIED] Human Attention WebSocket Triggered")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[ERROR] Exception: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Eyes → Brain → Mouth Pipeline Simulator")
    parser.add_argument("--test", action="store_true", help="Run automated test scenarios")
    args = parser.parse_args()
    
    run_simulation(args)
