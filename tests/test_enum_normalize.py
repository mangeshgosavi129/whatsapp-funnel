"""
Quick test for HTL pipeline enum handling.
Tests that structured output and fuzzy matching work correctly.
"""
import sys
import os
sys.path.append(os.getcwd())

from llm.utils import normalize_enum
from server.enums import ConversationStage, IntentLevel, UserSentiment, DecisionAction

print("=" * 60)
print("Testing normalize_enum with fuzzy matching")
print("=" * 60)

# Test cases that previously caused errors
test_cases = [
    # (value, enum_class, expected_result)
    ("qualifying", ConversationStage, ConversationStage.QUALIFICATION),
    ("qualification", ConversationStage, ConversationStage.QUALIFICATION),
    ("Greeting", ConversationStage, ConversationStage.GREETING),
    ("GREETING", ConversationStage, ConversationStage.GREETING),  # uppercase input -> lowercase value
    ("SEND_NOW", DecisionAction, DecisionAction.SEND_NOW),
    ("send_now", DecisionAction, DecisionAction.SEND_NOW),
    ("high", IntentLevel, IntentLevel.HIGH),
    ("HIGH", IntentLevel, IntentLevel.HIGH),  # uppercase input
    ("very high", IntentLevel, IntentLevel.VERY_HIGH),  # with space
    ("neutral", UserSentiment, UserSentiment.NEUTRAL),
    ("NEUTRAL", UserSentiment, UserSentiment.NEUTRAL),  # uppercase input
    (None, ConversationStage, ConversationStage.GREETING),  # None returns default
    ("invalid_value_xyz", ConversationStage, ConversationStage.GREETING),  # fallback
]

all_passed = True
for value, enum_class, expected in test_cases:
    default = ConversationStage.GREETING if enum_class == ConversationStage else None
    result = normalize_enum(value, enum_class, default)
    
    status = "✅" if result == expected else "❌"
    if result != expected:
        all_passed = False
    
    print(f"{status} normalize_enum({value!r}, {enum_class.__name__}) = {result}")
    if result != expected:
        print(f"   Expected: {expected}")

print()
print("=" * 60)
if all_passed:
    print("✅ ALL TESTS PASSED - Enum handling is production-robust!")
else:
    print("❌ SOME TESTS FAILED - Review the output above")
print("=" * 60)
