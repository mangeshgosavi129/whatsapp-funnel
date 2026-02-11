
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
from llm.schemas import GenerateOutput
from llm import pipeline
from llm.steps import generate, memory
from llm.prompts import (
    GENERATE_SYSTEM_PROMPT, GENERATE_USER_TEMPLATE
)

def print_simulation_steps():
    """Prints the steps of the simulation/pipeline flow."""
    print("\n" + "="*60)
    print("SIMULATION FLOW STEPS:")
    print("1. [WEBHOOK] Incoming message received in worker.main.handle_webhook")
    print("2. [CONTEXT] Worker builds PipelineInput using conversation/lead data")
    print("3. [RAG] Pipeline runs search_knowledge to get relevant context")
    print("4. [GENERATE] Pipeline runs run_generate (Observation -> Decision -> Response)")
    print("5. [ACTION] Worker sends message to WhatsApp if should_respond=True")
    print("6. [STATE] Worker updates conversation state (stage, intent, etc.)")
    print("7. [MEMORY] Worker runs run_memory in background to update rolling summary")
    print("="*60 + "\n")


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
            if "GENERATE" in msg:
                log_fmt = self.purple + "%(message)s" + self.reset
            elif "RAG" in msg:
                log_fmt = self.blue + "%(message)s" + self.reset
            elif "Response:" in msg:
                log_fmt = self.cyan + "%(message)s" + self.reset
            elif "Latency:" in msg:
                log_fmt = self.green + "%(message)s" + self.reset
            elif "Bot:" in msg:
                log_fmt = self.yellow + "%(message)s" + self.reset
        
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# Configure logging with UTF-8 encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

root_logger = logging.getLogger()
for h in root_logger.handlers[:]:
    root_logger.removeHandler(h)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColorFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("whatsapp_worker.main").setLevel(logging.INFO)  # Enabled for debugging
logging.getLogger("whatsapp_worker.processors.actions").setLevel(logging.DEBUG)

llm_log = logging.getLogger("llm")
llm_log.setLevel(logging.CRITICAL)  # Only log critical errors
llm_log.handlers.clear()
llm_log.propagate = False 


# ==========================================
# MONKEY PATCHING FOR TRACING
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


original_run_generate = generate.run_generate
original_run_memory = memory.run_memory


def traced_run_generate(context):
    start = time.time()
    
    print(f"\n[GENERATE] (INPUT)")
    print(f"   > Stage: {context.conversation_stage.value}")
    print(f"   > Intent: {context.intent_level.value} | Sentiment: {context.user_sentiment.value}")
    print(f"   > Messages: {len(context.last_messages)}")
    if context.last_messages:
        for msg in context.last_messages[-5:]:
            print(f"      [{msg.sender}] {_safe_slice(msg.text, 100)}")

    # Trace RAG Context if present
    if hasattr(context, 'dynamic_knowledge_context') and context.dynamic_knowledge_context:
        print(f"   > RAG Context Injected: Yes ({len(context.dynamic_knowledge_context)} chars)")
        if VERBOSE:
             print(f"   --> {_safe_slice(context.dynamic_knowledge_context, 200).replace('\n', ' ')}")
    else:
        print(f"   > RAG Context: None")
        
    result, lat, tokens = original_run_generate(context)
    duration = (time.time() - start) * 1000
    
    print(f"\n[GENERATE] (OUTPUT) - {duration:.1f}ms")
    print(f"   - Thought Process: {_safe_slice(result.thought_process, 200)}")
    print(f"   - Intent: {result.intent_level.value} | Sentiment: {result.user_sentiment.value}")
    print(f"   - Risks: Spam={result.risk_flags.spam_risk.value} | Policy={result.risk_flags.policy_risk.value}")
    print(f"   - Action: {result.action.value} -> {result.new_stage.value.upper()}")
    print(f"   - Should Respond: {result.should_respond}")
    if result.message_text:
        print(f"   - Message: \"{result.message_text}\"")
    
    return result, lat, tokens


def traced_search_knowledge(query, organization_id, **kwargs):
    """Traced version of search_knowledge."""
    start = time.time()
    print(f"\n[RAG] (SEARCH)")
    print(f"   > Query: {query}")
    
    results = original_search_knowledge(query, organization_id, **kwargs)
    duration = (time.time() - start) * 1000
    
    print(f"\n[RAG] (RESULTS) - {duration:.1f}ms")
    if results:
        print(f"   > Found {len(results)} chunks")
        for i, res in enumerate(results):
            print(f"   [{i+1}] {res.get('title', 'Unknown')} (Score: {res.get('score', 0.0):.4f})")
    else:
        print(f"   > No results found")
        
    return results

def traced_run_memory(context, user_message, generate_output):
    start = time.time()
    
    print(f"\n[MEMORY] (INPUT)")
    print(f"   > Context Summary Len: {len(context.rolling_summary)} chars")
    
    result_summary = original_run_memory(context, user_message, generate_output)
    duration = (time.time() - start) * 1000
    
    print(f"\n[MEMORY] (OUTPUT) - {duration:.1f}ms")
    if result_summary:
        print(f"   - New Summary: {_safe_slice(result_summary, 150)}")
    else:
        print(f"   - No new summary generated")
    
    return result_summary

# Apply patches to both the module itself and where it might be imported
pipeline.search_knowledge = traced_search_knowledge
llm.pipeline.search_knowledge = traced_search_knowledge

generate.run_generate = traced_run_generate
llm.pipeline.run_generate = traced_run_generate  # The pipeline module uses run_generate

memory.run_memory = traced_run_memory
# worker_main imports run_memory directly from llm.steps.memory
import llm.steps.memory
llm.steps.memory.run_memory = traced_run_memory


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
    print(f"\n[BOT]: \"{content}\"")
    TEST_STATE["last_bot_message"] = content
    return {"status": "simulated_success"}


def mocked_emit_human_attention(conversation_id, organization_id):
    print(f"\n[ALERT] Human Attention Event for Conv {conversation_id}!")
    TEST_STATE["human_attention_triggered"] = True
    return {"status": "success"}


def mocked_get_integration_with_org(phone_id):
    return {
        "organization_id": str(uuid4()),
        "access_token": "mock_token",
        "version": "v17.0",
        "organization_name": "Test Org",
        "business_name": "Test Business",
        "business_description": "A test business for simulation",
        "flow_prompt": "Help the user with their inquiry."
    }

def mocked_get_or_create_lead(org_id, phone, name):
    return {"id": str(uuid4()), "phone": phone, "name": name}

def mocked_get_or_create_conversation(org_id, lead_id):
    return {"id": str(uuid4()), "rolling_summary": "", "mode": "bot"}, True

def mocked_get_conversation(conv_id):
    return {"id": str(conv_id), "rolling_summary": "", "mode": "bot"}

def mocked_store_incoming_message(conv_id, lead_id, text):
    return {"status": "success"}

def mocked_update_conversation(conv_id, **kwargs):
    return {"status": "success"}

def mocked_update_lead(lead_id, **kwargs):
    return {"status": "success"}

def mocked_get_organization_ctas(org_id):
    return []

def mocked_emit_cta_initiated(conversation_id, organization_id, cta_type, **kwargs):
    print(f"\n[EVENT] CTA {cta_type} initiated!")
    return {"status": "success"}

def mocked_log_pipeline_event(conversation_id, **kwargs):
    return {"status": "success"}

def mocked_store_outgoing_message(conv_id, lead_id, content, message_from):
    return {"status": "success"}

def mocked_get_conversation_messages(conv_id, limit=3):
    return []

api_client.get_integration_with_org = mocked_get_integration_with_org
api_client.get_or_create_lead = mocked_get_or_create_lead
api_client.get_or_create_conversation = mocked_get_or_create_conversation
api_client.get_conversation = mocked_get_conversation
api_client.store_incoming_message = mocked_store_incoming_message
api_client.update_conversation = mocked_update_conversation
api_client.emit_human_attention = mocked_emit_human_attention
api_client.send_bot_message = mocked_send_bot_message
api_client.update_lead = mocked_update_lead
api_client.get_organization_ctas = mocked_get_organization_ctas
api_client.emit_cta_initiated = mocked_emit_cta_initiated
api_client.log_pipeline_event = mocked_log_pipeline_event
api_client.store_outgoing_message = mocked_store_outgoing_message
api_client.get_conversation_messages = mocked_get_conversation_messages

actions_module.api_client.emit_human_attention = mocked_emit_human_attention
actions_module.api_client.send_bot_message = mocked_send_bot_message
actions_module.api_client.update_conversation = mocked_update_conversation
actions_module.api_client.update_lead = mocked_update_lead
actions_module.api_client.get_organization_ctas = mocked_get_organization_ctas
actions_module.api_client.emit_cta_initiated = mocked_emit_cta_initiated
actions_module.api_client.log_pipeline_event = mocked_log_pipeline_event


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
    }
]

def run_test_scenarios(phone_id, user_phone, user_name):
    print(f"\n[TEST] Running {len(TEST_SCENARIOS)} Test Scenarios...")
    
    passed = 0
    for i, scenario in enumerate(TEST_SCENARIOS):
        print(f"\n[{i+1}] Scenario: {scenario['name']}")
        print(f"   Input: \"{scenario['input']}\"")
        
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
            failures.append(f"Status Code: {status_code}. Result: {result}")
        
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
                
    print(f"\nResults: {passed}/{len(TEST_SCENARIOS)} Passed")


def run_simulation(args):
    print_simulation_steps()
    print("\n=== Unified Pipeline Simulator ===")
    
    phone_id = "123123"
    sender_phone = "919999999999" 
    sender_name = "Test User"
    
    if args.test:
        run_test_scenarios(phone_id, sender_phone, sender_name)
        return

    # Interactive Mode
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
            
            result, status_code = worker_main.process_message(
                phone_number_id=phone_id,
                sender_phone=sender_phone,
                sender_name=sender_name,
                message_text=user_input
            )
            
            total_duration = (time.time() - start_total) * 1000
            print(f"\nLatency: {total_duration:.1f}ms")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[ERROR] Exception: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Unified Pipeline Simulator")
    parser.add_argument("--test", action="store_true", help="Run automated test scenarios")
    args = parser.parse_args()
    
    run_simulation(args)
