from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from policy.route_plan import RouteExecutionPlan


_PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _trace_file_name(input_name: str) -> str:
    input_path = Path(input_name)
    stem = input_path.stem if input_path.suffix.lower() == ".json" else input_path.name
    return f"{stem}.agent-input.json"


def get_agent_input_trace_path(output_root: Path, input_name: str) -> Path:
    return output_root / "agent_inputs" / _trace_file_name(input_name)


def _write_trace(trace_path: Path, payload: dict[str, Any]) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_trace(trace_path: Path) -> dict[str, Any]:
    if not trace_path.exists():
        return {}
    return json.loads(trace_path.read_text(encoding="utf-8"))


def initialize_agent_input_trace(
    *,
    output_root: Path,
    input_name: str,
    execution_plan: RouteExecutionPlan,
) -> Path:
    trace_path = get_agent_input_trace_path(output_root, input_name)
    payload = {
        "file_name": input_name,
        "route": execution_plan.route,
        "workflow": execution_plan.workflow,
        "profile": execution_plan.profile,
        "skillset": execution_plan.skillset,
        "status": "running",
        "current_skill": None,
        "started_at": _now(),
        "updated_at": _now(),
        "completed_at": None,
        "skills": [
            {
                "skill_name": skill.skill_name,
                "criterion": skill.criterion,
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "prompt": None,
                "error": None,
            }
            for skill in execution_plan.skills
        ],
    }
    _write_trace(trace_path, payload)
    return trace_path


def build_prompt_trace(
    *,
    template_messages: list[dict[str, str]],
    prompt_values: dict[str, str],
    rendered_messages: list[dict[str, str]],
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    for index, template_message in enumerate(template_messages):
        template = template_message["template"]
        template_values = {
            match.group(1): prompt_values.get(match.group(1), "")
            for match in _PLACEHOLDER_PATTERN.finditer(template)
        }

        rendered = rendered_messages[index] if index < len(rendered_messages) else {}
        messages.append(
            {
                "role": template_message["role"],
                "prompt_template": template,
                "template_values": template_values,
                "prompt_text": rendered.get("content", ""),
            }
        )

    return {"messages": messages}


def update_agent_input_trace_skill(
    *,
    trace_path: Path,
    skill_name: str,
    status: str,
    prompt_trace: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    payload = _read_trace(trace_path)
    if not payload:
        return

    now = _now()
    payload["status"] = "running"
    payload["current_skill"] = skill_name if status == "running" else None
    payload["updated_at"] = now

    for item in payload.get("skills", []):
        if item.get("skill_name") != skill_name:
            continue
        item["status"] = status
        item["error"] = error
        if status == "running" and not item.get("started_at"):
            item["started_at"] = now
        if status in {"success", "error"}:
            item["completed_at"] = now
        if prompt_trace is not None:
            item["prompt"] = prompt_trace
        break

    _write_trace(trace_path, payload)


def complete_agent_input_trace(*, trace_path: Path, status: str = "completed") -> None:
    payload = _read_trace(trace_path)
    if not payload:
        return

    now = _now()
    payload["status"] = status
    payload["current_skill"] = None
    payload["updated_at"] = now
    payload["completed_at"] = now
    _write_trace(trace_path, payload)
