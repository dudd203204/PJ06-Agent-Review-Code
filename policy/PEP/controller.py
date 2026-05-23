from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from policy.errors import PolicyError
from policy.PEP.enforcement import enforce_skill_usage, enforce_skillset_selection, filter_allowed_tools_for_principal
from policy.shared.models import PolicyViolationError
from policy.utils import ensure_policy_storage_layout, get_active_profile


def ensure_enforcement_policy_section(policy_path: Path) -> None:
    """Ensure split policy storage exists for PEP checks."""
    ensure_policy_storage_layout(policy_path)


def enforce_access_policy(
    selection: Dict[str, str],
    policy_path: Path,
    registry: Dict[str, Any],
) -> Dict[str, Any]:
    """Enforce principal-aware skill selection policy from runtime_policy.json."""
    ensure_policy_storage_layout(policy_path)

    try:
        mode = selection.get("mode", "")
        if mode == "skillset":
            selected_skillset = selection.get("skillset", "")
            enforce_skillset_selection(selected_skillset)
        elif mode == "skill_file":
            selected_skill_file = selection.get("skill_file", "").replace("\\", "/")
            skill_name = Path(selected_skill_file).stem
            for item in registry.get("skills", []):
                if str(item.get("skill_file", "")) == selected_skill_file:
                    skill_name = str(item.get("name", skill_name))
                    break
            enforce_skill_usage(skill_name)
        else:
            raise PolicyError(f"Unsupported selection mode: {mode}")
    except PolicyViolationError as exc:
        raise PolicyError(exc.decision.reason) from exc

    return {}


def filter_allowed_tools(tool_names: List[str], pep_policy: Dict[str, Any]) -> List[str]:
    """Return tool names permitted for the principal in pep_policy context."""
    _ = pep_policy
    return filter_allowed_tools_for_principal(tool_names)


def filter_skillset_by_runtime_policy(skill_names: List[str], policy_path: Path) -> List[str]:
    """Apply profile excluded_skills as final deny override for skillset execution."""
    _, profile = get_active_profile(policy_path)
    excluded = {str(item) for item in profile.get("excluded_skills", [])}
    return [name for name in skill_names if name not in excluded]
