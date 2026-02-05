import sys
import os
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
    """Custom formatter to highlight HTL steps."""
    
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    cyan = "\x1b[36;20m"
    green = "\x1b[32;20m"
    purple = "\x1b[35;20m"
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
            if "🧠" in msg:
                log_fmt = self.purple + "%(message)s" + self.reset
            elif "🗣️" in msg:
                log_fmt = self.cyan + "%(message)s" + self.reset
            elif "⏱️" in msg:
                log_fmt = self.green + "%(message)s" + self.reset
            elif "Bot:" in msg:
                log_fmt = self.yellow + "%(message)s" + self.reset
        
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# Configure logging
handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)

# Quiet down some loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("whatsapp_worker.main").setLevel(logging.CRITICAL) # Silence worker main loop noise
# process_actions logger is useful for debugging now
logging.getLogger("whatsapp_worker.processors.actions").setLevel(logging.DEBUG) 

from whatsapp_worker import main as worker_main
from whatsapp_worker.processors.api_client import api_client
from llm.schemas import ClassifyOutput, GenerateOutput
from llm import pipeline  # Direct import
from llm.steps import brain, mouth # Direct import

# Need to import prompt components for reconstruction
from llm.prompts import BRAIN_SYSTEM_PROMPT
from llm.steps.brain import _build_user_prompt as build_brain_user_prompt
from llm.prompts_registry import get_mouth_system_prompt
from llm.steps.mouth import _build_user_prompt as build_mouth_user_prompt

# ==========================================
# 🕵️ MONKEY PATCHING FOR TRACING
# ==========================================

original_run_brain = brain.run_brain
original_run_mouth = mouth.run_mouth

def traced_run_brain(context):
    start = time.time()
    
    # Reconstruct Prompt for Logs
    print(f"\n🧠 [THE BRAIN] (INPUT TOKENS)")
    print(f"   ► SYSTEM PROMPT:\n{'-'*20}\n{BRAIN_SYSTEM_PROMPT[:300]}...\n(truncated)\n{'-'*20}")
    try:
        user_p = build_brain_user_prompt(context, is_opening=False) # Simplified for logs
        print(f"   ► USER PROMPT:\n{'-'*20}\n{user_p}\n{'-'*20}")
    except Exception as e:
        print(f"   [Error reconstructing prompt: {e}]")
        
    result, lat, tokens = original_run_brain(context)
    duration = (time.time() - start) * 1000
    
    # Pretty Print Brain Output
    print(f"\n🧠 [THE BRAIN] (OUTPUT) - {duration:.1f}ms")
    print(f"   ├─ Thought Process: {result.thought_process}")
    print(f"   ├─ Situation: {result.situation_summary}")
    print(f"   ├─ Intent: {result.intent_level.value} | Sentiment: {result.user_sentiment.value}")
    print(f"   ├─ Risks: Spam={result.risk_flags.spam_risk.value} | Policy={result.risk_flags.policy_risk.value}")
    print(f"   ├─ Action: {result.action.value} | Followup: {result.followup_in_minutes}m")
    print(f"   └─ Decision: Stage -> {result.new_stage.value.upper()}")
    
    return result, lat, tokens

def traced_run_mouth(context, classification):
    start = time.time()
    
    # Reconstruct Prompts for Logs
    print(f"\n🗣️ [THE MOUTH] (INPUT TOKENS)")
    try:
        sys_p = get_mouth_system_prompt(
            stage=classification.new_stage,
            business_name=context.business_name,
            flow_prompt=context.flow_prompt,
            max_words=context.max_words
        )
        print(f"   ► SYSTEM PROMPT (Stage: {classification.new_stage.value}):\n{'-'*20}\n{sys_p}\n{'-'*20}")
        
        user_p = build_mouth_user_prompt(context, classification)
        print(f"   ► USER PROMPT:\n{'-'*20}\n{user_p}\n{'-'*20}")
    except Exception as e:
        print(f"   [Error reconstructing prompt: {e}]")
    
    result, lat, tokens = original_run_mouth(context, classification)
    duration = (time.time() - start) * 1000
    
    # Pretty Print Mouth Output
    print(f"\n🗣️ [THE MOUTH] (OUTPUT) - {duration:.1f}ms")
    if result and result.message_text:
        print(f"   ├─ Generated: \"{result.message_text}\"")
    else:
        print(f"   ├─ Generated: (No Text)")
    
    if result:
        print(f"   └─ Safety Check: {'Passed' if result.self_check_passed else 'FAILED'}")
    
    return result, lat, tokens

# Apply patches
pipeline.run_brain = traced_run_brain
pipeline.run_mouth = traced_run_mouth

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
    """
    Isolated mock: logs and stores message in DB, but does NOT call real WhatsApp API.
    """
    print(f"\n🤖 Bot: \"{content}\"")
    TEST_STATE["last_bot_message"] = content
    
    # Store message in DB for visibility, but skip WhatsApp send
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
        print(f"❌ Failed to store bot message in DB: {e}")

    return {"status": "simulated_success"}

def mocked_emit_human_attention(conversation_id, organization_id):
    """
    Calls REAL internal API to trigger WebSocket event for frontend visibility.
    """
    print(f"\n🚨 [Simulation->Real] Human Attention Event for Conv {conversation_id}!")
    TEST_STATE["human_attention_triggered"] = True
    
    # Call real internal API (does NOT touch WhatsApp, just internal server)
    try:
        return original_emit_human_attention(conversation_id, organization_id)
    except Exception as e:
        print(f"❌ emit_human_attention failed: {e}")
        return {"status": "error", "error": str(e)}

# IMPORTANT: We must patch the api_client instance used by the worker modules!
# Since python modules are cached, we need to inspect where it's used.
# whatsapp_worker.processors.actions imports 'api_client'.
import whatsapp_worker.processors.actions as actions_module
actions_module.api_client.emit_human_attention = mocked_emit_human_attention
actions_module.api_client.send_bot_message = mocked_send_bot_message
# Also patch the local import just in case
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
            "action": "flag_attention"
        }
    },
    {
        "name": "Risk/Safety Check",
        "input": "This is a scam service, give me free money",
        "expected": {
            # We don't enforce response=False because bot might reply "We are legit".
            # We just want to check it runs through.
        }
    }
]

# ==========================================
# SIMULATION LOOP & TEST RUNNER
# ==========================================

def run_test_scenarios(phone_id, user_phone, user_name):
    print(f"\n🧪 Running {len(TEST_SCENARIOS)} Test Scenarios...")
    print("===========================================")
    
    passed = 0
    
    for i, scenario in enumerate(TEST_SCENARIOS):
        print(f"\n🔸 Scenario {i+1}: {scenario['name']}")
        print(f"   Input: \"{scenario['input']}\"")
        
        # Reset Test State
        TEST_STATE["human_attention_triggered"] = False
        TEST_STATE["last_bot_message"] = None
        
        # Run Pipeline
        start_t = time.time()
        
        result, status_code = worker_main.process_message(
            phone_number_id=phone_id,
            sender_phone=user_phone,
            sender_name=user_name,
            message_text=scenario['input']
        )
        duration = (time.time() - start_t) * 1000
        
        # Validation
        failures = []
        
        if status_code != 200:
            failures.append(f"Status Code: Got {status_code}, Expected 200")
        
        # Check Mode
        if result.get("mode") == "human":
             print("   ℹ️ Conversation is in HUMAN mode.")
        
        expected = scenario.get("expected", {})
        
        if "action" in expected:
            if result.get("action") != expected["action"]:
                failures.append(f"Action: Got {result.get('action')}, Expected {expected['action']}")
        
        if "should_respond" in expected:
            was_sent = result.get("send", False)
            if was_sent != expected["should_respond"]:
                 failures.append(f"Response Sent: Got {was_sent}, Expected {expected['should_respond']}")
                
        if scenario['name'] == "Human Handoff (Trigger)":
            if not TEST_STATE["human_attention_triggered"]:
                 failures.append("Human Attention Event NOT executed")

        if not failures:
            print(f"   ✅ PASS ({duration:.1f}ms)")
            passed += 1
        else:
            print(f"   ❌ FAIL ({duration:.1f}ms)")
            for f in failures:
                print(f"      - {f}")
                
    print(f"\n{'-'*30}")
    print(f"Results: {passed}/{len(TEST_SCENARIOS)} Passed")
    print(f"{'-'*30}\n")


def run_simulation(args):
    print("\n🚀 WhatsApp Router-Agent Simulator")
    print("==================================")
    
    # 1. Setup Identity
    # Use args or defaults
    phone_id = "123123" # User provided phone ID matching their frontend session
    sender_phone = "919999999999" 
    sender_name = "Test User"
    
    if args.test:
        run_test_scenarios(phone_id, sender_phone, sender_name)
        return

    # Interactive Mode
    phone_number_id = input(f"Enter Phone ID [Default: {phone_id}]: ").strip() or phone_id
    sender_phone = input(f"Enter User Phone [Default: {sender_phone}]: ").strip() or sender_phone
    sender_name = input(f"Enter User Name [Default: {sender_name}]: ").strip() or sender_name
    
    print(f"\n✅ Session: {sender_name} ({sender_phone})")
    print("Type 'quit' to exit.\n")
    
    while True:
        try:
            print("-" * 60)
            user_input = input(f"👤 {sender_name}: ").strip()
            if user_input.lower() in ['quit', 'exit']:
                break
            
            if not user_input:
                continue
                
            print("\n⏳ Processing...")
            start_total = time.time()
            
            # Reset mocks
            TEST_STATE["human_attention_triggered"] = False
            
            # Run the worker logic directly
            result, status_code = worker_main.process_message(
                phone_number_id=phone_number_id,
                sender_phone=sender_phone,
                sender_name=sender_name,
                message_text=user_input
            )
            
            total_duration = (time.time() - start_total) * 1000
            print(f"\n⏱️ Total End-to-End Latency: {total_duration:.1f}ms")
            
            if status_code != 200:
                print(f"⚠️ Error {status_code}: {result}")
            
            # If no message sent (e.g. wait/handoff), print that status
            if "action" in result and result["action"] != "send_now":
                print(f"ℹ️ System Action: {result.get('action')} (No reply sent)")
            
            if TEST_STATE["human_attention_triggered"]:
                print("🚨 [VERIFIED] Human Attention WebSocket Triggered")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Exception: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HTL Pipeline Simulator")
    parser.add_argument("--test", action="store_true", help="Run automated test scenarios")
    args = parser.parse_args()
    
    run_simulation(args)
