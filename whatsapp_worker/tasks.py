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
from server.enums import MessageFrom, ConversationMode

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
    Process all due scheduled follow-ups via API.
    
    This task runs every minute via Celery beat.
    """
    try:
        # Get all pending follow-ups that are due
        due_actions = api_client.get_due_actions(limit=50)
        
        if not due_actions:
            return {"processed": 0}
        
        logger.info(f"Processing {len(due_actions)} due follow-ups")
        
        processed = 0
        errors = 0
        
        for action in due_actions:
            try:
                process_single_followup(action)
                processed += 1
            except Exception as e:
                logger.error(f"Error processing followup {action['id']}: {e}", exc_info=True)
                errors += 1
                # Mark as cancelled to prevent infinite retries
                try:
                    api_client.update_action_status(
                        UUID(action["id"]),
                        status="cancelled"
                    )
                except Exception:
                    pass
        
        return {"processed": processed, "errors": errors}
        
    except Exception as e:
        logger.error(f"process_due_followups error: {e}", exc_info=True)
        return {"error": str(e)}


def process_single_followup(action: dict):
    """
    Process a single scheduled follow-up action via API.
    """
    action_id = UUID(action["id"])
    
    try:
        # Get full context for the followup
        context = api_client.get_followup_context(action_id)
    except InternalsAPIError as e:
        logger.warning(f"Could not get context for action {action_id}: {e.detail}")
        api_client.update_action_status(action_id, status="cancelled")
        return
    
    conversation = context["conversation"]
    lead = context["lead"]
    
    # Skip if conversation is no longer in bot mode
    if conversation.get("mode") != ConversationMode.BOT.value:
        logger.info(f"Skipping followup for {conversation['id']}: mode is {conversation.get('mode')}")
        api_client.update_action_status(action_id, status="cancelled")
        return
    
    # Build org config dict from followup context
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
    logger.info(f"Running followup pipeline for conversation {conversation['id']}")
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
            logger.info(f"Sent followup to {lead['phone']}")
        except Exception as e:
            logger.error(f"Failed to send followup message via API: {e}")
    
    # Mark action as executed
    api_client.update_action_status(
        action_id,
        status="executed",
        executed_at=datetime.now(timezone.utc)
    )


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


@celery_app.task(name="whatsapp_worker.tasks.process_followup")
def process_followup_task(action_id: str):
    """
    Process a specific follow-up action by ID via API.
    
    This can be used for immediate processing instead of waiting for beat.
    """
    try:
        action_uuid = UUID(action_id)
        
        # Get the action
        try:
            action = api_client.get_scheduled_action(action_uuid)
        except InternalsAPIError as e:
            if e.status_code == 404:
                return {"error": "Action not found"}
            raise
        
        if action["status"] != "pending":
            return {"error": f"Action status is {action['status']}"}
        
        process_single_followup(action)
        
        return {"status": "processed"}
        
    except Exception as e:
        logger.error(f"process_followup_task error: {e}", exc_info=True)
        return {"error": str(e)}
