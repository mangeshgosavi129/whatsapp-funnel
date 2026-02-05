
from llm.schemas import ClassifyOutput, RiskFlags
from server.enums import IntentLevel, UserSentiment, DecisionAction, ConversationStage, RiskLevel

def test_classify_output_limits():
    long_thought_process = "a" * 500  # 500 chars > old 300 limit
    long_situation_summary = "b" * 300 # 300 chars > old 200 limit

    try:
        output = ClassifyOutput(
            thought_process=long_thought_process,
            situation_summary=long_situation_summary,
            intent_level=IntentLevel.INFO,
            user_sentiment=UserSentiment.NEUTRAL,
            risk_flags=RiskFlags(
                spam_risk=RiskLevel.LOW,
                policy_risk=RiskLevel.LOW,
                hallucination_risk=RiskLevel.LOW
            ),
            action=DecisionAction.WAIT_SCHEDULE,
            new_stage=ConversationStage.DISCOVERY,
            should_respond=False,
            confidence=0.9
        )
        print("SUCCESS: ClassifyOutput accepted long strings.")
    except Exception as e:
        print(f"FAILURE: Validation error: {e}")

if __name__ == "__main__":
    test_classify_output_limits()
