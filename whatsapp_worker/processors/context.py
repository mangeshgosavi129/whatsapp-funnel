"""
Context Builder for HTL Pipeline.
Gathers all necessary context via API calls to build pipeline input.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from llm.schemas import (
    PipelineInput, MessageContext, TimingContext, NudgeContext
)
from server.enums import (
    ConversationStage, ConversationMode, IntentLevel, UserSentiment
)
from whatsapp_worker.processors.api_client import api_client

logger = logging.getLogger(__name__)

def get_last_messages(
    conversation_id: UUID,
    limit: int = 10
) -> List[MessageContext]:
    """
    Get last N messages for context via API.
    """
    messages = api_client.get_conversation_messages(conversation_id, limit)
    
    return [
        MessageContext(
            sender=msg["sender"],
            text=msg["text"],
            timestamp=msg["timestamp"],
        )
        for msg in messages
    ]


def calculate_whatsapp_window(last_user_message_at: Optional[str]) -> bool:
    """
    Check if WhatsApp 24-hour messaging window is open.
    
    WhatsApp Business API allows sending messages without templates
    only within 24 hours of the last user message.
    """
    if not last_user_message_at:
        return False  # No user message = no window
    
    # Parse ISO timestamp
    try:
        last_msg_time = datetime.fromisoformat(last_user_message_at.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return False
    
    # Ensure timezone-aware comparison
    now = datetime.now(timezone.utc)
    if last_msg_time.tzinfo is None:
        last_msg_time = last_msg_time.replace(tzinfo=timezone.utc)
    
    window_end = last_msg_time + timedelta(hours=24)
    
    return now < window_end


def build_pipeline_context(
    org_config: Dict,
    conversation: Dict,
    lead: Dict,
) -> PipelineInput:
    """
    Build complete pipeline context from API data.
    
    Args:
        org_config: Dict with organization config including:
            - organization_name: str
            - business_name: Optional[str]
            - business_description: Optional[str]
            - flow_prompt: Optional[str]
        conversation: Conversation data from API
        lead: Lead data from API
    """
    conversation_id = UUID(conversation["id"])
    
    # Get last messages
    last_messages = get_last_messages(conversation_id, limit=10)
    
    # Get current time in ISO format
    now = datetime.now(timezone.utc)
    now_local = now.isoformat()
    
    # Calculate WhatsApp window
    whatsapp_window = calculate_whatsapp_window(conversation.get("last_user_message_at"))
    
    # Build timing context
    timing = TimingContext(
        now_local=now_local,
        last_user_message_at=conversation.get("last_user_message_at"),
        last_bot_message_at=conversation.get("last_bot_message_at"),
        whatsapp_window_open=whatsapp_window,
    )
    
    # Build nudge context
    nudges = NudgeContext(
        followup_count_24h=conversation.get("followup_count_24h", 0),
        total_nudges=conversation.get("total_nudges", 0),
    )
    
    # Parse enums from string values
    stage = ConversationStage(conversation.get("stage", ConversationStage.GREETING.value))
    intent_level = IntentLevel(conversation.get("intent_level", IntentLevel.UNKNOWN.value)) if conversation.get("intent_level") else IntentLevel.UNKNOWN
    user_sentiment = UserSentiment(conversation.get("user_sentiment", UserSentiment.NEUTRAL.value)) if conversation.get("user_sentiment") else UserSentiment.NEUTRAL
    mode = conversation.get("mode", ConversationMode.BOT.value)
    
    # Get business config from org_config (with fallback to org name)
    business_name = org_config.get("business_name") or org_config.get("organization_name", "")
    business_description = org_config.get("business_description") or ""
    flow_prompt = org_config.get("flow_prompt") or ""
    
    # Fetch available CTAs
    try:
        raw_ctas = api_client.get_organization_ctas(UUID(org_config["organization_id"]))
        available_ctas = [
            {"id": str(cta["id"]), "name": cta["name"]}
            for cta in raw_ctas
        ]
    except Exception as e:
        logger.error(f"Failed to fetch CTAs for context: {e}")
        available_ctas = []

    # Build pipeline input
    context = PipelineInput(
        # Business context (from organization config)
        organization_id=UUID(org_config["organization_id"]),
        business_name=business_name,
        business_description=business_description,
        flow_prompt=flow_prompt,
        
        # CTAs
        available_ctas=available_ctas,
        
        # Conversation context  
        rolling_summary=conversation.get("rolling_summary", ""),
        last_messages=last_messages,
        
        # Current state
        conversation_stage=stage,
        conversation_mode=mode,
        intent_level=intent_level,
        user_sentiment=user_sentiment,
        active_cta_id=UUID(conversation["cta_id"]) if conversation.get("cta_id") else None,
        
        # Timing
        timing=timing,
        nudges=nudges,
        
        # Constraints (defaults for now)
        max_words=80,
        questions_per_message=1,
        language_pref="en",
    )
    
    return context