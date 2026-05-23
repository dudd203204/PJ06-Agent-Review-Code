from __future__ import annotations

from typing import Any, Dict, Optional


def build_unclassified_result(file_name: str, route_match: Optional[Dict[str, str]]) -> Dict[str, Any]:
    return {
        "file_name": file_name,
        "route": "unclassified",
        "route_match": route_match,
        "workflow": "none",
        "overall_status": "unsupported",
        "checks": [],
        "policy_events": [],
        "errors": ["Input filename did not match any configured route"],
    }


def build_invalid_json_result(file_name: str, route: str, route_match: Optional[Dict[str, str]], error_text: str) -> Dict[str, Any]:
    return {
        "file_name": file_name,
        "route": route,
        "route_match": route_match,
        "workflow": "none",
        "overall_status": "failed",
        "checks": [],
        "policy_events": [],
        "errors": [f"Invalid JSON: {error_text}"],
    }


def build_policy_error_result(file_name: str, route: str, route_match: Optional[Dict[str, str]], error_text: str) -> Dict[str, Any]:
    return {
        "file_name": file_name,
        "route": route,
        "route_match": route_match,
        "workflow": "policy_resolution",
        "overall_status": "failed",
        "checks": [],
        "policy_events": [],
        "errors": [error_text],
    }
