"""
Celery Tasks for HTL Pipeline.
Handles scheduled follow-ups and periodic maintenance.
"""
import logging
from datetime import datetime, timezone
from celery import Celery

from server.database import SessionLocal
from server.models import (
    ScheduledAction, Conversation, Lead, Organization, WhatsAppIntegration
)
from server.enums import ScheduledActionStatus, ConversationMode
from whatsapp_worker.context import build_pipeline_context
from whatsapp_worker.actions import handle_pipeline_result, store_outgoing_message, reset_daily_followup_counts
from whatsapp_worker.send import send_whatsapp_text
from llm.pipeline import run_followup_pipeline
from server.enums import MessageFrom

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
    Process all due scheduled follow-ups.
    
    This task runs every minute via Celery beat.
    """
    db = SessionLocal()
    
    try:
        now = datetime.now(timezone.utc)
        
        # Get all pending follow-ups that are due
        due_actions = db.query(ScheduledAction).filter(
            ScheduledAction.status == ScheduledActionStatus.PENDING,
            ScheduledAction.scheduled_at <= now
        ).limit(50).all()  # Process max 50 at a time
        
        if not due_actions:
            return {"processed": 0}
        
        logger.info(f"Processing {len(due_actions)} due follow-ups")
        
        processed = 0
        errors = 0
        
        for action in due_actions:
            try:
                process_single_followup(db, action)
                processed += 1
            except Exception as e:
                logger.error(f"Error processing followup {action.id}: {e}", exc_info=True)
                errors += 1
                # Mark as failed to prevent infinite retries
                action.status = ScheduledActionStatus.CANCELLED
        
        db.commit()
        
        return {"processed": processed, "errors": errors}
        
    except Exception as e:
        logger.error(f"process_due_followups error: {e}", exc_info=True)
        db.rollback()
        return {"error": str(e)}
        
    finally:
        db.close()


def process_single_followup(db, action: ScheduledAction):
    """
    Process a single scheduled follow-up action.
    """
    # Get conversation
    conversation = db.query(Conversation).filter(
        Conversation.id == action.conversation_id
    ).first()
    
    if not conversation:
        logger.warning(f"Conversation {action.conversation_id} not found for followup")
        action.status = ScheduledActionStatus.CANCELLED
        return
    
    # Skip if conversation is no longer in bot mode
    if conversation.mode != ConversationMode.BOT:
        logger.info(f"Skipping followup for {conversation.id}: mode is {conversation.mode.value}")
        action.status = ScheduledActionStatus.CANCELLED
        return
    
    # Get lead
    lead = db.query(Lead).filter(Lead.id == conversation.lead_id).first()
    if not lead:
        logger.warning(f"Lead {conversation.lead_id} not found")
        action.status = ScheduledActionStatus.CANCELLED
        return
    
    # Get organization
    organization = db.query(Organization).filter(
        Organization.id == conversation.organization_id
    ).first()
    if not organization:
        logger.warning(f"Organization {conversation.organization_id} not found")
        action.status = ScheduledActionStatus.CANCELLED
        return
    
    # Get WhatsApp integration
    integration = db.query(WhatsAppIntegration).filter(
        WhatsAppIntegration.organization_id == organization.id,
        WhatsAppIntegration.is_connected == True
    ).first()
    if not integration:
        logger.warning(f"No WhatsApp integration for org {organization.id}")
        action.status = ScheduledActionStatus.CANCELLED
        return
    
    # Build pipeline context
    pipeline_context = build_pipeline_context(db, organization, conversation, lead)
    
    # Run followup pipeline
    logger.info(f"Running followup pipeline for conversation {conversation.id}")
    pipeline_result = run_followup_pipeline(pipeline_context)
    
    # Handle result
    response_message = handle_pipeline_result(
        db, conversation, lead.id, pipeline_result
    )
    
    # Send message if needed
    if response_message:
        store_outgoing_message(
            db, conversation, lead.id, response_message, MessageFrom.BOT
        )
        
        try:
            send_whatsapp_text(
                to=lead.phone,
                message=response_message,
                access_token=integration.access_token,
                phone_number_id=integration.phone_number_id,
                version=integration.version,
            )
            logger.info(f"Sent followup to {lead.phone}")
        except Exception as e:
            logger.error(f"Failed to send followup message: {e}")
    
    # Mark action as executed
    action.status = ScheduledActionStatus.EXECUTED
    action.executed_at = datetime.now(timezone.utc)


@celery_app.task(name="whatsapp_worker.tasks.reset_daily_counts")
def reset_daily_counts():
    """
    Reset daily followup counts for all conversations.
    
    This task runs once per day via Celery beat.
    """
    db = SessionLocal()
    
    try:
        count = reset_daily_followup_counts(db)
        logger.info(f"Reset daily followup counts for {count} conversations")
        return {"reset": count}
        
    except Exception as e:
        logger.error(f"reset_daily_counts error: {e}", exc_info=True)
        return {"error": str(e)}
        
    finally:
        db.close()


@celery_app.task(name="whatsapp_worker.tasks.process_followup")
def process_followup_task(action_id: str):
    """
    Process a specific follow-up action by ID.
    
    This can be used for immediate processing instead of waiting for beat.
    """
    db = SessionLocal()
    
    try:
        action = db.query(ScheduledAction).filter(
            ScheduledAction.id == action_id
        ).first()
        
        if not action:
            return {"error": "Action not found"}
        
        if action.status != ScheduledActionStatus.PENDING:
            return {"error": f"Action status is {action.status.value}"}
        
        process_single_followup(db, action)
        db.commit()
        
        return {"status": "processed"}
        
    except Exception as e:
        logger.error(f"process_followup_task error: {e}", exc_info=True)
        db.rollback()
        return {"error": str(e)}
        
    finally:
        db.close()
