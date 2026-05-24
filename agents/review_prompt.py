from __future__ import annotations

from typing import Dict, List

from langchain_core.prompts import ChatPromptTemplate


# ============================================================================
# IMPROVEMENT #1: Skill-Specific System Prompts
# ============================================================================

SYSTEM_PROMPT_GENERIC = (
    "You are a senior code reviewer.\n"
    "Inspect the source file carefully and evaluate EVERY check defined in the skill definition.\n"
    "You must NOT skip any check — even if the check clearly passes.\n"
    "For each check, provide:\n"
    "  - Status: PASSED or FAILED\n"
    "  - Note / Feedback: a clear explanation of WHY it passes or fails, with evidence from the source.\n"
    "Do not propose solutions or code fixes. Base every decision only on evidence visible in the numbered source."
)

SYSTEM_PROMPT_FORM_QUALITY = (
    "You are an expert Form.io quality validator.\n"
    "\n"
    "EXPERTISE:\n"
    "  - Form.io component naming conventions (camelCase requirement)\n"
    "  - JavaScript logic safety (null/undefined handling)\n"
    "  - Form structure and component nesting patterns\n"
    "  - Auto-generated vs intentional component keys\n"
    "\n"
    "CORE FOCUS:\n"
    "  1. Component key naming compliance (camelCase)\n"
    "  2. Auto-generated duplicate detection (numeric suffixes)\n"
    "  3. Admin field classification and prefixing\n"
    "  4. JavaScript logic safety in calculations\n"
    "  5. Form structure validity\n"
    "\n"
    "CRITICAL RULES:\n"
    "  - Evidence-based: Always reference exact line numbers and field paths\n"
    "  - Thorough: Check EVERY component (never skip due to file size)\n"
    "  - Comprehensive: When a check fails, list ALL violations (not just first)\n"
    "  - Precise: Provide violations with current→suggested values\n"
    "  - No assumptions: Only use explicitly visible JSON data\n"
    "  - ALL checks: Return EVERY check (A1, A2, A3) even if PASSED\n"
    "\n"
    "VIOLATION REPORTING IMPERATIVE:\n"
    "  - If check A1 fails: You MUST report ALL components with naming violations\n"
    "  - If check A3 fails: You MUST report ALL admin components without prefix\n"
    "  - Never report 'violations exist' without listing each one\n"
    "  - Never omit violations to save space - include all with line numbers"
)

SYSTEM_PROMPT_BACK_OFFICE = (
    "You are a back-office configuration security validator.\n"
    "\n"
    "EXPERTISE:\n"
    "  - Back-office form configuration and mapping\n"
    "  - Report generation security (Excel, UIB)\n"
    "  - Admin field exposure detection\n"
    "  - Business rule priority enforcement\n"
    "\n"
    "CORE FOCUS:\n"
    "  1. Form.IO URL mapping correctness\n"
    "  2. Business rule priority (Segment Rule > System Action)\n"
    "  3. Excel report configuration activation\n"
    "  4. Excel admin field exposure prevention\n"
    "  5. UIB configuration activation\n"
    "  6. UIB admin field exposure prevention\n"
    "\n"
    "CRITICAL RULES:\n"
    "  - Security first: Admin fields MUST NOT appear in reports\n"
    "  - Structural: Validate all required configs are active when needed\n"
    "  - Precise: Exact field paths and array indices\n"
    "  - Comprehensive: When a check fails, list ALL violations (not just first)\n"
    "  - Conditional: Some checks only apply if prerequisites are met\n"
    "  - ALL checks: Return EVERY check (B1-B6) without exception\n"
    "\n"
    "VIOLATION REPORTING IMPERATIVE:\n"
    "  - If check B4 fails (ADMIN fields exposed): List ALL exposed fields\n"
    "  - If check B6 fails (UIB ADMIN exposure): List ALL exposed fields\n"
    "  - Never omit violations - report all with field names and include_to_report values"
)

# ============================================================================
# IMPROVEMENT #2: Check-Specific Instructions
# ============================================================================

CHECK_INSTRUCTIONS_FORM_QUALITY = (
    "CHECKS TO EVALUATE (INDEPENDENTLY - do NOT mix them):\n"
    "\n"
    "═ A1 - camelCase Validation (Component Keys) ═\n"
    "  RULE: Component keys must follow camelCase - first word lowercase, subsequent words uppercase first letter, NO underscores, NO hyphens, NO spaces\n"
    "  \n"
    "  VALID camelCase examples (DO NOT REPORT THESE):\n"
    "    ✓ files  (single word, lowercase)\n"
    "    ✓ data  (single word, lowercase)\n"
    "    ✓ main  (single word, lowercase)\n"
    "    ✓ visitName  (first=lowercase, second=uppercase)\n"
    "    ✓ startDateOfVisit  (first=lowercase, others=uppercase)\n"
    "    ✓ noOfParent  (first=lowercase, others=uppercase)\n"
    "    ✓ dropdownA  (first=lowercase, second=uppercase)\n"
    "    ✓ testTextField1  (camelCase with numbers is OK for A1 - A2 handles numbers separately)\n"
    "\n"
    "  INVALID camelCase examples (REPORT THESE):\n"
    "    ✗ sys_attachment_auth  (has underscores - VIOLATION)\n"
    "    ✗ VisitName  (starts uppercase - VIOLATION)\n"
    "    ✗ visit_name  (has underscores - VIOLATION)\n"
    "    ✗ visit-name  (has hyphens - VIOLATION)\n"
    "    ✗ visit name  (has spaces - VIOLATION)\n"
    "\n"
    "  FOCUS ON: \"key\" field naming only (NOT \"label\")\n"
    "  EXCEPTION: Ignore \"ADMIN_Sys Attachment Auth\" ONLY if inside Admin panel AND key is sys_attachment_auth\n"
    "  EXCEPTION: Ignore type=htmlelement and type=columns\n"
    "  \n"
    "  CRITICAL RULE: Report ONLY components that have underscore, hyphen, space, or start with uppercase.\n"
    "  DO NOT report keys that already match the valid examples above.\n"
    "  DO NOT report keys just because the label has multiple words - check the key value, not the label.\n"
    "  DO NOT MIX: Don't evaluate admin prefix (that's A3), don't check numeric suffix (that's A2)\n"
    "\n"
    "═ A2 - Auto-Generated Numeric Suffix Detection ═\n"
    "  FOCUS ON: \"key\" field ending with numbers only\n"
    "  RULE: Keys should not end with 1, 2, 3... etc (testField1 → testField)\n"
    "  EXCEPTION: Ignore type=html, htmlelement, columns\n"
    "  WHAT TO REPORT: ONLY components with keys ending in digits (testField1, name2, component99)\n"
    "  DO NOT MIX: Don't evaluate camelCase (that's A1), don't check admin prefix (that's A3)\n"
    "\n"
    "═ A3 - ADMIN_ Prefix Classification ═\n"
    "  FOCUS ON: \"label\" field prefix only (NOT \"key\")\n"
    "  RULE: Components INSIDE Admin panel must have labels starting with ADMIN_ (ADMIN_Approver, ADMIN_Rejection)\n"
    "  SCOPE: Only check components that are direct/nested children of the panel with label=\"Admin\"\n"
    "  WHAT TO REPORT: ONLY components inside Admin panel whose label does NOT start with ADMIN_\n"
    "  DO NOT MIX: Don't evaluate key naming (that's A1), don't check numeric suffixes (that's A2)\n"
    "\n"
    "CRITICAL SEPARATION RULE:\n"
    "  • A1 evaluates KEYS (must be camelCase)\n"
    "  • A2 evaluates KEYS (must not end in numbers)\n"
    "  • A3 evaluates LABELS in Admin panel (must start with ADMIN_)\n"
    "  These are COMPLETELY INDEPENDENT - a component can PASS A1/A2 but FAIL A3"
)


CHECK_INSTRUCTIONS_BACK_OFFICE = (
    "CHECKS TO EVALUATE (in dependency order):\n"
    "\n"
    "B1 - Form.IO URL Validation (PREREQUISITE)\n"
    "  └─ Focus: Must start with 'https://formio-staging/d-'\n"
    "  └─ Impact: Prerequisite for B2-B6 context\n"
    "\n"
    "B2 - Business Rule Priority\n"
    "  └─ Focus: Segment Rule takes precedence over System Action\n"
    "  └─ Impact: Critical for business logic flow\n"
    "\n"
    "B3 - Excel Config Active (PREREQUISITE for B4)\n"
    "  └─ Focus: excel_configs.is_active must be true\n"
    "  └─ Conditional: Skip B4 if B3 not active\n"
    "\n"
    "B4 - Excel Admin Field Exposure (depends on B3)\n"
    "  └─ Focus: ADMIN_ fields with include_to_report=true\n"
    "  └─ Security: Must not expose admin fields in reports\n"
    "\n"
    "B5 - UIB Config Active (PREREQUISITE for B6)\n"
    "  └─ Focus: uib_configs.is_active must be true\n"
    "  └─ Conditional: Skip B6 if B5 not active\n"
    "\n"
    "B6 - UIB Admin Field Exposure (depends on B5)\n"
    "  └─ Focus: ADMIN_ fields in uib_fields\n"
    "  └─ Security: Must not expose admin fields in UIB"
)

# ============================================================================
# IMPROVEMENT #3: Evidence Format Specification
# ============================================================================

EVIDENCE_FORMAT = (
    "FEEDBACK QUALITY REQUIREMENTS:\n"
    "\n"
    "For PASSED checks - Format:\n"
    "  'Checked [WHAT]. Result: [EVIDENCE]. Status: PASSED.'\n"
    "  Example: 'Checked all 45 components. All follow camelCase (firstName, lastName, emailAddress). PASSED.'\n"
    "\n"
    "For FAILED checks - MUST include (1) WHAT + WHERE (2) WHY (3) FIX:\n"
    "  Format:\n"
    "    'Line XXXX: Component \"LABEL\" has key=\"KEY\". \n"
    "     Issue: [SPECIFIC VIOLATION]. \n"
    "     Suggestion: Change to \"CORRECTED_KEY\".'\n"
    "\n"
    "  Example (GOOD - single violation):\n"
    "    'Line 0156: Component \"Customer\" has key=\"customer_name\" (contains underscore).\n"
    "     Issue: Violates camelCase naming requirement.\n"
    "     Suggestion: Change key to \"customerName\".'\n"
    "\n"
    "  Example (GOOD - MULTIPLE violations in one check):\n"
    "    'Found 3 naming violations:\n"
    "     Line 0156: Component \"Customer\" has key=\"customer_name\". Suggestion: \"customerName\".\n"
    "     Line 0234: Component \"Email Address\" has key=\"email_address\". Suggestion: \"emailAddress\".\n"
    "     Line 0567: Component \"Phone Number\" has key=\"phone_number\". Suggestion: \"phoneNumber\".'\n"
    "\n"
    "  Example (BAD - incomplete):\n"
    "    'Line 0156: Component \"Customer\" has naming issue.' → Missing suggestion\n"
    "    'Some components violate naming.' → Which ones? Which lines?\n"
    "    'Multiple naming issues found' → Missing specifics\n"
    "\n"
    "CRITICAL: Report EVERY violation:\n"
    "  ✅ If check fails due to 1 violation: List that 1 violation with full details\n"
    "  ✅ If check fails due to 3 violations: List ALL 3 violations with line numbers\n"
    "  ✅ If check fails due to 10 violations: List ALL 10 violations (use compact format if needed)\n"
    "  ❌ NEVER omit violations or list only the first one\n"
    "  ❌ NEVER say 'Multiple violations exist' without listing them\n"
    "\n"
    "SPECIFICITY: Always include:\n"
    "  ✅ Exact line number (matching numbered source) for EACH violation\n"
    "  ✅ Component label and field path\n"
    "  ✅ Current value and suggested value\n"
    "  ✅ When multiple violations: Use format 'Line XXXX: ..., Line YYYY: ...'\n"
    "  ❌ Generic explanations without line numbers"
)

# ============================================================================
# IMPROVEMENT #4: Failure Case Handling Matrix
# ============================================================================

FAILURE_MATRIX = (
    "FAILURE CRITERIA (What makes each check FAILED):\n"
    "\n"
    "B1 (Form.IO URL):\n"
    "  FAIL: form.form_url missing OR not starting with 'https://formio-staging/d-'\n"
    "  PASS: form.form_url exists AND has correct prefix\n"
    "\n"
    "B3 (Excel Config Active):\n"
    "  FAIL: excel_configs missing OR is_active is false\n"
    "  PASS: excel_configs.is_active is true\n"
    "  NOT_APPLICABLE: JSON explicitly indicates Excel reports not used\n"
    "\n"
    "B4 (Excel Admin Field Exposure) - IMPORTANT LOGIC:\n"
    "  FAIL: Value starts with ADMIN_ AND include_to_report=true\n"
    "        (This means ADMIN field WILL appear in Excel report)\n"
    "  PASS: No values starting with ADMIN_ OR\n"
    "        All ADMIN_ values have include_to_report=false\n"
    "        (ADMIN fields won't appear in report - safe)\n"
    "  EXAMPLE PASS: ADMIN_Sys Attachment (value) + include_to_report=false\n"
    "                → Report won't include this field, so it's SAFE\n"
    "  EXAMPLE FAIL: ADMIN_Sys Attachment (value) + include_to_report=true\n"
    "                → Report WILL include this field, so it FAILS"
)

# ============================================================================
# IMPROVEMENT #8: Retry Instructions
# ============================================================================

RETRY_INSTRUCTION = (
    "RESPONSE VALIDATION:\n"
    "\n"
    "Your response will be validated for:\n"
    "  1. Valid JSON array format\n"
    "  2. ALL checks present (no omissions)\n"
    "  3. Every check has required fields\n"
    "  4. FAILED checks include ALL violations (not just first one)\n"
    "\n"
    "If validation fails:\n"
    "  - You will be asked to retry\n"
    "  - Next attempt may use SIMPLIFIED version of this prompt\n"
    "\n"
    "TIPS FOR SUCCESSFUL RESPONSE:\n"
    "  ✅ Return valid JSON array (verify syntax)\n"
    "  ✅ Include EVERY check (even if PASSED)\n"
    "  ✅ Each check has three fields: rule, status, feedback\n"
    "  ✅ Every FAILED check needs specific line number(s)\n"
    "  ✅ For FAILED checks with MULTIPLE violations: List ALL of them\n"
    "  ✅ Include line number for each violation\n"
    "  ✅ Keep feedback clear and concise (50-300 chars per check, longer if multiple violations)\n"
    "  ✅ Quote exact values from the source\n"
    "\n"
    "MULTIPLE VIOLATIONS RULE:\n"
    "  If a FAILED check has more than 1 violation:\n"
    "  - MUST list all violations found\n"
    "  - Each violation needs its own line number\n"
    "  - Separate violations with commas or semicolons\n"
    "  - Example: 'Lines 0001, 0034, 0156 all have issue X...'\n"
    "\n"
    "If you cannot evaluate all checks:\n"
    "  - Provide status INCOMPLETE\n"
    "  - Include all checks you did evaluate\n"
    "  - Explain which checks couldn't be evaluated and why"
)

# ============================================================================
# Line Number Reference (IMPROVEMENT #5)
# ============================================================================

LINE_REFERENCE_INSTRUCTION = (
    "LINE NUMBER USAGE:\n"
    "\n"
    "Every line in the source is numbered with 4 digits:\n"
    "  0001 | {{...\n"
    "  0002 | ...\n"
    "  0156 | \"key\": \"value\"\n"
    "\n"
    "When referencing violations:\n"
    "  ✅ CORRECT: 'Line 0156: key=\"customer_name\"'\n"
    "  ✅ CORRECT: 'Lines 0156, 0234, 0567 have violations'\n"
    "  ❌ WRONG: 'Line 156' (missing leading zero)\n"
    "  ❌ WRONG: 'Around line 156' (be exact)\n"
    "\n"
    "Always quote the exact text from that line:\n"
    "  'Line 0156: \"key\": \"customer_name\" → should be \"customerName\"'"
)


# ============================================================================
# Main Template Building Functions
# ============================================================================

def get_system_prompt_for_skillset(skillset: str) -> str:
    """Return skill-specific system prompt based on skillset."""
    prompts = {
        "form_quality": SYSTEM_PROMPT_FORM_QUALITY,
        "back_office_quality": SYSTEM_PROMPT_BACK_OFFICE,
    }
    return prompts.get(skillset, SYSTEM_PROMPT_GENERIC)


def get_check_instructions_for_skillset(skillset: str) -> str:
    """Return check-specific instructions based on skillset."""
    instructions = {
        "form_quality": CHECK_INSTRUCTIONS_FORM_QUALITY,
        "back_office_quality": CHECK_INSTRUCTIONS_BACK_OFFICE,
    }
    return instructions.get(skillset, "")


def get_check_instructions_for_skill_definition(skill_definition: dict, skillset: str) -> str:
    """Extract check IDs from skill definition and build skill-specific instructions."""
    # If skill_definition has 'skill' with check definitions, use those
    if not skill_definition or 'skill' not in skill_definition:
        return get_check_instructions_for_skillset(skillset)
    
    skill_checks = skill_definition.get('skill', {})
    
    # If it's a dict, keys are check IDs (D1, D2, D3 for run_time_quality)
    if isinstance(skill_checks, dict):
        check_ids = sorted(skill_checks.keys())
    # If it's a list, extract id field
    elif isinstance(skill_checks, list):
        check_ids = [item.get('id', f'check_{i}') for i, item in enumerate(skill_checks) if isinstance(item, dict)]
    else:
        check_ids = []
    
    if not check_ids:
        return get_check_instructions_for_skillset(skillset)
    
    # Build skill-specific instructions for only these checks
    instruction_lines = [
        f"CHECKS TO EVALUATE (ONLY these {len(check_ids)} checks):\n"
    ]
    
    for check_id in check_ids:
        check_data = skill_checks.get(check_id, {}) if isinstance(skill_checks, dict) else {}
        review_item = check_data.get('review_item', f'Check {check_id}')
        description = check_data.get('description', '')
        
        instruction_lines.append(f"\n{check_id} - {review_item}")
        if description:
            # Indent description
            desc_lines = description.split('\n')
            for desc_line in desc_lines[:2]:  # Limit to 2 lines
                instruction_lines.append(f"  └─ {desc_line}")
    
    return "\n".join(instruction_lines)


def build_system_message_template(skillset: str, skill_definition: dict) -> str:
    """Build complete system message with all improvements."""
    system_base = get_system_prompt_for_skillset(skillset)
    
    # Extract check IDs from skill definition to build skill-specific instructions
    check_instructions = get_check_instructions_for_skill_definition(skill_definition, skillset)
    
    # Build template - escape JSON braces to prevent ChatPromptTemplate from parsing them as variables
    # Use quadruple braces {{{{}}} to escape properly for template parsing
    template_parts = [
        system_base,
        "",
        check_instructions,
        "",
        LINE_REFERENCE_INSTRUCTION,
        "",
        FAILURE_MATRIX,
        "",
        EVIDENCE_FORMAT,
        "",
        RETRY_INSTRUCTION,
        "",
        "Selected skill definition payload:",
        "[skill_definition]",
        "{skill_definition}",
        "[/skill_definition]",
        "",
        "CRITICAL OUTPUT FORMAT:",
        "Return a JSON array with EVERY check (example format):",
        "[",
        '  {{"rule": "B1", "status": "PASSED", "feedback": "..."}},',
        '  {{"rule": "B2", "status": "FAILED", "feedback": "..."}},',
        "  ...",
        "]",
        "",
        "Rules:",
        "1. EVERY check MUST be present in response",
        "2. status field values must be exactly PASSED or FAILED",
        "3. feedback field REQUIRED for every check (even for PASSED)",
        "4. feedback for FAILED checks MUST have specific evidence with line numbers"
    ]
    
    return "\n".join(template_parts)


SYSTEM_MESSAGE_TEMPLATE = "{system_message_template_will_be_built_dynamically}"

HUMAN_MESSAGE_TEMPLATE = (
    "Review the file below and evaluate EVERY check in the skill definition.\n\n"
    "Input file: {input_name}\n"
    "Numbered source:\n"
    "[numbered_source]\n"
    "{numbered_source_text}\n"
    "[/numbered_source]\n\n"
    "Evaluate all checks independently and return JSON array with every check."
)


def build_review_prompt(skillset: str = "default", skill_definition: dict = None) -> ChatPromptTemplate:
    """Build optimized review prompt with skill-specific improvements."""
    if skill_definition is None:
        skill_definition = {}
    
    # Build system message BEFORE creating template to avoid variable parsing issues
    system_message_content = build_system_message_template(skillset, skill_definition)
    
    # Use literal system message (not templated) to avoid ChatPromptTemplate parsing JSON examples
    # This prevents {"rule"} being interpreted as a variable
    return ChatPromptTemplate.from_messages(
        [
            ("system", system_message_content),
            ("human", HUMAN_MESSAGE_TEMPLATE),
        ]
    )


def build_agent_review_prompt(skillset: str = "default", skill_definition: dict = None) -> ChatPromptTemplate:
    """Alias for build_review_prompt for backward compatibility."""
    return build_review_prompt(skillset, skill_definition)


def build_review_prompt_trace_templates(skillset: str = "default", skill_definition: dict = None) -> List[Dict[str, str]]:
    """Build prompt trace templates with skill-specific improvements."""
    if skill_definition is None:
        skill_definition = {}
    
    system_message = build_system_message_template(skillset, skill_definition)
    
    return [
        {"role": "system", "template": system_message},
        {"role": "human", "template": HUMAN_MESSAGE_TEMPLATE},
    ]
