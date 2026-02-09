"""
Celery Tasks for HTL Pipeline.
Handles scheduled follow-ups and periodic maintenance via API calls.
"""
import logging
from uuid import UUID
from celery import Celery
from whatsapp_worker.processors.api_client import api_client
from whatsapp_worker.processors.context import build_pipeline_context
from whatsapp_worker.processors.actions import handle_pipeline_result
from llm.pipeline import run_followup_pipeline
from server.enums import ConversationStage
from whatsapp_worker.config import config
from logging_config import setup_logging

# Configure logging
setup_logging()

logger = logging.getLogger(__name__)


CELERY_BROKER_URL = config.CELERY_BROKER_URL
CELERY_RESULT_BACKEND = config.CELERY_RESULT_BACKEND

celery_app = Celery(
    "htl_tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Celery Beat Schedule
celery_app.conf.beat_schedule = {
    "process-due-followups": {
        "task": "whatsapp_worker.tasks.process_due_followups",
        "schedule": 60.0,  # Every 60 seconds
    },
}

celery_app.conf.timezone = "UTC"


@celery_app.task(name="whatsapp_worker.tasks.process_due_followups")
def process_due_followups():
    """
    Process all due real-time follow-ups.
    
    This task runs every minute via Celery beat.
    """
    logger.info("SCHEDULE: Starting process_due_followups check")
    try:
        # Get all conversations currently in a followup window
        due_followups = api_client.get_due_followups()
        
        if not due_followups:
            logger.info("SCHEDULE: No due follow-ups found")
            return {"processed": 0}
            
        logger.info(f"SCHEDULE: Found {due_followups} due follow-ups")
        
        processed = 0
        errors = 0
        
        for context in due_followups:
            try:
                process_realtime_followup(context)
                processed += 1
            except Exception as e:
                logger.error(f"Error processing realtime followup: {e}", exc_info=True)
                errors += 1
        
        logger.info(f"SCHEDULE: Completed. Processed: {processed}, Errors: {errors}")
        return {"processed": processed, "errors": errors}
        
    except Exception as e:
        logger.error(f"SCHEDULE: Critical error in process_due_followups: {e}", exc_info=True)
        return {"error": str(e)}


def process_realtime_followup(context: dict):
    """
    Process a single real-time follow-up via API.
    """
    conversation = context["conversation"]
    lead = context["lead"]
    followup_type = context["followup_type"]
    
    logger.info(f"Processing {followup_type} for conversation {conversation['id']}")

    # Special handling for GHOSTED - no message, just update stage to close out
    if followup_type == ConversationStage.GHOSTED or followup_type == "ghosted":
        try:
            api_client.update_conversation(
                UUID(conversation["id"]),
                stage=ConversationStage.GHOSTED
            )
            logger.info(f"Marked conversation {conversation['id']} as GHOSTED (no response after followups)")
        except Exception as e:
            logger.error(f"Failed to mark conversation as GHOSTED: {e}")
        return

    # Override the stage for the prompt registry to pick the correct warmup
    # We don't save this stage change to DB yet, it's just for generation
    conversation["stage"] = followup_type
    
    # Build org config dict from context
    org_config = {
        "organization_id": context["organization_id"],
        "organization_name": context["organization_name"],
        "business_name": context.get("business_name"),
        "business_description": context.get("business_description"),
        "flow_prompt": context.get("flow_prompt"),
    }
    
    # Build pipeline context
    pipeline_context = build_pipeline_context(
        org_config,
        conversation,
        lead
    )
    
    # Run followup pipeline
    pipeline_result = run_followup_pipeline(pipeline_context)
    
    # Handle result
    response_message = handle_pipeline_result(
        conversation, UUID(lead["id"]), pipeline_result
    )
    
    # Send and store message via API if needed
    if response_message:
        try:
            api_client.send_bot_message(
                organization_id=UUID(context["organization_id"]),
                conversation_id=UUID(conversation["id"]),
                content=response_message,
                access_token=context["access_token"],
                phone_number_id=context["phone_number_id"],
                version=context["version"],
                to=lead["phone"],
            )
            # Update conversation tracking state
            current_count = conversation.get("followup_count_24h", 0)
            api_client.update_conversation(
                UUID(conversation["id"]),
                stage=followup_type,
                followup_count_24h=current_count + 1
            )
            logger.info(f"Sent {followup_type} to {lead['phone']}")
        except Exception as e:
            logger.error(f"Failed to send followup message via API: {e}")
