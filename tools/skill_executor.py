from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.agent_input_trace import build_prompt_trace, update_agent_input_trace_skill
from tools.review_source import build_numbered_source_text
from tools.skill_loader import SkillLoadError, load_skill_bundle
from utils.logger import get_logger

logger = get_logger()


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
            # LLM omitted this check — no issues found means PASSED
            payload[check_name] = {"Status": "PASSED", "Note / Feedback": ""}
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
            # It's only required when Status is FAILED
            if field_key == "Note / Feedback" and check_status == "PASSED":
                continue
            
            if field_key not in payload[check_name]:
                # Fill in missing field with default value
                if field_key == "Status":
                    payload[check_name][field_key] = "FAILED"
                else:
                    payload[check_name][field_key] = ""
            if not isinstance(payload[check_name].get(field_key, ""), str):
                payload[check_name][field_key] = str(payload[check_name].get(field_key, ""))
    return payload


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
        logger.info("Loading skill bundle skill=%s skillset=%s", skill_name, skillset or "")
        skill_bundle = load_skill_bundle(
            project_root=project_root,
            registry_path=registry_path,
            skill_name=skill_name,
            skillset=skillset,
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
            logger.debug("Invoking agent for skill=%s", skill_name)
            agent_raw_output = _invoke_agent(
                agent_executor=agent_executor,
                prompt_values=prompt_values,
                messages=messages,
                max_agent_iterations=max_agent_iterations,
            )
            logger.debug("Agent invocation completed for skill=%s", skill_name)
        except Exception as invoke_exc:
            logger.error(
                "Failed to invoke agent for skill=%s error=%s",
                skill_name,
                str(invoke_exc),
                exc_info=True,
            )
            raise
        
        try:
            # Serialize agent output for logging (full output, no truncation)
            if isinstance(agent_raw_output, dict) and "output" in agent_raw_output:
                output_str = agent_raw_output.get("output", "")
            else:
                output_str = str(agent_raw_output)
        except Exception:
            output_str = str(agent_raw_output)
        logger.info(
            "Agent raw output for skill=%s: %s",
            skill_name,
            output_str,
        )
        
        try:
            logger.debug("Parsing agent result for skill=%s", skill_name)
            result = parse_agent_result(agent_raw_output, response_format)
            logger.debug("Agent result parsed successfully for skill=%s", skill_name)
        except Exception as parse_exc:
            logger.error(
                "Failed to parse agent result for skill=%s error=%s",
                skill_name,
                str(parse_exc),
                exc_info=True,
            )
            raise
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
