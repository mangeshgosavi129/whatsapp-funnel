"""
WhatsApp Worker - Main Entry Point.
Long-polls SQS for incoming WhatsApp messages and processes them through HTL pipeline.
Refactored to be Async-first for robust LLM handling.
"""
import logging
import json
import time
import base64
import asyncio
from typing import Mapping, Tuple, Optional
from collections import defaultdict
from functools import partial
from uuid import UUID
import boto3
from whatsapp_worker.config import config
from whatsapp_worker.processors.context import build_pipeline_context
from whatsapp_worker.processors.actions import handle_pipeline_result
from whatsapp_worker.processors.api_client import api_client
from whatsapp_worker.security import validate_signature
from llm.pipeline import run_pipeline
from llm.steps.memory import run_memory
from server.enums import ConversationMode
from logging_config import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


# --- SQS Client Initialization ---
# boto3 is sync, so we keep it global but will run calls in threads
sqs = boto3.client(
    'sqs',
    region_name=config.AWS_REGION,
    aws_access_key_id=config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY
)

def start_worker():
    """Entry point for the worker."""
    logger.info("Starting Async Worker Loop...")
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
    except Exception as e:
        logger.critical(f"Worker crashed: {e}", exc_info=True)


async def worker_loop():
    """
    Infinite async loop to pull messages from SQS.
    """
    logger.info(f"HTL Worker listening on: {config.QUEUE_URL}")
    loop = asyncio.get_running_loop()

    while True:
        try:
            # Run blocking SQS receive in a separate thread
            response = await loop.run_in_executor(
                None,
                partial(
                    sqs.receive_message,
                    QueueUrl=config.QUEUE_URL,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=20,
                    VisibilityTimeout=60
                )
            )

            messages = response.get('Messages', [])
            if not messages:
                continue

            for message in messages:
                # Process each message concurrently?
                # For safety/ordering, we process sequentially per message for now,
                # but could use asyncio.create_task for parallelism.
                await process_sqs_message(message, loop)

        except Exception as e:
            logger.error(f"Worker Loop Error: {e}", exc_info=True)
            await asyncio.sleep(5)


async def process_sqs_message(message: dict, loop: asyncio.AbstractEventLoop):
    """Handle a single SQS message."""
    receipt_handle = message['ReceiptHandle']
    
    try:
        # Parse logic
        sqs_message = json.loads(message['Body'])
        body = sqs_message.get('body', {})
        headers = sqs_message.get('headers', {})
        raw_body_b64 = sqs_message.get('raw_body_b64')
        
        raw_body = base64.b64decode(raw_body_b64) if raw_body_b64 else None
        
        # Verify Signature
        if raw_body and headers:
            # CPU bound but fast, can stay in loop or move to thread if heavy
            is_valid = validate_signature(raw_body, headers)
            if not is_valid:
                logger.warning("Signature verification failed.")
                await loop.run_in_executor(
                    None, 
                    partial(sqs.delete_message, QueueUrl=config.QUEUE_URL, ReceiptHandle=receipt_handle)
                )
                return
        else:
             logger.warning("Missing raw_body/headers.")
             await loop.run_in_executor(
                None, 
                partial(sqs.delete_message, QueueUrl=config.QUEUE_URL, ReceiptHandle=receipt_handle)
            )
             return
        
        # Process Webhook
        result_body, status_code = await handle_webhook(body, loop)

        if status_code == 200:
            await loop.run_in_executor(
                None,
                partial(sqs.delete_message, QueueUrl=config.QUEUE_URL, ReceiptHandle=receipt_handle)
            )
        else:
            logger.warning(f"Processing failed {status_code}. Letting SQS retry.")
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON error: {e}")
    except Exception as e:
        logger.error(f"Message Error: {e}", exc_info=True)


async def handle_webhook(body: Mapping, loop: asyncio.AbstractEventLoop) -> Tuple[Mapping, int]:
    """Async webhook handler."""
    try:
        value = body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
        
        if value.get("statuses"):
            return {"status": "ok", "type": "status_update"}, 200

        messages = value.get("messages")
        if not messages:
            return {"status": "ok", "type": "no_messages"}, 200

        msg = messages[0]
        
        contacts = value.get("contacts", [])
        sender_phone = contacts[0].get("wa_id") if contacts else msg.get("from")
        sender_name = contacts[0].get("profile", {}).get("name") if contacts else None
        phone_number_id = value.get("metadata", {}).get("phone_number_id")
        
        if not sender_phone or not phone_number_id:
            return {"status": "error", "message": "Missing required fields"}, 400
        
        text_body = None
        if msg.get("type") == "text":
            text_body = msg["text"]["body"]
        
        if not text_body:
            return {"status": "ok", "type": "non_text"}, 200

        logger.info(f"Received from {sender_phone}: {text_body[:100]}...")
        
        return await process_message(
            phone_number_id=phone_number_id,
            sender_phone=sender_phone,
            sender_name=sender_name,
            message_text=text_body,
            loop=loop
        )
        
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500


async def process_message(
    phone_number_id: str,
    sender_phone: str,
    sender_name: Optional[str],
    message_text: str,
    loop: asyncio.AbstractEventLoop
) -> Tuple[Mapping, int]:
    """
    Process a message through the Router-Agent pipeline (Async).
    """
    try:
        # Step 1: Gather Info (Blocking sync calls wrapped in thread)
        def gather_info():
            org_result = api_client.get_integration_with_org(phone_number_id)
            if not org_result:
                raise ValueError("Organization not found")
            
            organization_id = UUID(org_result["organization_id"])
            access_token = org_result["access_token"]
            version = org_result["version"]
            
            lead = api_client.get_or_create_lead(organization_id, sender_phone, sender_name)
            lead_id = UUID(lead["id"])
            
            conversation, _ = api_client.get_or_create_conversation(organization_id, lead_id)
            conversation_id = UUID(conversation["id"])
            
            api_client.store_incoming_message(conversation_id, lead_id, message_text)
            
            # Refresh
            conversation = api_client.get_conversation(conversation_id)
            
            return org_result, organization_id, access_token, version, lead, lead_id, conversation, conversation_id

        # Run gather_info in executor
        try:
            org_result, organization_id, access_token, version, lead, lead_id, conversation, conversation_id = await loop.run_in_executor(None, gather_info)
        except ValueError as ve:
             return {"status": "error", "message": str(ve)}, 404

        # Step 2: Check Mode
        if conversation.get("mode") == ConversationMode.HUMAN.value:
            return {"status": "ok", "mode": "human"}, 200
        
        # Step 3: Run Async Pipeline
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
        
        # AWAIT PIPELINE
        pipeline_result = await run_pipeline(pipeline_context, message_text)
        
        # Step 4: Immediate Action (Send Message)
        response_text = None
        if pipeline_result.should_send_message and pipeline_result.response:
            response_text = pipeline_result.response.message_text
            try:
                # Wrap sending in thread
                await loop.run_in_executor(
                    None,
                    partial(
                        api_client.send_bot_message,
                        organization_id=organization_id,
                        conversation_id=conversation_id,
                        content=response_text,
                        access_token=access_token,
                        phone_number_id=phone_number_id,
                        version=version,
                        to=sender_phone,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to send WhatsApp message: {e}")

        # Step 5: Update State & Background Tasks
        
        # DB Update (Blocking)
        await loop.run_in_executor(
            None,
            partial(handle_pipeline_result, conversation, lead_id, pipeline_result)
        )
        
        # Background Summary (Async)
        if pipeline_result.needs_background_summary:
            new_summary = await run_memory(
                context=pipeline_context, 
                user_message=message_text,
                mouth_output=pipeline_result.mouth,
                brain_output=pipeline_result.brain
            )
            
            if new_summary:
                try:
                    await loop.run_in_executor(
                        None,
                        partial(api_client.update_conversation, conversation_id, rolling_summary=new_summary)
                    )
                    logger.info(f"Updated rolling summary for {conversation_id}")
                except Exception as e:
                    logger.error(f"Failed to save summary: {e}")

        return {
            "status": "ok",
            "action": pipeline_result.classification.action.value,
            "send": pipeline_result.should_send_message,
            "stage": pipeline_result.classification.new_stage.value,
        }, 200

    except Exception as e:
        logger.error(f"Message processing error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500


if __name__ == "__main__":
    start_worker()