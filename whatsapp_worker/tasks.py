"""
Celery Tasks for HTL Pipeline.
Handles scheduled follow-ups and periodic maintenance via API calls.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from celery import Celery

from whatsapp_worker.processors.api_client import api_client, InternalsAPIError
from whatsapp_worker.processors.context import build_pipeline_context
from whatsapp_worker.processors.actions import handle_pipeline_result, reset_daily_followup_counts
from llm.pipeline import run_followup_pipeline
from server.enums import MessageFrom, ConversationMode, ConversationStage

logger = logging.getLogger(__name__)

# Celery app configuration
# The broker URL should come from environment in production
import os
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "htl_tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Celery Beat Schedule
celery_app.conf.beat_schedule = {
    # Check for due follow-ups every minute
    "process-due-followups": {
        "task": "whatsapp_worker.tasks.process_due_followups",
        "schedule": 60.0,  # Every 60 seconds
    },
    # Reset daily followup counts at midnight
    "reset-daily-counts": {
        "task": "whatsapp_worker.tasks.reset_daily_counts",
        "schedule": 86400.0,  # Every 24 hours
    },
}

celery_app.conf.timezone = "UTC"


@celery_app.task(name="whatsapp_worker.tasks.process_due_followups")
def process_due_followups():
    """
    Process all due real-time follow-ups.
    
    This task runs every minute via Celery beat.
    """
    try:
        # Get all conversations currently in a followup window
        due_followups = api_client.get_due_followups()
        
        if not due_followups:
            return {"processed": 0}
        
        logger.info(f"Processing {len(due_followups)} due follow-ups")
        
        processed = 0
        errors = 0
        
        for context in due_followups:
            try:
                process_realtime_followup(context)
                processed += 1
            except Exception as e:
                logger.error(f"Error processing realtime followup: {e}", exc_info=True)
                errors += 1
        
        return {"processed": processed, "errors": errors}
        
    except Exception as e:
        logger.error(f"process_due_followups error: {e}", exc_info=True)
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


@celery_app.task(name="whatsapp_worker.tasks.reset_daily_counts")
def reset_daily_counts():
    """
    Reset daily followup counts for all conversations via API.
    
    This task runs once per day via Celery beat.
    """
    try:
        count = reset_daily_followup_counts()
        logger.info(f"Reset daily followup counts for {count} conversations")
        return {"reset": count}
        
    except Exception as e:
        logger.error(f"reset_daily_counts error: {e}", exc_info=True)
        return {"error": str(e)}
