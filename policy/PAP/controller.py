from __future__ import annotations

from pathlib import Path
from typing import Any

from policy.utils import ensure_policy_storage_layout, read_json, write_json


def ensure_admin_policy_section(policy_path: Path) -> None:
    """Ensure split PAP storage layout exists."""
    ensure_policy_storage_layout(policy_path)


def refresh_pap_inventory(
    policy_path: Path,
    registry: dict[str, Any],
    available_tools: list[str],
) -> dict[str, Any]:
    """Refresh registered resources in base policy from discovered skills and tools."""
    paths = ensure_policy_storage_layout(policy_path)
    base_doc = read_json(paths["base_path"])

    grouped: dict[str, list[dict[str, str]]] = {}
    flat_skill_names: list[str] = []

    for item in registry.get("skills", []):
        skill_file = str(item.get("skill_file", ""))
        skillset = Path(skill_file).parent.name
        skill_item = {
            "name": str(item.get("name", "")),
            "description": str(item.get("description", "")),
            "skill_file": skill_file,
            "skillset": skillset,
        }
        grouped.setdefault(skillset, []).append(skill_item)
        if skill_item["name"]:
            flat_skill_names.append(skill_item["name"])

    inventory = {
        "skillsets": [
            {"name": key, "skills": value}
            for key, value in sorted(grouped.items(), key=lambda pair: pair[0])
        ],
        "skills": sorted(set(flat_skill_names)),
        "tools": sorted(list(set(available_tools))),
    }

    base_doc.setdefault("registered_resources", {})
    resources = base_doc["registered_resources"]
    resources["skillsets"] = [item["name"] for item in inventory["skillsets"]]
    resources["skills"] = inventory["skills"]
    resources["tools"] = inventory["tools"]
    resources.setdefault("actions", ["skillset.select", "skill.use", "tool.invoke"])

    write_json(paths["base_path"], base_doc)
    return inventory
