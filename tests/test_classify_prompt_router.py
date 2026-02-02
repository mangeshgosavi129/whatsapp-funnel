
import pytest
from llm.schemas import PipelineInput, MessageContext, TimingContext, NudgeContext
from llm.steps.classify import _is_opening_message, _build_user_prompt
from llm.prompts_registry import get_classify_system_prompt
from server.enums import ConversationStage, IntentLevel, UserSentiment

@pytest.fixture
def base_context():
    return PipelineInput(
        business_name="Test Business",
        business_description="Test Description",
        conversation_stage=ConversationStage.GREETING,
        conversation_mode="bot",
        intent_level=IntentLevel.UNKNOWN,
        user_sentiment=UserSentiment.NEUTRAL,
        timing=TimingContext(now_local="2024-01-01T12:00:00", whatsapp_window_open=True),
        nudges=NudgeContext()
    )

def test_opening_message_detection(base_context):
    # Case 1: Empty history
    base_context.last_3_messages = []
    base_context.rolling_summary = ""
    assert _is_opening_message(base_context) is True

    # Case 2: One message, no summary
    base_context.last_3_messages = [MessageContext(sender="lead", text="Hi", timestamp="...")]
    assert _is_opening_message(base_context) is True

    # Case 3: Multiple messages (Reply path)
    base_context.last_3_messages = [
        MessageContext(sender="lead", text="Hi", timestamp="..."),
        MessageContext(sender="bot", text="Hello!", timestamp="...")
    ]
    assert _is_opening_message(base_context) is False

    # Case 4: One message but with summary (Partial fail recovery / Long conversation)
    base_context.last_3_messages = [MessageContext(sender="lead", text="Hi", timestamp="...")]
    base_context.rolling_summary = "User previously asked about X."
    assert _is_opening_message(base_context) is False

def test_opening_path_excludes_history(base_context):
    base_context.last_3_messages = [MessageContext(sender="lead", text="Hi", timestamp="...")]
    base_context.rolling_summary = ""
    
    prompt = _build_user_prompt(base_context, is_opening=True)
    
    assert "CONVERSATION HISTORY" not in prompt
    assert "rolling_summary" not in prompt
    assert "Last Messages" not in prompt
    # Business context should also be excluded
    assert base_context.business_name not in prompt
    assert base_context.business_description not in prompt

def test_reply_path_includes_history(base_context):
    base_context.last_3_messages = [
        MessageContext(sender="lead", text="Hi", timestamp="..."),
        MessageContext(sender="bot", text="Hello!", timestamp="...")
    ]
    base_context.rolling_summary = "The user is interested in testing."
    
    prompt = _build_user_prompt(base_context, is_opening=False)
    
    assert "CONVERSATION HISTORY" in prompt
    assert "The user is interested in testing." in prompt
    assert "[lead] Hi" in prompt
    assert "[bot] Hello!" in prompt

def test_classify_system_prompt_isolation():
    # Greeting Stage
    greeting_prompt = get_classify_system_prompt(ConversationStage.GREETING, is_opening=False)
    assert "=== STAGE: GREETING ===" in greeting_prompt
    assert "=== STAGE: QUALIFICATION ===" not in greeting_prompt
    assert "=== STAGE: PRICING ===" not in greeting_prompt

    # Pricing Stage
    pricing_prompt = get_classify_system_prompt(ConversationStage.PRICING, is_opening=False)
    assert "=== STAGE: PRICING ===" in pricing_prompt
    assert "=== STAGE: GREETING ===" not in pricing_prompt
    assert "=== STAGE: QUALIFICATION ===" not in pricing_prompt

def test_opening_message_forces_greeting_prompt():
    # Even if context says PRICING, an opening message should use GREETING prompt
    prompt = get_classify_system_prompt(ConversationStage.PRICING, is_opening=True)
    assert "=== STAGE: GREETING ===" in prompt
    assert "OPENING message from a new lead" in prompt
    assert "=== STAGE: PRICING ===" not in prompt
