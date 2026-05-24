from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.review_prompt import (
    build_review_prompt,
    build_review_prompt_trace_templates,
)
from tools.agent_input_trace import build_prompt_trace, update_agent_input_trace_skill
from tools.review_source import build_numbered_source_text
from tools.skill_loader import SkillLoadError, load_skill_bundle
from utils.logger import get_logger

logger = get_logger()


def _validate_input_file_size(
    raw_source_text: str,
    skillset: Optional[str] = None,
    skill_name: Optional[str] = None,
) -> tuple[bool, str]:
    """
    IMPROVEMENT #6: Validate input file size before processing.
    Returns (is_valid, message)
    
    Size limits:
    - form_quality: 50KB (forms are typically small)
    - back_office_quality: 200KB (backoffice configs can be larger)
    - default: 100KB
    """
    file_size_bytes = len(raw_source_text.encode('utf-8'))
    file_size_kb = file_size_bytes / 1024
    
    # Determine size limit based on skillset
    if skillset == "form_quality":
        size_limit_kb = 50
    elif skillset == "back_office_quality":
        size_limit_kb = 200
    else:
        size_limit_kb = 100
    
    if file_size_kb > size_limit_kb:
        return False, (
            f"Input file too large: {file_size_kb:.1f}KB (limit: {size_limit_kb}KB) "
            f"for skillset={skillset or 'default'} skill={skill_name or '?'}"
        )
    
    return True, f"Input file size OK: {file_size_kb:.1f}KB (limit: {size_limit_kb}KB)"


@dataclass(frozen=True)
class AgentInvocationTarget:
    runnable: Any
    uses_messages_input: bool


def _rendered_message_dicts(messages: Any) -> List[Dict[str, str]]:
    raw_messages = messages.to_messages() if hasattr(messages, "to_messages") else getattr(messages, "messages", [])
    rendered: List[Dict[str, str]] = []
    for message in raw_messages:
        rendered.append(
            {
                "role": str(getattr(message, "type", message.__class__.__name__)),
                "content": str(getattr(message, "content", "")),
            }
        )
    return rendered


def _create_agent_executor(
    *,
    llm: Any,
    prompt: Any,
    response_format: Dict[str, Any],
    max_agent_iterations: int,
    verbose: bool,
) -> Any:
    logger.debug("Creating direct LLM invoker (no agent tools needed)")
    # No agent needed - just invoke LLM directly on rendered prompt
    return AgentInvocationTarget(
        runnable=llm,
        uses_messages_input=True,
    )


def build_agent_response_format_schema(*, skill_name: str, response_format: Dict[str, Any]) -> Dict[str, Any]:
    logger.debug("Starting build_agent_response_format_schema for skill=%s", skill_name)
    logger.debug("response_format type=%s keys=%s", type(response_format), list(response_format.keys()) if isinstance(response_format, dict) else "N/A")
    
    properties: Dict[str, Any] = {}
    required_checks: List[str] = []

    for check_id, check_format in response_format.items():
        logger.debug("Processing check_id=%s type=%s", check_id, type(check_format))
        if not isinstance(check_format, dict) or not check_format:
            logger.debug("Skipping check_id=%s not a dict or empty", check_id)
            continue

        field_properties: Dict[str, Any] = {}
        required_fields: List[str] = []
        for field_name, field_description in check_format.items():
            logger.debug("Processing field_name=%s type=%s", field_name, type(field_description))
            field_schema: Dict[str, Any] = {
                "type": "string",
                "description": str(field_description),
            }
            if field_name.lower() == "status":
                field_schema["enum"] = ["PASSED", "FAILED"]
            field_properties[str(field_name)] = field_schema
            required_fields.append(str(field_name))

        if not field_properties:
            logger.debug("Skipping check_id=%s no field properties", check_id)
            continue

        check_name = str(check_id)
        properties[check_name] = {
            "type": "object",
            "properties": field_properties,
            "required": required_fields,
            "additionalProperties": False,
        }
        required_checks.append(check_name)

    if not properties:
        raise ValueError("Skill response_format must contain at least one check format")

    logger.debug("Schema built successfully with %d checks", len(properties))
    return {
        "title": f"{skill_name}_response_format",
        "description": "Structured skill review output generated from output_style.format.",
        "type": "object",
        "properties": properties,
        "required": required_checks,
        "additionalProperties": False,
    }


def _simplify_skill_definition(skill_bundle: Dict[str, Any], simplification_level: int) -> Dict[str, Any]:
    """
    IMPROVEMENT #5: Simplify skill definition for retry attempts.
    Level 0: Original (full)
    Level 1: Medium (simplified procedures)
    Level 2: Minimal (just check IDs and names)
    """
    simplified = json.loads(json.dumps(skill_bundle))  # Deep copy
    
    if simplification_level < 1:
        return simplified  # Return original
    
    # Level 1: Simplify procedures (keep first line only, max 100 chars per check)
    if simplification_level >= 1:
        if "checks" in simplified and isinstance(simplified["checks"], list):
            for check in simplified["checks"]:
                if "procedure" in check and isinstance(check["procedure"], list):
                    # Keep only first line of procedure
                    first_line = check["procedure"][0] if check["procedure"] else ""
                    check["procedure"] = [first_line[:100]] if first_line else []
    
    # Level 2: Minimal (keep only check ID and name)
    if simplification_level >= 2:
        if "checks" in simplified and isinstance(simplified["checks"], list):
            for check in simplified["checks"]:
                # Keep only id and name, remove procedure details
                check_id = check.get("id")
                check_name = check.get("name")
                # Clear procedure
                check["procedure"] = [f"Validate {check_name or check_id}"]
    
    return simplified


def _message_to_agent_dict(message: Any) -> Dict[str, str]:
    logger.debug("Converting message to dict: type=%s", type(message))
    role = str(getattr(message, "type", message.__class__.__name__))
    if role == "human":
        role = "user"
    elif role == "ai":
        role = "assistant"
    return {
        "role": role,
        "content": str(getattr(message, "content", "")),
    }


def _agent_messages_input(messages: Any) -> List[Dict[str, str]]:
    logger.debug("Processing agent messages input: type=%s hasattr_to_messages=%s", type(messages), hasattr(messages, "to_messages"))
    raw_messages = messages.to_messages() if hasattr(messages, "to_messages") else getattr(messages, "messages", [])
    logger.debug("Got raw_messages: type=%s len=%s", type(raw_messages), len(raw_messages) if isinstance(raw_messages, (list, tuple)) else "N/A")
    result = [_message_to_agent_dict(message) for message in raw_messages]
    logger.debug("Processed %d messages", len(result))
    return result


def _invoke_agent(
    *,
    agent_executor: Any,
    prompt_values: Dict[str, str],
    messages: Any,
    max_agent_iterations: int,
) -> Any:
    logger.debug("Invoking LLM directly on rendered messages")
    runnable = getattr(agent_executor, "runnable", agent_executor)
    logger.debug("LLM type=%s", type(runnable))
    
    # Invoke LLM directly on the pre-rendered messages
    logger.debug("Calling LLM.invoke on rendered prompt messages")
    response = runnable.invoke(messages)
    logger.debug("LLM response type=%s", type(response))
    
    # Extract string content from LLM response (handles AIMessage, str, etc.)
    if isinstance(response, str):
        return response
    elif hasattr(response, "content"):
        return response.content
    else:
        return str(response)


def _extract_json_object(text: str) -> Dict[str, Any]:
    if not text or not text.strip():
        return {}  # Return empty dict for empty responses
    
    stripped = text.strip()
    
    # Remove code fence if present
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()
    
    # Try direct parse first
    try:
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload
        elif isinstance(payload, list) and len(payload) > 0:
            # If it's a list of dicts with violation format like [{"line": "...", "violation": "..."}, ...]
            # Return it as-is - will be handled specially in parse_agent_result
            return {"_raw_list": payload}
    except json.JSONDecodeError:
        pass
    
    # If direct parse fails, try wrapping in braces (handles "K1: {...} K2: {...}")
    try:
        wrapped = "{" + stripped + "}"
        payload = json.loads(wrapped)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    
    # Last resort: try to extract a valid JSON object from corrupted text
    # Find all {...} patterns and try to parse them
    json_patterns = re.findall(r"\{[^{}]*(?:\{[^{}]*(?:\{[^{}]*\})*[^{}]*\})*[^{}]*\}", stripped, re.DOTALL)
    for pattern in json_patterns:
        try:
            payload = json.loads(pattern)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            continue
    
    return {}  # Return empty dict if all parsing fails


def _validate_dynamic_response_payload(payload: Dict[str, Any], response_format: Dict[str, Any]) -> Dict[str, Any]:
    for check_id, check_format in response_format.items():
        check_name = str(check_id)
        if check_name not in payload:
            # IMPROVEMENT #2: LLM omitted this check — mark as INCOMPLETE, not PASSED
            # This prevents false negatives where omitted checks are silently treated as passed
            logger.warning(
                "LLM omitted check %s — marking as INCOMPLETE for manual review",
                check_name
            )
            payload[check_name] = {
                "Status": "INCOMPLETE",
                "Note / Feedback": "Check not evaluated by LLM — requires manual review"
            }
            continue
        if not isinstance(payload[check_name], dict):
            # If check value is not a dict, replace with FAILED
            payload[check_name] = {"Status": "FAILED", "Note / Feedback": "Invalid check format"}
            continue
        if not isinstance(check_format, dict):
            continue
        
        # Get the Status value if present
        check_status = payload[check_name].get("Status", "").upper() if "Status" in payload[check_name] else None
        
        for field_name in check_format:
            field_key = str(field_name)
            
            # Make "Note / Feedback" optional for PASSED checks
            # It's only required when Status is FAILED or INCOMPLETE
            if field_key == "Note / Feedback" and check_status in ("PASSED",):
                continue
            
            if field_key not in payload[check_name]:
                # Fill in missing field with default value
                if field_key == "Status":
                    payload[check_name][field_key] = "INCOMPLETE"
                else:
                    payload[check_name][field_key] = ""
            if not isinstance(payload[check_name].get(field_key, ""), str):
                payload[check_name][field_key] = str(payload[check_name].get(field_key, ""))
    return payload


def _validate_feedback_quality(payload: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    IMPROVEMENT #3: Validate feedback quality for all checks.
    Returns (is_valid, list_of_issues)
    """
    issues: List[str] = []
    
    for check_id, check_payload in payload.items():
        if not isinstance(check_payload, dict):
            continue
        
        status = str(check_payload.get("Status", "")).upper()
        feedback = str(check_payload.get("Note / Feedback", "")).strip()
        
        # PASSED checks can have empty feedback
        if status == "PASSED":
            continue
        
        # FAILED and INCOMPLETE checks MUST have meaningful feedback
        if status in ("FAILED", "INCOMPLETE"):
            # Check minimum length
            if len(feedback) < 15:
                issues.append(
                    f"Check {check_id} ({status}): Feedback too brief ({len(feedback)} chars, need ≥15). "
                    f"Feedback: '{feedback}'"
                )
            
            # For FAILED checks, look for line numbers or specific evidence
            if status == "FAILED" and "line" not in feedback.lower() and "found" not in feedback.lower():
                issues.append(
                    f"Check {check_id} ({status}): Missing line number or specific evidence. "
                    f"Feedback should include 'Line XXXX' or specific violation locations."
                )
    
    return len(issues) == 0, issues


def _validate_response_structure(
    payload: Dict[str, Any],
    response_format: Dict[str, Any]
) -> tuple[bool, List[str]]:
    """
    IMPROVEMENT #4: Validate response structure before returning results.
    Returns (is_valid, list_of_issues)
    """
    issues: List[str] = []
    required_checks = set(str(k) for k in response_format.keys())
    present_checks = set(str(k) for k in payload.keys() if isinstance(payload.get(k), dict))
    
    # Check if all required checks are present
    missing_checks = required_checks - present_checks
    if missing_checks:
        issues.append(f"Missing checks in response: {', '.join(sorted(missing_checks))}")
    
    # Check that each check has required fields
    for check_id in required_checks:
        check_id_str = str(check_id)
        if check_id_str not in payload:
            continue
        
        check_payload = payload[check_id_str]
        if not isinstance(check_payload, dict):
            issues.append(f"Check {check_id_str}: Not a dictionary")
            continue
        
        # Every check must have Status
        if "Status" not in check_payload:
            issues.append(f"Check {check_id_str}: Missing 'Status' field")
        else:
            status = str(check_payload.get("Status", "")).upper()
            if status not in ("PASSED", "FAILED", "INCOMPLETE"):
                issues.append(
                    f"Check {check_id_str}: Invalid Status '{status}' "
                    f"(must be PASSED, FAILED, or INCOMPLETE)"
                )
    
    # Validate feedback quality
    quality_is_valid, quality_issues = _validate_feedback_quality(payload)
    if not quality_is_valid:
        # Log quality issues but don't fail on them (just warnings)
        for issue in quality_issues:
            logger.warning("Feedback quality issue: %s", issue)
    
    return len(issues) == 0, issues


def _invoke_agent_with_retry(
    agent_executor: Any,
    llm: Any,
    prompt: Any,
    skill_bundle: Dict[str, Any],
    skillset: Optional[str],
    prompt_values: Dict[str, Any],
    messages: Any,
    response_format: Dict[str, Any],
    max_agent_iterations: int,
    skill_name: str,
) -> Dict[str, Any]:
    """
    IMPROVEMENT #5: Invoke agent with retry logic.
    Attempts 3 times with increasing simplification levels.
    Returns parsed result or INCOMPLETE status if all attempts fail.
    """
    max_retries = 3
    
    for attempt in range(max_retries):
        simplification_level = attempt  # 0, 1, 2
        
        if attempt > 0:
            logger.warning(
                "Retrying skill=%s with simplification_level=%d (attempt %d/%d)",
                skill_name,
                simplification_level,
                attempt + 1,
                max_retries,
            )
            # Simplify skill definition for retry
            simplified_skill = _simplify_skill_definition(skill_bundle, simplification_level)
            # Rebuild prompt values with simplified skill
            prompt_values["skill_definition"] = json.dumps(simplified_skill, indent=2)
            # Rebuild prompt with simplified skill
            prompt = build_review_prompt(
                skillset=skillset or "default",
                skill_definition=simplified_skill
            )
            # Re-render messages
            messages = prompt.invoke(prompt_values)
        
        try:
            logger.debug("Invoking agent for skill=%s attempt=%d", skill_name, attempt + 1)
            agent_raw_output = _invoke_agent(
                agent_executor=agent_executor,
                prompt_values=prompt_values,
                messages=messages,
                max_agent_iterations=max_agent_iterations,
            )
            logger.debug("Agent invocation completed for skill=%s attempt=%d", skill_name, attempt + 1)
            
            # Try to parse result
            result = parse_agent_result(agent_raw_output, response_format)
            
            # Validate response structure
            is_valid, validation_issues = _validate_response_structure(result, response_format)
            if is_valid:
                logger.info("Agent succeeded for skill=%s on attempt=%d", skill_name, attempt + 1)
                return result
            else:
                logger.warning(
                    "Response validation failed for skill=%s attempt=%d: %s",
                    skill_name,
                    attempt + 1,
                    "; ".join(validation_issues)
                )
                # If last attempt, return what we have (with INCOMPLETE markers)
                if attempt == max_retries - 1:
                    for check_id in response_format.keys():
                        check_id_str = str(check_id)
                        if check_id_str not in result or not isinstance(result.get(check_id_str), dict):
                            result[check_id_str] = {
                                "Status": "INCOMPLETE",
                                "Note / Feedback": "Response validation failed"
                            }
                    return result
                # Otherwise continue to next retry
                continue
        except Exception as e:
            logger.warning(
                "Agent invocation failed for skill=%s attempt=%d error=%s",
                skill_name,
                attempt + 1,
                str(e),
                exc_info=True,
            )
            # If last attempt, return INCOMPLETE for all checks
            if attempt == max_retries - 1:
                result = {}
                for check_id in response_format.keys():
                    check_id_str = str(check_id)
                    result[check_id_str] = {
                        "Status": "INCOMPLETE",
                        "Note / Feedback": f"Failed after {max_retries} attempts: {str(e)[:100]}"
                    }
                return result
            # Otherwise continue to next retry
            continue
    
    # Should not reach here, but fallback
    result = {}
    for check_id in response_format.keys():
        check_id_str = str(check_id)
        result[check_id_str] = {
            "Status": "INCOMPLETE",
            "Note / Feedback": "All retry attempts exhausted"
        }
    return result



def parse_agent_result(agent_result: Any, response_format: Dict[str, Any]) -> Dict[str, Any]:
    payload = {}
    
    if isinstance(agent_result, dict) and "structured_response" in agent_result:
        structured_response = agent_result["structured_response"]
        if hasattr(structured_response, "model_dump"):
            payload = structured_response.model_dump()
        elif isinstance(structured_response, dict):
            payload = structured_response
    elif isinstance(agent_result, dict) and "violations" in agent_result:
        payload = agent_result
    elif isinstance(agent_result, dict) and "output" in agent_result:
        output = agent_result["output"]
        if isinstance(output, dict):
            payload = output
        elif isinstance(output, str):
            payload = _extract_json_object(output)
    elif isinstance(agent_result, str):
        payload = _extract_json_object(agent_result)
    elif isinstance(agent_result, dict):
        payload = agent_result
    
    # Handle raw list format returned by LLM
    if isinstance(payload, dict) and "_raw_list" in payload:
        raw_list = payload["_raw_list"]
        payload = {}
        if isinstance(raw_list, list) and len(raw_list) > 0:
            first = raw_list[0] if isinstance(raw_list[0], dict) else {}

            if "rule" in first or "status" in first:
                # Format 2: [{"rule": "A1", "status": "FAILED", "feedback": "..."}]
                for item in raw_list:
                    if not isinstance(item, dict):
                        continue
                    check_id = item.get("rule") or item.get("check") or item.get("id")
                    if not check_id:
                        continue
                    status_raw = str(item.get("status", "FAILED")).upper()
                    status = "PASSED" if status_raw == "PASSED" else "FAILED"
                    note = item.get("feedback") or item.get("note") or item.get("Note / Feedback") or ""
                    payload[str(check_id)] = {"Status": status, "Note / Feedback": str(note)}
            else:
                # Format 1: [{"B1": {"Status": "PASSED", ...}}, {"B2": {...}}]
                for item in raw_list:
                    if isinstance(item, dict):
                        for k, v in item.items():
                            if isinstance(v, dict):
                                payload[k] = v
    
    # If payload is empty, create default response with all checks failed
    if not payload:
        payload = {}
        for check_id in response_format.keys():
            payload[str(check_id)] = {"Status": "FAILED", "Note / Feedback": "No response from LLM"}
    
    return _validate_dynamic_response_payload(payload, response_format)


def execute_skill(
    *,
    skill_name: str,
    criterion: str,
    project_root,
    registry_path,
    llm,
    prompt,
    max_agent_iterations: int,
    verbose: bool,
    input_file_name: str,
    raw_source_text: str,
    skillset: Optional[str] = None,
    agent_input_trace_path: Optional[Path] = None,
    prompt_trace_templates: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    logger.info(
        "Skill execution requested skill=%s criterion=%s file=%s",
        skill_name,
        criterion,
        input_file_name,
    )

    try:
        # IMPROVEMENT #6: Validate input file size before processing
        is_valid_size, size_message = _validate_input_file_size(
            raw_source_text=raw_source_text,
            skillset=skillset,
            skill_name=skill_name,
        )
        logger.info("File size validation: %s", size_message)
        
        if not is_valid_size:
            logger.warning("Input file too large, marking all checks as SKIPPED")
            response_format_temp = {}
            try:
                temp_bundle = load_skill_bundle(
                    project_root=project_root,
                    registry_path=registry_path,
                    skill_name=skill_name,
                    skillset=skillset,
                )
                response_format_temp = temp_bundle.get("response_format", {})
            except Exception as e:
                logger.debug("Could not load skill for format info: %s", str(e))
            
            # Return SKIPPED for all checks
            result = {}
            for check_id in response_format_temp.keys():
                check_id_str = str(check_id)
                result[check_id_str] = {
                    "Status": "SKIPPED",
                    "Note / Feedback": f"File too large for evaluation: {size_message}"
                }
            return {
                "allowed": True,
                "status": "success",
                "skill_name": skill_name,
                "criterion": criterion,
                "reason": "File too large - evaluation skipped",
                "result": result,
                "policy_decision": None,
                "error": None,
            }
        
        logger.info("Loading skill bundle skill=%s skillset=%s", skill_name, skillset or "")
        skill_bundle = load_skill_bundle(
            project_root=project_root,
            registry_path=registry_path,
            skill_name=skill_name,
            skillset=skillset,
        )
        
        # IMPROVEMENT #1: Build skill-specific prompts instead of using generic one
        logger.debug("Building skill-specific prompt for skillset=%s skill=%s", skillset or "default", skill_name)
        skill_specific_prompt = build_review_prompt(
            skillset=skillset or "default",
            skill_definition=skill_bundle
        )
        prompt = skill_specific_prompt  # Override the generic prompt with skill-specific one
        
        # Also build skill-specific prompt trace templates if needed
        if prompt_trace_templates is None:
            prompt_trace_templates = build_review_prompt_trace_templates(
                skillset=skillset or "default",
                skill_definition=skill_bundle
            )
        
        numbered_source_text = build_numbered_source_text(raw_source_text)
        logger.info("Calling agent for skill=%s file=%s", skill_name, input_file_name)
        response_format = skill_bundle.get("response_format")
        if not isinstance(response_format, dict):
            raise ValueError(f"Skill '{skill_name}' does not define output_style.format")
        
        try:
            logger.debug("Building agent response format schema for skill=%s", skill_name)
            agent_response_format = build_agent_response_format_schema(
                skill_name=skill_name,
                response_format=response_format,
            )
            logger.debug("Agent response format schema built for skill=%s", skill_name)
        except Exception as schema_exc:
            logger.error(
                "Failed to build schema for skill=%s error=%s",
                skill_name,
                str(schema_exc),
                exc_info=True,
            )
            raise
        
        prompt_values = {
            "skill_definition": json.dumps(skill_bundle, indent=2),
            "input_name": input_file_name,
            "numbered_source_text": numbered_source_text,
        }
        rendered_prompt_values = prompt_values
        
        try:
            logger.debug("Invoking prompt template for skill=%s", skill_name)
            messages = prompt.invoke(rendered_prompt_values)
            logger.debug("Prompt template invoked for skill=%s", skill_name)
        except Exception as prompt_exc:
            logger.error(
                "Failed to invoke prompt for skill=%s error=%s",
                skill_name,
                str(prompt_exc),
                exc_info=True,
            )
            raise
        
        if agent_input_trace_path is not None and prompt_trace_templates is not None:
            prompt_trace = build_prompt_trace(
                template_messages=prompt_trace_templates,
                prompt_values=prompt_values,
                rendered_messages=_rendered_message_dicts(messages),
            )
            update_agent_input_trace_skill(
                trace_path=agent_input_trace_path,
                skill_name=skill_name,
                status="running",
                prompt_trace=prompt_trace,
            )
        
        try:
            logger.debug("Creating agent executor for skill=%s", skill_name)
            agent_executor = _create_agent_executor(
                llm=llm,
                prompt=prompt,
                response_format=agent_response_format,
                max_agent_iterations=max_agent_iterations,
                verbose=verbose,
            )
            logger.debug("Agent executor created for skill=%s", skill_name)
        except Exception as executor_exc:
            logger.error(
                "Failed to create agent executor for skill=%s error=%s",
                skill_name,
                str(executor_exc),
                exc_info=True,
            )
            raise
        
        try:
            logger.debug("Invoking agent with retry logic for skill=%s", skill_name)
            # IMPROVEMENT #5: Use retry logic with progressive simplification
            result = _invoke_agent_with_retry(
                agent_executor=agent_executor,
                llm=llm,
                prompt=prompt,
                skill_bundle=skill_bundle,
                skillset=skillset,
                prompt_values=prompt_values,
                messages=messages,
                response_format=response_format,
                max_agent_iterations=max_agent_iterations,
                skill_name=skill_name,
            )
            logger.debug("Agent invocation with retry completed for skill=%s", skill_name)
        except Exception as invoke_exc:
            logger.error(
                "Failed to invoke agent with retry for skill=%s error=%s",
                skill_name,
                str(invoke_exc),
                exc_info=True,
            )
            # Return INCOMPLETE for all checks on fatal error
            result = {}
            for check_id in response_format.keys():
                check_id_str = str(check_id)
                result[check_id_str] = {
                    "Status": "INCOMPLETE",
                    "Note / Feedback": f"Fatal error during invocation: {str(invoke_exc)[:100]}"
                }
        
        if result:
            # Result already validated by _invoke_agent_with_retry
            logger.debug("Using result from _invoke_agent_with_retry for skill=%s", skill_name)
        if agent_input_trace_path is not None:
            update_agent_input_trace_skill(
                trace_path=agent_input_trace_path,
                skill_name=skill_name,
                status="success",
            )
        logger.info("Agent completed skill=%s file=%s status=success", skill_name, input_file_name)
        return {
            "allowed": True,
            "status": "success",
            "skill_name": skill_name,
            "criterion": criterion,
            "reason": "Skill executed successfully",
            "result": result,
            "policy_decision": None,
            "error": None,
        }
    except SkillLoadError as exc:
        if agent_input_trace_path is not None:
            update_agent_input_trace_skill(
                trace_path=agent_input_trace_path,
                skill_name=skill_name,
                status="error",
                error=str(exc),
            )
        logger.error(
            "Skill bundle load failed skill=%s criterion=%s file=%s error=%s",
            skill_name,
            criterion,
            input_file_name,
            str(exc),
        )
        return {
            "allowed": True,
            "status": "error",
            "skill_name": skill_name,
            "criterion": criterion,
            "reason": "Skill loading failed",
            "result": None,
            "policy_decision": None,
            "error": str(exc),
        }
    except Exception as exc:  # pragma: no cover - defensive runtime path
        if agent_input_trace_path is not None:
            update_agent_input_trace_skill(
                trace_path=agent_input_trace_path,
                skill_name=skill_name,
                status="error",
                error=str(exc),
            )
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        logger.error(
            "Agent invocation failed skill=%s criterion=%s file=%s error=%s",
            skill_name,
            criterion,
            input_file_name,
            error_msg,
            exc_info=True,  # ← Include full traceback
        )
        return {
            "allowed": True,
            "status": "error",
            "skill_name": skill_name,
            "criterion": criterion,
            "reason": "Skill execution failed",
            "result": None,
            "policy_decision": None,
            "error": error_msg,
        }
