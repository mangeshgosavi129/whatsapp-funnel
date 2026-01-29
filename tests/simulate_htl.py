import sys
import os
import asyncio
import logging
from unittest.mock import MagicMock
from uuid import uuid4

# Add project root to path
sys.path.append(os.getcwd())

# === CUSTOM LOGGING FOR SIMULATION ===
class ColorFormatter(logging.Formatter):
    """Custom formatter to highlight HTL steps."""
    
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    blue = "\x1b[34;20m"
    green = "\x1b[32;20m"
    reset = "\x1b[0m"
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: grey + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        
        # Highlight HTL steps
        msg = record.msg
        if isinstance(msg, str):
            if "Running Step 1: Analyze" in msg:
                log_fmt = self.blue + "%(message)s" + self.reset
            elif "Running Step 2: Decide" in msg:
                log_fmt = self.blue + "%(message)s" + self.reset
            elif "Running Step 3: Generate" in msg:
                log_fmt = self.green + "%(message)s" + self.reset
            elif "Pipeline result: action=" in msg:
                log_fmt = self.yellow + "%(message)s" + self.reset
        
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# Configure logging
handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])

# Quiet down some loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

from whatsapp_worker import main as worker_main
from whatsapp_worker.processors.api_client import api_client
from llm.config import llm_config

# Debug: Check LLM Config
api_key_display = f"{llm_config.api_key[:10]}...{llm_config.api_key[-4:]}" if llm_config.api_key else "NOT SET"
groq_env = os.environ.get('GROQ_API_KEY', '')
groq_env_display = f"{groq_env[:5]}..." if groq_env else "Not Set"
print(f"\n🐛 DEBUG: Local Simulator Config Check")
print(f"   API Key: {api_key_display}")
print(f"   Model: {llm_config.model or 'NOT SET'}")
print(f"   Base URL: {llm_config.base_url or 'NOT SET'}")
print(f"   Env Var GROQ_API_KEY: {groq_env_display}\n")

# ==========================================
# MOCK / PATCH SETTINGS
# ==========================================

# We want to intercept the final "send" call so we don't need a real WhatsApp API
# but we DO want to persist the conversation updates.

original_send_bot_message = api_client.send_bot_message

def mocked_send_bot_message(organization_id, conversation_id, content, *args, **kwargs):
    print("\n" + "="*60)
    print(f"🤖 BOT RESPONSE (Mocked Send): {content}")
    print("="*60 + "\n")
    
    # We still want to "store" this message in the DB so context is preserved for the next turn
    # The original send_bot_message does: API call -> Server sends to Meta -> Server saves to DB.
    # Since we skip the server call, we must manually tell the server to store this outgoing message.
    
    # Note: Access token/phone_id doesn't matter here since we are mocking the external send
    # but we need to store it as "sent" in the DB.
    
    # Retrieve lead_id from conversation to store message correctly
    # detailed way would be fetching conversation first, but let's try to just store it.
    
    # To keep it simple, we will just use the internal "store_outgoing_message" endpoint
    # which is normally used by the server, but we can use it here to simulate "sent".
    
    try:
        # We need lead_id. 
        # Since we don't have it handy in arguments, let's fetch the conversation 
        conv = api_client.get_conversation(conversation_id)
        lead_id = conv['lead_id']
        
        api_client.store_outgoing_message(
            conversation_id=conversation_id,
            lead_id=lead_id,
            content=content,
            message_from="bot"
        )
        print("✅ Message stored in DB (Context updated)")
    except Exception as e:
        print(f"❌ Failed to store bot message in DB: {e}")

    return {"status": "mocked_success"}

# Patch the client
api_client.send_bot_message = mocked_send_bot_message

# ==========================================
# SIMULATION LOOP
# ==========================================

def run_simulation():
    print("🚀 WhatsApp HTL Pipeline Simulator")
    print("----------------------------------")
    print("Pre-requisite: Ensure 'uvicorn server.main:app' is running on localhost:8000")
    print("Pre-requisite: Ensure you have at least one Organization and WhatsAppIntegration in your local DB.")
    
    # 1. Setup Identity
    print("\n--- Configuration ---")
    phone_number_id = input("Enter a Phone Number ID (from your DB): ").strip()
    if not phone_number_id:
        # Default fallback for lazy testing if they set up the seed
        phone_number_id = "100609346426084" 
        print(f"Using default Phone Number ID: {phone_number_id}")

    sender_phone = input("Enter your simulated phone number (e.g. 919876543210): ").strip() or "919999999999"
    sender_name = input("Enter your name: ").strip() or "Test User"
    
    print(f"\n✅ Session started for {sender_name} ({sender_phone})")
    print("Type 'quit' or 'exit' to stop.\n")
    
    while True:
        try:
            user_input = input(f"👤 {sender_name}: ").strip()
            if user_input.lower() in ['quit', 'exit']:
                break
            
            if not user_input:
                continue
                
            print("... (Processing) ...")
            
            # Run the worker logic directly
            result, status_code = worker_main.process_message(
                phone_number_id=phone_number_id,
                sender_phone=sender_phone,
                sender_name=sender_name,
                message_text=user_input
            )
            
            if status_code != 200:
                print(f"⚠️ Error {status_code}: {result}")
            
            # If no message sent (e.g. wait/handoff), print that status
            if "action" in result and result["action"] != "send_now":
                print(f"ℹ️ System Action: {result.get('action')} (No reply sent)")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Exception: {e}")

if __name__ == "__main__":
    run_simulation()
