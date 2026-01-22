"""
Actions Handler for HTL Pipeline Results.
Processes pipeline results and executes the appropriate actions.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from llm.schemas import PipelineResult
from server.models import (
    Conversation, Message, ScheduledAction, ConversationEvent
)
from server.enums import (
    MessageFrom, ConversationMode, ScheduledActionStatus
)

logger = logging.getLogger(__name__)


def handle_pipeline_result(
    db: Session,
    conversation: Conversation,
    lead_id: UUID,
    result: PipelineResult,
) -> Optional[str]:
    """
    Process pipeline result and execute actions.
    
    Returns:
        Message text to send, or None if not sending
    """
    message_to_send = None
    
    # ========================================
    # Update conversation state from analysis
    # ========================================
    
    # Update stage if recommended and confidence is high enough
    if result.analysis.confidence >= 0.6:
        if result.analysis.stage_recommendation != conversation.stage:
            logger.info(f"Stage transition: {conversation.stage.value} -> {result.analysis.stage_recommendation.value}")
            conversation.stage = result.analysis.stage_recommendation
    
    # ========================================
    # Handle decision actions
    # ========================================
    
    if result.should_send_message:
        # We're sending a message
        message_to_send = result.response.message_text
        
        # Apply state patch from generation
        if result.response.state_patch:
            patch = result.response.state_patch
            if patch.intent_level:
                conversation.intent_level = patch.intent_level
            if patch.user_sentiment:
                conversation.user_sentiment = patch.user_sentiment
            if patch.conversation_stage:
                conversation.stage = patch.conversation_stage
        
        # Update conversation with new stage
        conversation.stage = result.response.next_stage
        
    elif result.should_schedule_followup:
        # Schedule a follow-up
        followup_minutes = result.decision.followup_in_minutes
        if followup_minutes > 0:
            schedule_followup(
                db, 
                conversation, 
                followup_minutes,
                result.decision.followup_reason
            )
        
    elif result.should_escalate:
        # Escalate to human
        conversation.mode = ConversationMode.HUMAN
        logger.info(f"Escalating conversation {conversation.id} to human: {result.decision.why}")
        # TODO: Send WebSocket notification to frontend
    
    # ========================================
    # Always update rolling summary
    # ========================================
    if result.summary and result.summary.updated_rolling_summary:
        conversation.rolling_summary = result.summary.updated_rolling_summary
    
    # ========================================
    # Log pipeline event
    # ========================================
    log_pipeline_event(db, conversation.id, result)
    
    db.flush()
    
    return message_to_send


def store_outgoing_message(
    db: Session,
    conversation: Conversation,
    lead_id: UUID,
    message_text: str,
    message_from: MessageFrom = MessageFrom.BOT,
) -> Message:
    """
    Store outgoing bot/human message and update conversation.
    """
    now = datetime.now(timezone.utc)
    
    message = Message(
        organization_id=conversation.organization_id,
        conversation_id=conversation.id,
        lead_id=lead_id,
        message_from=message_from,
        content=message_text,
        status="sent",
    )
    db.add(message)
    
    # Update conversation timestamps
    conversation.last_message = message_text[:500]
    conversation.last_message_at = now
    conversation.last_bot_message_at = now
    
    db.flush()
    
    return message


def schedule_followup(
    db: Session,
    conversation: Conversation,
    delay_minutes: int,
    reason: str = "",
) -> ScheduledAction:
    """
    Schedule a follow-up action for later execution.
    """
    # Cancel any existing pending follow-ups for this conversation
    db.query(ScheduledAction).filter(
        ScheduledAction.conversation_id == conversation.id,
        ScheduledAction.status == ScheduledActionStatus.PENDING
    ).update({"status": ScheduledActionStatus.CANCELLED})
    
    # Create new scheduled action
    scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
    
    action = ScheduledAction(
        conversation_id=conversation.id,
        organization_id=conversation.organization_id,
        scheduled_at=scheduled_at,
        status=ScheduledActionStatus.PENDING,
        action_type="followup",
        action_context=reason,
    )
    db.add(action)
    
    # Update conversation
    conversation.scheduled_followup_at = scheduled_at
    conversation.total_nudges = (conversation.total_nudges or 0) + 1
    
    # Increment 24h followup count
    conversation.followup_count_24h = (conversation.followup_count_24h or 0) + 1
    
    db.flush()
    
    logger.info(f"Scheduled followup for conversation {conversation.id} at {scheduled_at}")
    
    return action


def log_pipeline_event(
    db: Session,
    conversation_id: UUID,
    result: PipelineResult,
) -> ConversationEvent:
    """
    Log pipeline execution for audit/debugging.
    """
    event = ConversationEvent(
        conversation_id=conversation_id,
        event_type="pipeline_run",
        pipeline_step="complete",
        input_summary=f"stage={result.analysis.stage_recommendation.value}, conf={result.analysis.confidence:.2f}",
        output_summary=f"action={result.decision.action.value}, send={result.should_send_message}",
        latency_ms=result.pipeline_latency_ms,
        tokens_used=result.total_tokens_used,
    )
    db.add(event)
    
    return event


def reset_daily_followup_counts(db: Session) -> int:
    """
    Reset followup_count_24h for all conversations.
    Should be called daily by Celery beat.
    
    Returns:
        Number of conversations reset
    """
    result = db.query(Conversation).filter(
        Conversation.followup_count_24h > 0
    ).update({"followup_count_24h": 0})
    
    db.commit()
    
    logger.info(f"Reset daily followup counts for {result} conversations")
    
    return result
