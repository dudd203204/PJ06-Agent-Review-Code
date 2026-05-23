from __future__ import annotations

from typing import Dict, List

from langchain_core.prompts import ChatPromptTemplate


SYSTEM_PROMPT = (
    "You are a senior code reviewer.\n"
    "Inspect the source file carefully and evaluate EVERY check defined in the skill definition.\n"
    "You must NOT skip any check — even if the check clearly passes.\n"
    "For each check, provide:\n"
    "  - Status: PASSED or FAILED\n"
    "  - Note / Feedback: a clear explanation of WHY it passes or fails, with evidence from the source.\n"
    "Do not propose solutions or code fixes. Base every decision only on evidence visible in the numbered source."
)

SYSTEM_MESSAGE_TEMPLATE = (
    f"{SYSTEM_PROMPT}\n\n"
    "Selected skill definition payload:\n"
    "[skill_definition]\n"
    "{skill_definition}\n"
    "[/skill_definition]\n\n"
    "CRITICAL OUTPUT RULES:\n"
    "1. Respond with a JSON array. Each element corresponds to exactly one check.\n"
    "2. You MUST include EVERY check key defined in the skill (e.g. A1, A2, B1, B2, C1, etc.). "
    "Do NOT omit any check — including ones that PASS.\n"
    "3. Each element must follow this format:\n"
    "   {{\"rule\": \"<check_id>\", \"status\": \"PASSED\" or \"FAILED\", "
    "\"feedback\": \"<explanation with evidence from source>\"}}\n"
    "4. The 'feedback' field is REQUIRED for every check, whether PASSED or FAILED.\n"
    "5. Do not include line numbers that are not visible in the numbered source."
)

HUMAN_MESSAGE_TEMPLATE = (
    "Review the file below and evaluate every check in the skill definition.\n\n"
    "Input file: {input_name}\n"
    "Numbered source:\n"
    "[numbered_source]\n"
    "{numbered_source_text}\n"
    "[/numbered_source]"
)


def build_review_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_MESSAGE_TEMPLATE),
            ("human", HUMAN_MESSAGE_TEMPLATE),
        ]
    )


def build_agent_review_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_MESSAGE_TEMPLATE),
            ("human", HUMAN_MESSAGE_TEMPLATE),
        ]
    )


def build_review_prompt_trace_templates() -> List[Dict[str, str]]:
    return [
        {"role": "system", "template": SYSTEM_MESSAGE_TEMPLATE},
        {"role": "human", "template": HUMAN_MESSAGE_TEMPLATE},
    ]
