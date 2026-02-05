
import sys
import os
import logging
import json
from uuid import UUID, uuid4

# Add project root to path
sys.path.append(os.getcwd())

from llm.schemas import PipelineInput, ClassifyOutput, TimingContext, NudgeContext, GenerateOutput
from llm.steps.mouth import _validate_and_build_output, _build_user_prompt
from server.enums import ConversationStage, IntentLevel, UserSentiment, DecisionAction

# Setup minimal logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_mouth_parsing():
    print("\n--- Testing Mouth Parsing ---")
    
    context = PipelineInput(
        business_name="Test Business",
        conversation_stage=ConversationStage.GREETING,
        conversation_mode="bot",
        intent_level=IntentLevel.LOW,
        user_sentiment=UserSentiment.CURIOUS,
        timing=TimingContext(now_local="2026-02-05T12:00:00Z"),
        nudges=NudgeContext(),
        language_pref="en"
    )
    
    # Test case 1: Valid UUID string
    valid_uuid = str(uuid4())
    data = {"message_text": "Hello", "selected_cta_id": valid_uuid}
    output = _validate_and_build_output(data, context)
    print(f"Test 1 (Valid UUID String): {output.selected_cta_id == UUID(valid_uuid)}")
    assert output.selected_cta_id == UUID(valid_uuid)
    
    # Test case 2: Invalid UUID string (The "1" case)
    data = {"message_text": "Hello", "selected_cta_id": "1"}
    output = _validate_and_build_output(data, context)
    print(f"Test 2 (Invalid UUID '1'): {output.selected_cta_id is None}")
    assert output.selected_cta_id is None
    
    # Test case 3: Integer (The "1" case as int)
    data = {"message_text": "Hello", "selected_cta_id": 1}
    output = _validate_and_build_output(data, context)
    print(f"Test 3 (Invalid int '1'): {output.selected_cta_id is None}")
    assert output.selected_cta_id is None
    
    # Test case 4: None/Null
    data = {"message_text": "Hello", "selected_cta_id": None}
    output = _validate_and_build_output(data, context)
    print(f"Test 4 (Null): {output.selected_cta_id is None}")
    assert output.selected_cta_id is None

def test_mouth_prompt_rendering():
    print("\n--- Testing Mouth Prompt Rendering ---")
    
    cta_id = uuid4()
    context = PipelineInput(
        business_name="Test Business",
        available_ctas=[{"id": str(cta_id), "name": "Book Call"}],
        conversation_stage=ConversationStage.GREETING,
        conversation_mode="bot",
        intent_level=IntentLevel.LOW,
        user_sentiment=UserSentiment.CURIOUS,
        timing=TimingContext(now_local="2026-02-05T12:00:00Z"),
        nudges=NudgeContext(),
        language_pref="en"
    )
    
    classification = ClassifyOutput(
        thought_process="Reasoning",
        situation_summary="Summary",
        intent_level=IntentLevel.LOW,
        user_sentiment=UserSentiment.CURIOUS,
        risk_flags={"spam_risk": "low", "policy_risk": "low", "hallucination_risk": "low"},
        action=DecisionAction.SEND_NOW,
        new_stage=ConversationStage.QUALIFICATION,
        should_respond=True,
        confidence=0.9
    )
    
    prompt = _build_user_prompt(context, classification)
    
    # Verify prompt contains CTA section
    contains_ctas = "<available_ctas>" in prompt and "Book Call" in prompt
    print(f"Prompt contains available_ctas: {contains_ctas}")
    assert contains_ctas

if __name__ == "__main__":
    try:
        test_mouth_parsing()
        test_mouth_prompt_rendering()
        print("\n✅ All Mouth verification tests passed!")
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        exit(1)
