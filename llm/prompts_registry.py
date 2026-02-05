"""
Prompt Registry: Dynamic System Prompts for Router-Agent Architecture.
This module provides factory functions to assemble prompts from constants in llm.prompts.
"""
from server.enums import ConversationStage
from llm.prompts import (
    BASE_PERSONA,
    GENERATE_STAGE_INSTRUCTIONS,
    CLASSIFY_BASE_INSTRUCTIONS,
    CLASSIFY_STAGE_RULES
)

# ============================================================
# Factory Functions
# ============================================================

def get_system_prompt(
    stage: ConversationStage, 
    business_name: str, 
    business_description: str = "", 
    flow_prompt: str = "", 
    max_words: int = 80
) -> str:
    """
    Dynamically build the system prompt for Step 2 (Generate).
    Enriched with business context (The Mouth).
    """
    # 1. Base instructions (Identity & Persona)
    base = BASE_PERSONA.format(
        business_name=business_name, 
        business_description=business_description,
        flow_prompt=flow_prompt,
        max_words=max_words
    )
    
    # 2. Stage-specific instructions (The Mouth)
    # Fallback to Qualification if stage missing
    instruction_template = GENERATE_STAGE_INSTRUCTIONS.get(
        stage, 
        GENERATE_STAGE_INSTRUCTIONS[ConversationStage.QUALIFICATION]
    )
    
    return f"{base}\n\n{instruction_template}"


def get_classify_system_prompt(
    stage: ConversationStage, 
    is_opening: bool = False, 
    flow_prompt: str = ""
) -> str:
    """
    Build the system prompt for Step 1 (Classify).
    Enforces stage-based isolation to eliminate context pollution (The Brain).
    """
    # 1. Base instructions (Strategy Rules)
    base = CLASSIFY_BASE_INSTRUCTIONS.format(flow_prompt=flow_prompt)
    
    # 2. Stage-specific rules (The Router)
    # If opening message, force GREETING instructions regardless of input stage
    target_stage = ConversationStage.GREETING if is_opening else stage
    
    stage_rules = CLASSIFY_STAGE_RULES.get(
        target_stage, 
        CLASSIFY_STAGE_RULES[ConversationStage.QUALIFICATION]
    )
    
    # 3. Combine
    prompt = f"{base}\n\n{stage_rules}"
    
    # 4. Opening Message Exclusion
    if is_opening:
        prompt += "\nATTENTION: This is an OPENING message from a new lead. Do not reference any prior history."
    return prompt
