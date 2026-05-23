from __future__ import annotations

import re

ROUTE_A = "route_a"
ROUTE_B = "route_b"

ROUTE_A_PATTERNS = [
    re.compile(r"^input_formio.*\.json$", re.IGNORECASE),
    re.compile(r".*formio.*\.json$", re.IGNORECASE),
]

ROUTE_B_PATTERNS = [
    re.compile(r"^backoffice.*\.json$", re.IGNORECASE),
    re.compile(r".*backoffice.*\.json$", re.IGNORECASE),
]


def is_route_a(file_name: str) -> bool:
    return any(pattern.search(file_name) for pattern in ROUTE_A_PATTERNS)


def is_route_b(file_name: str) -> bool:
    return any(pattern.search(file_name) for pattern in ROUTE_B_PATTERNS)


def detect_route(file_name: str) -> str | None:
    if is_route_a(file_name):
        return ROUTE_A
    if is_route_b(file_name):
        return ROUTE_B
    return None


def explain_route_match(file_name: str) -> dict[str, str] | None:
    for pattern in ROUTE_A_PATTERNS:
        if pattern.search(file_name):
            return {"route": ROUTE_A, "pattern": pattern.pattern}

    for pattern in ROUTE_B_PATTERNS:
        if pattern.search(file_name):
            return {"route": ROUTE_B, "pattern": pattern.pattern}

    return None
