"""
Actions Handler for HTL Pipeline Results.
Processes pipeline results and executes the appropriate actions via API.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import UUID

from llm.schemas import PipelineResult
from server.enums import ConversationMode, MessageFrom
from whatsapp_worker.processors.api_client import api_client

logger = logging.getLogger(__name__)


def handle_pipeline_result(
    conversation: Dict,
    lead_id: UUID,
    result: PipelineResult,
) -> Optional[str]:
    """
    Process pipeline result and execute actions via API.
    
    Returns:
        Message text to send, or None if not sending
    """
    conversation_id = UUID(conversation["id"])
    message_to_send = None
    updates = {}
    
    # ========================================
    # Update conversation state from analysis
    # ========================================
    
    # Update stage if recommended and confidence is high enough
    if result.analysis.confidence >= 0.6:
        current_stage = conversation.get("stage")
        recommended_stage = result.analysis.stage_recommendation.value
        if recommended_stage != current_stage:
            logger.info(f"Stage transition: {current_stage} -> {recommended_stage}")
            updates["stage"] = recommended_stage
    
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
                updates["intent_level"] = patch.intent_level.value
            if patch.user_sentiment:
                updates["user_sentiment"] = patch.user_sentiment.value
            if patch.conversation_stage:
                updates["stage"] = patch.conversation_stage.value
        
        # Update conversation with new stage
        updates["stage"] = result.response.next_stage.value
        
    elif result.should_schedule_followup:
        # Schedule a follow-up
        followup_minutes = result.decision.followup_in_minutes
        if followup_minutes > 0:
            schedule_followup(
                conversation,
                followup_minutes,
                result.decision.followup_reason
            )
        
    elif result.should_escalate:
        # Escalate to human
        # updates["mode"] = ConversationMode.HUMAN.value  <-- User requested strict manual takeover
        logger.info(f"🚩 ACTION REQUIRED: Conversation {conversation_id} flagged for human attention: {result.decision.why}")
        # TODO: Send WebSocket notification (ACTION_HUMAN_ATTENTION_REQUIRED)
        # SOLUTION: Call in internal api to emit event based on WSEvents
    
    elif result.should_initiate_cta:
        # Initiate CTA
        logger.info(f"🚀 ACTION REQUIRED: Conversation {conversation_id} flagged for CTA: {result.decision.why}")
        # TODO: Send WebSocket notification (ACTION_CTA_INITIATED)
        # SOLUTION: Call in internal api to emit event based on WSEvents
    
    # ========================================
    # Always update rolling summary
    # ========================================
    if result.summary and result.summary.updated_rolling_summary:
        updates["rolling_summary"] = result.summary.updated_rolling_summary
    
    # ========================================
    # Apply conversation updates via API
    # ========================================
    if updates:
        api_client.update_conversation(conversation_id, **updates)
    
    # ========================================
    # Log pipeline event
    # ========================================
    log_pipeline_event(conversation_id, result)
    
    return message_to_send


def schedule_followup(
    conversation: Dict,
    delay_minutes: int,
    reason: str = "",
) -> Dict:
    """
    Schedule a follow-up action for later execution via API.
    """
    conversation_id = UUID(conversation["id"])
    organization_id = UUID(conversation["organization_id"])
    
    # Cancel any existing pending follow-ups for this conversation
    cancelled = api_client.cancel_pending_actions(conversation_id)
    if cancelled > 0:
        logger.info(f"Cancelled {cancelled} pending actions for conversation {conversation_id}")
    
    # Create new scheduled action
    scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
    
    action = api_client.create_scheduled_action(
        conversation_id=conversation_id,
        organization_id=organization_id,
        scheduled_at=scheduled_at,
        action_type="followup",
        action_context=reason,
    )
    
    logger.info(f"Scheduled followup for conversation {conversation_id} at {scheduled_at}")
    
    return action


def log_pipeline_event(
    conversation_id: UUID,
    result: PipelineResult,
) -> Dict:
    """
    Log pipeline execution for audit/debugging via API.
    """
    return api_client.log_pipeline_event(
        conversation_id=conversation_id,
        event_type="pipeline_run",
        pipeline_step="complete",
        input_summary=f"stage={result.analysis.stage_recommendation.value}, conf={result.analysis.confidence:.2f}",
        output_summary=f"action={result.decision.action.value}, send={result.should_send_message}",
        latency_ms=result.pipeline_latency_ms,
        tokens_used=result.total_tokens_used,
    )


def reset_daily_followup_counts() -> int:
    """
    Reset followup_count_24h for all conversations via API.
    Should be called daily by Celery beat.
    
    Returns:
        Number of conversations reset
    """
    result = api_client.reset_followup_counts()
    logger.info(f"Reset daily followup counts for {result} conversations")
    return result
