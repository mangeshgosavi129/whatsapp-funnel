"""
Actions Handler for HTL Pipeline Results.
Processes pipeline results and executes the appropriate actions via API.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID
from llm.schemas import PipelineResult
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
    
    # Use the unified classification output
    classification = result.classification
    
    # ========================================
    # Update conversation state from classification
    # ========================================
    
    # ========================================
    # 1. Collect all state updates
    # ========================================
    
    # Update stage if recommended and confidence is high enough
    if classification.confidence >= 0.6:
        current_stage = conversation.get("stage")
        recommended_stage = classification.new_stage.value
        if recommended_stage != current_stage:
            logger.info(f"Stage transition: {current_stage} -> {recommended_stage}")
            updates["stage"] = recommended_stage
    
    # Reflect Intent & Sentiment
    if classification.intent_level:
        updates["intent_level"] = classification.intent_level.value
    if classification.user_sentiment:
        updates["user_sentiment"] = classification.user_sentiment.value

    # Check for human attention flag (INDEPENDENT - can happen with any action)
    if result.should_escalate:
        logger.info(f"🚩 ACTION REQUIRED: Conversation {conversation_id} flagged for human attention")
        updates["needs_human_attention"] = True

    # Collect CTA fields (INDEPENDENT - CTA can be triggered even when sending a message)
    # e.g., "Let's book a call!" message + CTA initiation
    selected_cta_id = classification.selected_cta_id
    if result.response and result.response.selected_cta_id:
        selected_cta_id = result.response.selected_cta_id
        
    if selected_cta_id:
        updates["cta_id"] = str(selected_cta_id)
        if classification.cta_scheduled_at:
            updates["cta_scheduled_at"] = classification.cta_scheduled_at
        logger.info(f"📋 CTA selected: {selected_cta_id} for conversation {conversation_id}")

    # Handle message sending
    if result.should_send_message and result.response:
        message_to_send = result.response.message_text
        updates["stage"] = classification.new_stage.value
        
    # Update rolling summary
    if result.summary and result.summary.updated_rolling_summary:
        updates["rolling_summary"] = result.summary.updated_rolling_summary
    
    # ========================================
    # 2. Persist state updates to DB first
    # ========================================
    if updates:
        try:
            api_client.update_conversation(conversation_id, **updates)
            
            # Sync relevant fields to Lead model
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
                except Exception as e:
                    logger.error(f"Failed to sync lead {lead_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to persist conversation updates: {e}")
    
    # ========================================
    # 3. Emit WebSocket events (Enhancement)
    # ========================================
    
    # Emit human attention if flagged
    if updates.get("needs_human_attention"):
        try:
            api_client.emit_human_attention(
                conversation_id=conversation_id,
                organization_id=UUID(conversation["organization_id"]),
            )
        except Exception as e:
            logger.error(f"Failed to emit human attention event: {e}")

    # Emit CTA initiation if flagged
    if "cta_id" in updates:
        try:
            # Fetch CTA Name for the event
            cta_name = "CTA"
            selected_cta_id = updates["cta_id"]
            try:
                raw_ctas = api_client.get_organization_ctas(UUID(conversation["organization_id"]))
                for cta in raw_ctas:
                    if str(cta["id"]) == str(selected_cta_id):
                        cta_name = cta["name"]
                        break
            except Exception as e:
                logger.error(f"Failed to fetch CTA name for event: {e}")

            api_client.emit_cta_initiated(
                conversation_id=conversation_id,
                organization_id=UUID(conversation["organization_id"]),
                cta_type=cta_name,
                cta_name=cta_name,
                scheduled_time=updates.get("cta_scheduled_at") or datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            logger.error(f"Failed to emit CTA initiated event: {e}")

    # Log pipeline event
    log_pipeline_event(conversation_id, result)
    
    return message_to_send


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

