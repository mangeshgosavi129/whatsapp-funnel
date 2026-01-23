"""
WhatsApp Worker - Main Entry Point.
Long-polls SQS for incoming WhatsApp messages and processes them through HTL pipeline.
"""
import logging
import json
import time
from typing import Mapping, Tuple, Optional
from collections import defaultdict
from threading import Lock
from uuid import UUID

import boto3

from whatsapp_worker.config import config
from whatsapp_worker.processors.context import build_pipeline_context
from whatsapp_worker.processors.actions import handle_pipeline_result
from whatsapp_worker.processors.api_client import api_client
from llm.pipeline import run_pipeline
from server.enums import ConversationMode, MessageFrom

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- SQS Client Initialization ---
sqs = boto3.client(
    'sqs',
    region_name=config.AWS_REGION,
    aws_access_key_id=config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY
)

# --- Message Debouncing ---
# Prevents processing rapid successive messages separately
_message_buffer: dict = defaultdict(list)
_buffer_lock = Lock()
DEBOUNCE_SECONDS = 5  # Wait 5 seconds for additional messages


def start_worker():
    """
    Infinite loop to pull messages from SQS and process them through HTL pipeline.
    """
    logger.info(f"HTL Worker started. Listening on: {config.QUEUE_URL}")

    while True:
        try:
            # Long Polling: Wait up to 20 seconds for a message
            response = sqs.receive_message(
                QueueUrl=config.QUEUE_URL,
                MaxNumberOfMessages=10,  # Process batch for efficiency
                WaitTimeSeconds=20,
                VisibilityTimeout=60  # Give more time for pipeline processing
            )

            messages = response.get('Messages', [])
            if not messages:
                continue

            for message in messages:
                receipt_handle = message['ReceiptHandle']
                
                try:
                    body = json.loads(message['Body'])
                    result_body, status_code = handle_webhook(body)

                    if status_code == 200:
                        sqs.delete_message(
                            QueueUrl=config.QUEUE_URL,
                            ReceiptHandle=receipt_handle
                        )
                    else:
                        logger.warning(f"Processing failed with {status_code}. Message will be retried.")
                        
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    # Don't delete - let SQS retry

        except Exception as e:
            logger.error(f"Worker Loop Error: {e}", exc_info=True)
            time.sleep(5)  # Cooldown before retrying


def handle_webhook(body: Mapping) -> Tuple[Mapping, int]:
    """
    Handle incoming WhatsApp webhook payload.
    
    This is the main entry point for processing WhatsApp messages.
    """
    try:
        # Parse webhook payload
        value = body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
        
        # Skip status updates (delivered, read, etc.)
        if value.get("statuses"):
            return {"status": "ok", "type": "status_update"}, 200

        # Get messages
        messages = value.get("messages")
        if not messages:
            return {"status": "ok", "type": "no_messages"}, 200

        # Process first message (usually only one)
        msg = messages[0]
        
        # Get sender info
        contacts = value.get("contacts", [])
        sender_phone = contacts[0].get("wa_id") if contacts else msg.get("from")
        sender_name = contacts[0].get("profile", {}).get("name") if contacts else None
        # TODO: Add name is probably not given in the payload

        # Get receiver (our client's WhatsApp number)
        phone_number_id = value.get("metadata", {}).get("phone_number_id")
        
        if not sender_phone or not phone_number_id:
            logger.warning("Missing sender_phone or phone_number_id")
            return {"status": "error", "message": "Missing required fields"}, 400
        
        # Extract message text
        text_body = None
        if msg.get("type") == "text":
            text_body = msg["text"]["body"]
        elif msg.get("type") == "button":
            text_body = msg["button"]["text"]
        elif msg.get("type") == "interactive":
            interactive = msg.get("interactive", {})
            if interactive.get("type") == "button_reply":
                text_body = interactive["button_reply"]["title"]
            elif interactive.get("type") == "list_reply":
                text_body = interactive["list_reply"]["title"]
        
        if not text_body:
            logger.info(f"Non-text message from {sender_phone}, type: {msg.get('type')}")
            return {"status": "ok", "type": "non_text"}, 200

        logger.info(f"Received from {sender_phone}: {text_body[:100]}...")
        
        # Process through HTL pipeline
        return process_message(
            phone_number_id=phone_number_id,
            sender_phone=sender_phone,
            sender_name=sender_name,
            message_text=text_body,
        )
        
    except Exception as e:
        logger.error(f"Webhook handling error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500


def process_message(
    phone_number_id: str,
    sender_phone: str,
    sender_name: Optional[str],
    message_text: str,
) -> Tuple[Mapping, int]:
    """
    Process a message through the HTL pipeline using API calls.
    """
    try:
        # ========================================
        # Step 1: Gather Information via API
        # ========================================
        
        # Get organization from phone_number_id
        org_result = api_client.get_integration_with_org(phone_number_id)
        if not org_result:
            logger.error(f"No organization found for phone_number_id: {phone_number_id}")
            return {"status": "error", "message": "Organization not found"}, 404
        
        organization_id = UUID(org_result["organization_id"])
        organization_name = org_result["organization_name"]
        access_token = org_result["access_token"]
        version = org_result["version"]
        
        # Get or create lead
        lead = api_client.get_or_create_lead(organization_id, sender_phone, sender_name)
        lead_id = UUID(lead["id"])
        
        # Get or create conversation
        conversation, is_new_conversation = api_client.get_or_create_conversation(
            organization_id, lead_id
        )
        conversation_id = UUID(conversation["id"])
        
        # Store incoming message
        api_client.store_incoming_message(conversation, lead, message_text)
        
        # Refresh conversation data after storing message (timestamps updated)
        conversation = api_client.get_conversation(conversation_id)
        
        logger.info(f"Processing for org={organization_name}, conv={conversation_id}, mode={conversation.get('mode')}")
        
        # ========================================
        # Step 2: Check Mode (Bot vs Human)
        # ========================================
        
        if conversation.get("mode") == ConversationMode.HUMAN.value:
            # Human has taken over - just store message, don't run pipeline
            logger.info(f"Conversation {conversation_id} is in HUMAN mode, skipping pipeline")
            # TODO: Send WebSocket notification to frontend
            return {"status": "ok", "mode": "human", "message_stored": True}, 200
        
        # ========================================
        # Step 3: Run HTL Pipeline
        # ========================================
        
        # Build pipeline context
        pipeline_context = build_pipeline_context(
            organization_name, conversation, lead
        )
        
        # Run the pipeline
        logger.info(f"Running HTL pipeline for conversation {conversation_id}")
        pipeline_result = run_pipeline(pipeline_context, message_text)
        
        logger.info(
            f"Pipeline result: action={pipeline_result.decision.action.value}, "
            f"send={pipeline_result.should_send_message}, "
            f"latency={pipeline_result.pipeline_latency_ms}ms"
        )
        
        # ========================================
        # Step 4: Execute Actions
        # ========================================
        
        response_message = handle_pipeline_result(
            conversation, lead_id, pipeline_result
        )
        
        if response_message:
            # Send and store via API
            try:
                api_client.send_bot_message(
                    organization_id=organization_id,
                    conversation_id=conversation_id,
                    content=response_message,
                    access_token=access_token,
                    phone_number_id=phone_number_id,
                    version=version,
                    to=sender_phone,
                )
                logger.info(f"Sent response to {sender_phone}: {response_message[:50]}...")
            except Exception as e:
                logger.error(f"Failed to send WhatsApp message via API: {e}", exc_info=True)
                # If API fails, message might not be stored or sent
        
        return {
            "status": "ok",
            "action": pipeline_result.decision.action.value,
            "send": pipeline_result.should_send_message,
            "stage": pipeline_result.decision.next_stage.value,
        }, 200
        
    except Exception as e:
        logger.error(f"Message processing error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500


if __name__ == "__main__":
    start_worker()