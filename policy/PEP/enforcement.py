from __future__ import annotations

import json
from pathlib import Path

from policy.shared.models import PolicyDecision, PolicyViolationError
from policy.utils import get_active_profile
from utils.logger import get_logger

logger = get_logger()


def _get_engine():
    from policy import get_policy_engine

    return get_policy_engine()


def _current_policy_id() -> str:
    engine = _get_engine()
    storage_root = getattr(engine.registry, "storage_root", None)
    if storage_root is None:
        return "default"
    policy_id, _ = get_active_profile(Path(storage_root))
    return policy_id


def _persist_if_denied(decision: PolicyDecision) -> None:
    if decision.allowed:
        return

    engine = _get_engine()
    storage_root = getattr(engine.registry, "storage_root", None)
    if storage_root is None:
        return

    deny_path = Path(storage_root) / "policy_denials.jsonl"
    deny_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "decision_id": decision.decision_id,
        "policy_id": decision.policy_id,
        "action": decision.action,
        "target": decision.target,
        "reason": decision.reason,
        "timestamp_utc": decision.timestamp_utc,
    }
    with deny_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=True) + "\n")
    logger.warning(
        "Policy denied action=%s target=%s policy_id=%s reason=%s decision_id=%s",
        decision.action,
        decision.target,
        decision.policy_id,
        decision.reason,
        decision.decision_id,
    )


def enforce_skillset_selection(skillset: str) -> None:
    engine = _get_engine()
    policy_id = _current_policy_id()
    logger.info("Policy check requested action=skillset.select target=%s policy_id=%s", skillset, policy_id)
    decision = engine.can_select_skillset(policy_id, skillset)
    _persist_if_denied(decision)
    if not decision.allowed:
        raise PolicyViolationError(decision=decision)
    logger.info("Policy allowed action=skillset.select target=%s policy_id=%s", skillset, policy_id)


def enforce_skill_usage(skill_name: str) -> None:
    engine = _get_engine()
    policy_id = _current_policy_id()
    logger.info("Policy check requested action=skill.use target=%s policy_id=%s", skill_name, policy_id)
    decision = engine.can_use_skill(policy_id, skill_name)
    _persist_if_denied(decision)
    if not decision.allowed:
        raise PolicyViolationError(decision=decision)
    logger.info("Policy allowed action=skill.use target=%s policy_id=%s", skill_name, policy_id)


def enforce_tool(tool_name: str) -> None:
    engine = _get_engine()
    policy_id = _current_policy_id()
    logger.info("Policy check requested action=tool.invoke target=%s policy_id=%s", tool_name, policy_id)
    decision = engine.can_use_tool(policy_id, tool_name)
    _persist_if_denied(decision)
    if not decision.allowed:
        raise PolicyViolationError(decision=decision)
    logger.info("Policy allowed action=tool.invoke target=%s policy_id=%s", tool_name, policy_id)


def filter_allowed_tools_for_principal(tool_names: list[str]) -> list[str]:
    engine = _get_engine()
    allowed = set(engine.get_principal_allowed_tools(_current_policy_id()))
    return sorted([name for name in set(tool_names) if name in allowed])
