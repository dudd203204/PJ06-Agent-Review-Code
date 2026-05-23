from __future__ import annotations

from pathlib import Path

from policy.PAP.controller import ensure_admin_policy_section, refresh_pap_inventory
from policy.PAP.registry import JsonPolicyRegistry
from policy.PDP.controller import ensure_decision_policy_section, resolve_effective_selection
from policy.PDP.engine import PolicyEngine
from policy.PEP.controller import ensure_enforcement_policy_section, enforce_access_policy, filter_allowed_tools

_ENGINE: PolicyEngine | None = None


def get_policy_engine(policy_root: Path | None = None) -> PolicyEngine:
    """Return process-wide policy engine and refresh when policy files change."""
    global _ENGINE
    if _ENGINE is None:
        base_dir = policy_root if policy_root is not None else Path(__file__).parent
        registry = JsonPolicyRegistry(base_dir)
        registry.load()
        _ENGINE = PolicyEngine(registry)
    else:
        ensure_fresh = getattr(_ENGINE.registry, "ensure_fresh", None)
        if callable(ensure_fresh):
            ensure_fresh()
    return _ENGINE


def reload_policy_engine(policy_root: Path | None = None) -> PolicyEngine:
    """Force synchronous reload of policy engine from storage."""
    global _ENGINE
    base_dir = policy_root if policy_root is not None else Path(__file__).parent
    registry = JsonPolicyRegistry(base_dir)
    registry.load()
    _ENGINE = PolicyEngine(registry)
    return _ENGINE

__all__ = [
    "get_policy_engine",
    "reload_policy_engine",
    "ensure_admin_policy_section",
    "refresh_pap_inventory",
    "ensure_decision_policy_section",
    "resolve_effective_selection",
    "ensure_enforcement_policy_section",
    "enforce_access_policy",
    "filter_allowed_tools",
]
