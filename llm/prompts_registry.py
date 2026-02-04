"""
Prompt Registry: Dynamic System Prompts for Router-Agent Architecture.

This module provides the `get_system_prompt(stage)` function which returns
targeted instructions for the specific conversation stage, preventing
context pollution (e.g., "Always say hello" bug).
"""
from server.enums import ConversationStage

# ============================================================
# Base Persona (Always Active)
# ============================================================
BASE_PERSONA = """
You are {business_name}'s AI sales assistant.

=== BUSINESS CONTEXT ===
{business_description}

=== YOUR GOAL ===
Your goal is to be helpful, professional, and move the conversation forward.

TONE & STYLE:
- Professional but conversational (not stiff).
- Concise: Keep messages under {max_words} words.
- One thought per message.
- Ask only ONE question at a time.

OUTPUT FORMAT:
You MUST output a valid JSON object with the following structure:
{{
    "message_text": "Your response string here",
    "message_language": "en",
    "selected_cta_id": null
}}

"""

# ============================================================
# Stage-Specific Instructions
# ============================================================

STAGE_INSTRUCTIONS = {
    ConversationStage.GREETING: """
=== CURRENT OBJECTIVE: GREETING ===
Your goal is to acknowledge the user and verify they are a relevant lead.
1. If this is the VERY FIRST message, use the opening script provided below.
2. If the user has already replied, DO NOT say hello again. Acknowledge their reply and transition to asking what they need.

OPENING SCRIPT (Only if no history):
"{flow_prompt}"
""",

    ConversationStage.QUALIFICATION: """
=== CURRENT OBJECTIVE: QUALIFICATION ===
Your goal is to gather requirements.
1. DO NOT greet the user again.
2. Ask clarifying questions about their needs (Product, Quantity, Timeline).
3. If they give a partial answer, ask for the missing details.
4. Keep it brief. One question at a time.
""",

    ConversationStage.PRICING: """
=== CURRENT OBJECTIVE: PRICING ===
Your goal is to discuss value/pricing.
1. If possible, provide a range or estimate based on available data.
2. If exact pricing requires a quote, explain that and ask for necessary details.
3. Handle objections with empathy and value propositions.
""",

    ConversationStage.CTA: """
=== CURRENT OBJECTIVE: CLOSE / CTA ===
Your goal is to get a commitment.
1. Propose a specific next step (Call, Demo, Meeting).
2. Create urgency if appropriate.
3. Be clear and direct.
""",

    ConversationStage.FOLLOWUP: """
=== CURRENT OBJECTIVE: FOLLOW-UP ===
Your goal is to re-engage the user.
1. Reference the last conversation topic.
2. Ask if they have any further questions or are ready to proceed.
""",
    
    ConversationStage.FOLLOWUP_10M: """
=== CURRENT OBJECTIVE: 10-MINUTE FOLLOW-UP ===
The user expressed interest but hasn't replied in 10 minutes.
Send a brief, gentle nudge to see if they have any immediate questions about what you just discussed.
""",

    ConversationStage.FOLLOWUP_3H: """
=== CURRENT OBJECTIVE: 3-HOUR FOLLOW-UP ===
It's been 3 hours since the last interaction. 
Follow up to see if they've had a chance to consider the next steps or if they need more details to make a decision.
""",

    ConversationStage.FOLLOWUP_6H: """
=== CURRENT OBJECTIVE: 6-HOUR FOLLOW-UP ===
It's been 6 hours since the user last spoke.
Send a final professional check-in. Offer to schedule a quick call if that's easier for them than texting.
""",
    
    ConversationStage.CLOSED: """
=== CURRENT OBJECTIVE: CLOSED ===
The deal is closed. Be polite and professional.
Provide any final information or next steps.
""",

    ConversationStage.LOST: """
=== CURRENT OBJECTIVE: LOST ===
The user is not interested.
Be polite, thank them for their time, and end the conversation gracefully.
""",

    ConversationStage.GHOSTED: """
=== CURRENT OBJECTIVE: RE-ENGAGEMENT ===
The user stopped responding.
Send a gentle nudge to see if they are still interested.
"""
}

# ============================================================
# Factory Function
# ============================================================

def get_system_prompt(stage: ConversationStage, business_name: str, business_description: str = "", flow_prompt: str = "", max_words: int = 80) -> str:
    """
    Dynamically build the system prompt for the specific stage.
    """
    # Base instructions
    base = BASE_PERSONA.format(
        business_name=business_name, 
        business_description=business_description,
        max_words=max_words
    )
    
    # Stage instructions
    # Fallback to Qualification if stage missing
    instruction_template = STAGE_INSTRUCTIONS.get(stage, STAGE_INSTRUCTIONS[ConversationStage.QUALIFICATION])
    
    # Inject business-specific scripts into the template
    specific_instruction = instruction_template.format(flow_prompt=flow_prompt)
    
    return f"{base}\n\n{specific_instruction}"

# ============================================================
# Classify Factory (The Brain)
# ============================================================

from llm.prompts import CLASSIFY_BASE_INSTRUCTIONS, CLASSIFY_STAGE_INSTRUCTIONS

def get_classify_system_prompt(stage: ConversationStage, is_opening: bool = False) -> str:
    """
    Build the system prompt for Step 1 (Classify).
    Enforces stage-based isolation to eliminate context pollution.
    """
    # 1. Base instructions (behavior rules)
    base = CLASSIFY_BASE_INSTRUCTIONS
    
    # 2. Stage-specific rules (the router)
    # If opening message, force GREETING instructions regardless of input stage
    target_stage = ConversationStage.GREETING if is_opening else stage
    
    stage_rules = CLASSIFY_STAGE_INSTRUCTIONS.get(
        target_stage, 
        CLASSIFY_STAGE_INSTRUCTIONS[ConversationStage.QUALIFICATION]
    )
    
    # 3. Combine
    prompt = f"{base}\n\n{stage_rules}"
    
    # 4. Opening Message Exclusion
    if is_opening:
        prompt += "\nATTENTION: This is an OPENING message from a new lead. Do not reference any prior history."
    
    return prompt
