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
    
    # DEBUG: Trace should_escalate value
    print(f"[actions.py] handle_pipeline_result called for {conversation_id}")
    print(f"[actions.py] result.should_escalate = {result.should_escalate}")
    print(f"[actions.py] classification.needs_human_attention = {result.classification.needs_human_attention}")
    
    # Use the unified classification output
    classification = result.classification
    
    # ========================================
    # Update conversation state from classification
    # ========================================
    
    # Update stage if recommended and confidence is high enough
    if classification.confidence >= 0.6:
        current_stage = conversation.get("stage")
        recommended_stage = classification.new_stage.value
        if recommended_stage != current_stage:
            logger.info(f"Stage transition: {current_stage} -> {recommended_stage}")
            updates["stage"] = recommended_stage
    
    # ========================================
    # Handle decision actions
    # ========================================
    
    # Reflect Intent & Sentiment
    if classification.intent_level:
        updates["intent_level"] = classification.intent_level.value
    if classification.user_sentiment:
        updates["user_sentiment"] = classification.user_sentiment.value

    # ========================================
    # INDEPENDENT: Check for human attention flag ALWAYS
    # (Not mutually exclusive with sending messages)
    # ========================================
    if result.should_escalate:
        # Escalate to human
        logger.info(f"🚩 ACTION REQUIRED: Conversation {conversation_id} flagged for human attention")
        print(f"DEBUG: Entering should_escalate block for {conversation_id}") # DEBUG LOG
        
        # Flag persistent attention needed in DB
        updates["needs_human_attention"] = True
        
        try:
            print("DEBUG: Calling emit_human_attention...") # DEBUG LOG
            api_client.emit_human_attention(
                conversation_id=conversation_id,
                organization_id=UUID(conversation["organization_id"]),
            )
            print("DEBUG: emit_human_attention called successfully") # DEBUG LOG
        except Exception as e:
            logger.error(f"Failed to emit human attention event: {e}")
            print(f"DEBUG: Exception in emit_human_attention: {e}") # DEBUG LOG

    # ========================================
    # Handle message sending and other actions
    # ========================================
    if result.should_send_message:
        # We're sending a message
        if result.response:
            message_to_send = result.response.message_text
            
            # Note: State patching was removed from GenerateOutput in simplifications
            # We rely on Classification for state updates now.
             
            # Verify stage from response matches classification (sanity check)
            # In new flow, classification drives stage.
            updates["stage"] = classification.new_stage.value
        
    elif result.should_schedule_followup:
        # Schedule a follow-up
        followup_minutes = classification.followup_in_minutes
        if followup_minutes > 0:
            schedule_followup(
                conversation,
                followup_minutes,
                classification.followup_reason
            )
    
    elif result.should_initiate_cta:
        # Initiate CTA - notify frontend
        cta_type = classification.recommended_cta.value if classification.recommended_cta else "book_call"
        logger.info(f"🚀 CTA INITIATED: Conversation {conversation_id}, type={cta_type}")
        try:
            api_client.emit_cta_initiated(
                conversation_id=conversation_id,
                organization_id=UUID(conversation["organization_id"]),
                cta_type=cta_type,
                cta_name="CTA", # classification doesn't have cta_name anymore in simplified schema?
                scheduled_time=datetime.now(timezone.utc).isoformat(), # Default to now
            )
        except Exception as e:
            logger.error(f"Failed to emit CTA initiated event: {e}")
    
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
        
        # Also sync relevant fields to Lead model
        lead_updates = {}
        if "stage" in updates:
            lead_updates["conversation_stage"] = updates["stage"]
        if "intent_level" in updates:
            lead_updates["intent_level"] = updates["intent_level"]
        if "user_sentiment" in updates:
            lead_updates["user_sentiment"] = updates["user_sentiment"]
            
        if lead_updates:
            try:
                api_client.update_lead(lead_id, **lead_updates)
                logger.info(f"Synced lead {lead_id} with updates: {lead_updates}")
            except Exception as e:
                logger.error(f"Failed to sync lead {lead_id}: {e}")
    
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
    
    # Cancel any existing pending actions for this conversation
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
        input_summary=f"stage={result.classification.new_stage.value}, conf={result.classification.confidence:.2f}",
        output_summary=f"action={result.classification.action.value}, send={result.should_send_message}",
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
