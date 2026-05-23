from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from policy.errors import PolicyError
from policy.route_plan import resolve_route_execution_plan
from processor.results import build_invalid_json_result, build_policy_error_result, build_unclassified_result
from processor.route.route_a_workflow import run_route_a_workflow
from processor.route.route_b_workflow import run_route_b_workflow
from tools.file_tools import mark_file_as_proceeding, read_file_text
from utils.file_routing import ROUTE_A, ROUTE_B, detect_route, explain_route_match
from utils.logger import get_logger

logger = get_logger()


def relative_path(project_root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(project_root.resolve())).replace("\\", "/")


def process_input_file(
    *,
    input_file: Path,
    project_root: Path,
    proceed_root: Path,
    policy_root: Path,
    registry: Dict[str, Any],
    execution_context: Dict[str, Any],
) -> Dict[str, Any]:
    logger.info("Starting file processing file=%s", input_file.name)
    raw_source_text = read_file_text(project_root, relative_path(project_root, input_file))
    mark_file_as_proceeding(proceed_root, input_file)

    route = detect_route(input_file.name)
    route_match = explain_route_match(input_file.name)
    metadata = {"route_match": route_match}
    logger.info(
        "Route detection file=%s route=%s match=%s",
        input_file.name,
        route or "unclassified",
        route_match["pattern"] if isinstance(route_match, dict) and "pattern" in route_match else "none",
    )

    if route is None:
        return build_unclassified_result(input_file.name, route_match)

    try:
        json_data = json.loads(raw_source_text)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON file=%s error=%s", input_file.name, str(exc))
        return build_invalid_json_result(input_file.name, route, route_match, str(exc))

    if route == ROUTE_A:
        try:
            execution_plan = resolve_route_execution_plan(policy_root, route, registry)
        except PolicyError as exc:
            logger.error("Route execution plan failed file=%s route=%s error=%s", input_file.name, route, str(exc))
            return build_policy_error_result(input_file.name, route, route_match, str(exc))

        logger.info("Dispatching file=%s workflow=%s", input_file.name, execution_plan.workflow)
        return run_route_a_workflow(
            file_name=input_file.name,
            json_data=json_data,
            raw_source_text=raw_source_text,
            metadata=metadata,
            execution_context=execution_context,
            execution_plan=execution_plan,
        )

    if route == ROUTE_B:
        try:
            execution_plan = resolve_route_execution_plan(policy_root, route, registry)
        except PolicyError as exc:
            logger.error("Route execution plan failed file=%s route=%s error=%s", input_file.name, route, str(exc))
            return build_policy_error_result(input_file.name, route, route_match, str(exc))

        logger.info("Dispatching file=%s workflow=%s", input_file.name, execution_plan.workflow)
        return run_route_b_workflow(
            file_name=input_file.name,
            json_data=json_data,
            raw_source_text=raw_source_text,
            metadata=metadata,
            execution_context=execution_context,
            execution_plan=execution_plan,
        )

    return build_unclassified_result(input_file.name, route_match)
