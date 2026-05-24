"""Per-check LLM execution for focused evaluation of individual checks."""

import json
from typing import Any, Dict, Optional
from langchain_core.prompts import ChatPromptTemplate


def create_per_check_skill_definition(skill_definition: Dict[str, Any], check_id: str) -> Dict[str, Any]:
    """
    Extract a single check from a skill definition and create a focused sub-skill.
    
    Args:
        skill_definition: Full skill definition with multiple checks
        check_id: The specific check ID to extract (e.g., 'A1', 'A3', 'D1')
    
    Returns:
        Focused skill definition containing only the specified check
    """
    skill_copy = json.loads(json.dumps(skill_definition))  # Deep copy
    
    if 'skill' not in skill_copy or check_id not in skill_copy['skill']:
        return skill_copy  # Return as-is if check not found
    
    # Extract only the target check
    target_check = skill_copy['skill'][check_id]
    
    # Rebuild skill definition with only this check
    skill_copy['skill'] = {check_id: target_check}
    
    # Update response format to only include this check
    if 'output_style' in skill_copy and 'format' in skill_copy['output_style']:
        if check_id in skill_copy['output_style']['format']:
            skill_copy['output_style']['format'] = {
                check_id: skill_copy['output_style']['format'][check_id]
            }
    
    # Simplify description to focus on this check
    review_item = target_check.get('review_item', f'Check {check_id}')
    skill_copy['description'] = (
        f"This skill evaluates a single check: {check_id} - {review_item}\n\n"
        f"Original description: {skill_copy.get('description', 'N/A')}"
    )
    
    return skill_copy


def build_per_check_prompt(
    skillset: str,
    skill_definition: Dict[str, Any],
    check_id: str
) -> ChatPromptTemplate:
    """
    Build a focused prompt for a single check.
    
    Args:
        skillset: The skillset ('form_quality', 'back_office_quality', etc.)
        skill_definition: Full skill definition
        check_id: The specific check ID
    
    Returns:
        ChatPromptTemplate for focused check evaluation
    """
    from agents.review_prompt import get_system_prompt_for_skillset
    
    # Extract check-specific definition
    per_check_skill = create_per_check_skill_definition(skill_definition, check_id)
    
    # Get system prompt (skill-specific)
    system_prompt = get_system_prompt_for_skillset(skillset)
    
    # Build check-specific instruction
    if 'skill' in per_check_skill and check_id in per_check_skill['skill']:
        check_data = per_check_skill['skill'][check_id]
        review_item = check_data.get('review_item', f'Check {check_id}')
        description = check_data.get('description', '')
        goal = check_data.get('goal', '')
        
        check_instruction = (
            f"FOCUSED CHECK EVALUATION:\n"
            f"\nCheck ID: {check_id}\n"
            f"Review Item: {review_item}\n"
            f"\nDescription:\n{description}\n"
            f"\nGoal:\n{goal}\n"
            f"\nPROCEDURE:\n"
        )
        
        if 'procedure' in check_data:
            procedures = check_data['procedure']
            if isinstance(procedures, list):
                for step in procedures:
                    check_instruction += f"  • {step}\n"
        
        check_instruction += (
            f"\n\nRETURN ONLY THIS CHECK:\n"
            f"You must evaluate ONLY check {check_id}.\n"
            f"Return a JSON object with exactly one key:\n"
            f'{{\n'
            f'  "{check_id}": {{\n'
            f'    "Status": "PASSED" or "FAILED",\n'
            f'    "Note / Feedback": "Your detailed feedback"\n'
            f'  }}\n'
            f'}}\n'
        )
    else:
        check_instruction = f"Evaluate check {check_id} only."
    
    # Build message template with focus on single check
    system_with_check = (
        f"{system_prompt}\n\n"
        f"{check_instruction}"
    )
    
    human_template = (
        "FILE: {input_name}\n"
        "NUMBERED SOURCE:\n{numbered_source_text}\n\n"
        "SKILL DEFINITION:\n{skill_definition}\n\n"
        "Evaluate ONLY check {check_id} and return valid JSON with that check only."
    )
    
    return ChatPromptTemplate.from_messages([
        ("system", system_with_check),
        ("human", human_template),
    ])


def build_per_check_prompt_values(
    input_name: str,
    numbered_source_text: str,
    skill_definition: Dict[str, Any],
    check_id: str
) -> Dict[str, str]:
    """
    Build prompt values for per-check evaluation.
    """
    per_check_skill = create_per_check_skill_definition(skill_definition, check_id)
    
    return {
        "input_name": input_name,
        "numbered_source_text": numbered_source_text,
        "skill_definition": json.dumps(per_check_skill, indent=2),
        "check_id": check_id,
    }
