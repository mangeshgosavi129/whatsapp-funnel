"""
WhatsApp Worker - Main Entry Point.
Long-polls SQS for incoming WhatsApp messages and processes them through HTL pipeline.
"""
import logging
import json
import time
import base64
from typing import Mapping, Tuple, Optional
from collections import defaultdict
from threading import Lock
from uuid import UUID
import boto3
from whatsapp_worker.config import config
from whatsapp_worker.processors.context import build_pipeline_context
from whatsapp_worker.processors.actions import handle_pipeline_result
from whatsapp_worker.processors.api_client import api_client
from whatsapp_worker.security import validate_signature
from llm.pipeline import run_pipeline
from server.enums import ConversationMode
from logging_config import setup_logging

# Configure logging
setup_logging()
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
                    # Parse the new message format with raw_body and headers
                    sqs_message = json.loads(message['Body'])
                    
                    # Extract components
                    body = sqs_message.get('body', {})
                    headers = sqs_message.get('headers', {})
                    raw_body_b64 = sqs_message.get('raw_body_b64')
                    
                    # Decode raw body from base64
                    raw_body = base64.b64decode(raw_body_b64) if raw_body_b64 else None
                    
                    # Verify signature before processing
                    if raw_body and headers:
                        if not validate_signature(raw_body, headers):
                            logger.warning("Signature verification failed. Deleting message from queue.")
                            sqs.delete_message(
                                QueueUrl=config.QUEUE_URL,
                                ReceiptHandle=receipt_handle
                            )
                            continue
                    else:
                        logger.warning("Missing raw_body or headers for signature verification. Deleting message.")
                        sqs.delete_message(
                            QueueUrl=config.QUEUE_URL,
                            ReceiptHandle=receipt_handle
                        )
                        continue
                    
                    # Signature verified - proceed with processing
                    result_body, status_code = handle_webhook(body)

                    if status_code == 200:
                        sqs.delete_message(
                            QueueUrl=config.QUEUE_URL,
                            ReceiptHandle=receipt_handle
                        )
                    else:
                        logger.warning(f"Processing failed with {status_code}. Message will be retried.")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}. Body: {message.get('Body')}")
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
    Process a message through the Router-Agent pipeline.
    """
    try:
        # ========================================
        # Step 1: Gather Information via API
        # ========================================
        
        # Get organization
        org_result = api_client.get_integration_with_org(phone_number_id)
        if not org_result:
            return {"status": "error", "message": "Organization not found"}, 404
        
        organization_id = UUID(org_result["organization_id"])
        access_token = org_result["access_token"]
        version = org_result["version"]
        
        # Get/Create Lead & Conversation
        lead = api_client.get_or_create_lead(organization_id, sender_phone, sender_name)
        lead_id = UUID(lead["id"])
        
        conversation, _ = api_client.get_or_create_conversation(organization_id, lead_id)
        conversation_id = UUID(conversation["id"])
        
        # Store User Message
        api_client.store_incoming_message(conversation_id, lead_id, message_text)
        
        
        # Refresh conversation (timestamps)
        conversation = api_client.get_conversation(conversation_id)
        
        # ========================================
        # Step 2: Check Mode
        # ========================================
        
        if conversation.get("mode") == ConversationMode.HUMAN.value:
            return {"status": "ok", "mode": "human"}, 200
        
        # ========================================
        # Step 3: Run Pipeline (Generate)
        # ========================================
        
        pipeline_context = build_pipeline_context(
            {
                "organization_id": str(organization_id),
                "organization_name": org_result["organization_name"],
                "business_name": org_result.get("business_name"),
                "business_description": org_result.get("business_description"),
                "flow_prompt": org_result.get("flow_prompt"),
            }, 
            conversation, 
            lead
        )
        
        pipeline_result = run_pipeline(pipeline_context, message_text)
        
        # ========================================
        # Step 4: Immediate Action (Send Message)
        # ========================================
        
        response_text = None
        if pipeline_result.should_send_message and pipeline_result.generate:
            response_text = pipeline_result.generate.message_text
            try:
                # SEND TO WHATSAPP FIRST (Low Latency)
                api_client.send_bot_message(
                    organization_id=organization_id,
                    conversation_id=conversation_id,
                    content=response_text,
                    access_token=access_token,
                    phone_number_id=phone_number_id,
                    version=version,
                    to=sender_phone,
                )
            except Exception as e:
                logger.error(f"Failed to send WhatsApp message: {e}", exc_info=True)
                # We continue to update state even if send failed, to record intention

        # ========================================
        # Step 5: Update State & Background Tasks
        # ========================================

        # Update Conversation State (Stage, Intent, etc.)
        handle_pipeline_result(conversation, lead_id, pipeline_result)
        
        # Background Summary (The Memory)
        if pipeline_result.needs_background_summary:
            from llm.steps.memory import run_memory
            
            # Run summary generation
            new_summary = run_memory(
                context=pipeline_context, 
                user_message=message_text,
                generate_output=pipeline_result.generate,
            )
            
            # Update DB with new summary if generated
            if new_summary:
                try:
                    # We only update the summary here. Other fields handled by handle_pipeline_result.
                    api_client.update_conversation(conversation_id, rolling_summary=new_summary)
                    logger.info(f"Updated rolling summary for {conversation_id}")
                except Exception as e:
                    logger.error(f"Failed to save summary to DB: {e}")

        return {
            "status": "ok",
            "status": "ok",
            "action": pipeline_result.generate.action.value,
            "send": pipeline_result.should_send_message,
            "stage": pipeline_result.generate.new_stage.value,
        }, 200

    except Exception as e:
        logger.error(f"Message processing error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500


if __name__ == "__main__":
    start_worker()