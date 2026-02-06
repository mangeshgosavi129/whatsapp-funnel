
from llm.schemas import PipelineInput, TimingContext, NudgeContext
from server.enums import ConversationStage, IntentLevel, UserSentiment
from llm.steps.brain import _validate_and_build_output
from server.enums import ConversationStage

def test_brain_stage_fallback():
    print("Testing Brain stage fallback logic...")
    
    # Mock context with current stage 'greeting'
    context = PipelineInput(
        conversation_id="test_conv",
        business_name="Test Biz",
        conversation_mode="bot",
        intent_level=IntentLevel.LOW,
        user_sentiment=UserSentiment.CURIOUS,
        conversation_stage=ConversationStage.GREETING,
        last_messages=[],
        available_ctas=[],
        business_description="Test Business",
        flow_prompt="Test Flow",
        timing=TimingContext(now_local="12:00", whatsapp_window_open=True),
        nudges=NudgeContext(followup_count_24h=0, total_nudges=0)
    )
    
    # Mock data from LLM with an invalid stage 'interest_exploration'
    data = {
        "implementation_plan": "Test plan",
        "action": "send_now",
        "new_stage": "interest_exploration",
        "should_respond": True,
        "selected_cta_id": None,
        "cta_scheduled_at": None,
        "followup_in_minutes": 0,
        "followup_reason": "",
        "confidence": 0.97,
        "needs_human_attention": False
    }
    
    output = _validate_and_build_output(data, context)
    
    print(f"Old Stage: {context.conversation_stage}")
    print(f"LLM Stage (invalid): {data['new_stage']}")
    print(f"Output Stage: {output.new_stage}")
    
    assert output.new_stage == ConversationStage.GREETING
    print("SUCCESS: Brain correctly fell back to the old stage.")

if __name__ == "__main__":
    test_brain_stage_fallback()
