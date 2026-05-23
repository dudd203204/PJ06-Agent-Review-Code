from __future__ import annotations

from typing import Any

from policy.route_plan import RouteExecutionPlan
from processor.review_workflow import run_review_workflow


def run_route_b_workflow(
    *,
    file_name: str,
    json_data: dict[str, Any],
    raw_source_text: str,
    metadata: dict[str, Any],
    execution_context: dict[str, Any],
    execution_plan: RouteExecutionPlan,
) -> dict[str, Any]:
    _ = json_data
    return run_review_workflow(
        file_name=file_name,
        raw_source_text=raw_source_text,
        metadata=metadata,
        execution_context=execution_context,
        execution_plan=execution_plan,
    )
