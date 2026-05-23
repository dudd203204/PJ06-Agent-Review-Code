from __future__ import annotations

from pathlib import Path

from policy.utils import ensure_policy_storage_layout, read_runtime_policy


def ensure_decision_policy_section(policy_path: Path) -> None:
    """Ensure split policy storage exists for PDP decisions."""
    ensure_policy_storage_layout(policy_path)


def _normalize_skillset(value: str) -> str:
    normalized = value.replace("\\", "/").rstrip("/")
    return Path(normalized).name if normalized else ""


def resolve_effective_selection(
    policy_path: Path,
) -> dict[str, str]:
    """Resolve selection only from runtime_policy.json."""
    ensure_policy_storage_layout(policy_path)
    runtime_doc = read_runtime_policy(policy_path)
    selection = runtime_doc.get("selection", {})
    selection_mode = str(selection.get("mode", "")).strip()

    if selection_mode == "skill_file":
        return {
            "mode": "skill_file",
            "skill_file": str(selection.get("skill_file", "")).strip(),
            "skillset": "",
        }

    return {
        "mode": "skillset",
        "skillset": _normalize_skillset(str(selection.get("skillset", "")).strip()),
        "skill_file": "",
    }
