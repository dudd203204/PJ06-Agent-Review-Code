from __future__ import annotations

from typing import Optional

def resolve_policy_id(principal_id: Optional[str]) -> str:
    """Normalize runtime principal ID to policy principal ID."""
    candidate = (principal_id or "").strip()
    if not candidate:
        return "unknown"
    return candidate
