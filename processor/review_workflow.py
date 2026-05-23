from __future__ import annotations

from typing import Any

from policy.route_plan import RouteExecutionPlan
from tools.agent_input_trace import complete_agent_input_trace, initialize_agent_input_trace
from tools.skill_executor import execute_skill
from utils.logger import get_logger

logger = get_logger()


def _build_locations(result_payload: dict[str, Any]) -> list[int]:
    violations = result_payload.get("violations", [])
    locations: list[int] = []
    for item in violations:
        if not isinstance(item, dict):
            continue
        line_value = item.get("line")
        if isinstance(line_value, int):
            locations.append(line_value)
    return sorted(set(locations))


def _build_check_status(result_payload: dict[str, Any]) -> tuple[str, str]:
    if "violations" in result_payload and isinstance(result_payload.get("violations"), list):
        violations = result_payload["violations"]
        return (
            "failed" if violations else "passed",
            "Violations found" if violations else "No violations found",
        )

    failed_checks: list[str] = []
    for check_id, check_payload in result_payload.items():
        if not isinstance(check_payload, dict):
            continue
        status = str(check_payload.get("Status", "")).strip().upper()
        if status == "FAILED":
            failed_checks.append(str(check_id))

    if failed_checks:
        return "failed", f"Failed checks: {', '.join(failed_checks)}"
    return "passed", "No failed checks found"


def run_review_workflow(
    *,
    file_name: str,
    raw_source_text: str,
    metadata: dict[str, Any],
    execution_context: dict[str, Any],
    execution_plan: RouteExecutionPlan,
) -> dict[str, Any]:
    logger.info("Review workflow started file=%s route=%s skills=%s", file_name, execution_plan.route, len(execution_plan.skills))
    checks: list[dict[str, Any]] = []
    policy_events: list[dict[str, Any]] = []
    errors: list[str] = []
    trace_path = None
    trace_output_root = execution_context.get("agent_input_trace_output_root")
    if trace_output_root is not None:
        trace_path = initialize_agent_input_trace(
            output_root=trace_output_root,
            input_name=file_name,
            execution_plan=execution_plan,
        )

    for skill in execution_plan.skills:
        logger.info(
            "Review workflow invoking skill step skill=%s criterion=%s file=%s",
            skill.skill_name,
            skill.criterion,
            file_name,
        )
        skill_result = execute_skill(
            skill_name=skill.skill_name,
            criterion=skill.criterion,
            project_root=execution_context["project_root"],
            registry_path=execution_context["registry_path"],
            llm=execution_context["llm"],
            prompt=execution_context["prompt"],
            max_agent_iterations=execution_context["max_agent_iterations"],
            verbose=execution_context["agent_verbose"],
            input_file_name=file_name,
            raw_source_text=raw_source_text,
            skillset=execution_plan.skillset,
            agent_input_trace_path=trace_path,
            prompt_trace_templates=execution_context.get("prompt_trace_templates"),
        )

        status = str(skill_result.get("status", "error"))
        if status == "denied":
            checks.append(
                {
                    "skill_id": skill.skill_name,
                    "criterion": skill.criterion,
                    "status": "failed",
                    "reason": str(skill_result.get("reason", "Policy denied")),
                    "locations": [],
                    "evidence": None,
                }
            )
            decision = skill_result.get("policy_decision")
            if isinstance(decision, dict):
                policy_events.append(decision)
            continue

        if status == "error":
            reason = str(skill_result.get("reason", "Skill execution failed"))
            error_detail = str(skill_result.get("error", "Unknown error"))
            # Combine reason with error detail for meaningful feedback
            combined_reason = f"{reason}: {error_detail}"
            checks.append(
                {
                    "skill_id": skill.skill_name,
                    "criterion": skill.criterion,
                    "status": "failed",
                    "reason": combined_reason,
                    "locations": [],
                    "evidence": None,
                }
            )
            errors.append(f"{skill.skill_name}: {error_detail}")
            continue

        payload = skill_result.get("result")
        if not isinstance(payload, dict):
            payload = {}
        locations = _build_locations(payload)
        check_status, check_reason = _build_check_status(payload)

        checks.append(
            {
                "skill_id": skill.skill_name,
                "criterion": skill.criterion,
                "status": check_status,
                "reason": check_reason,
                "locations": locations,
                "evidence": payload,
            }
        )

    overall_status = "passed"
    for check in checks:
        if check.get("status") != "passed":
            overall_status = "failed"
            break

    logger.info("Review workflow finished file=%s route=%s overall_status=%s", file_name, execution_plan.route, overall_status)
    if trace_path is not None:
        complete_agent_input_trace(trace_path=trace_path)

    return {
        "file_name": file_name,
        "route": execution_plan.route,
        "route_match": metadata.get("route_match"),
        "workflow": execution_plan.workflow,
        "overall_status": overall_status,
        "checks": checks,
        "policy_events": policy_events,
        "errors": errors,
    }
