from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from policy.errors import PolicyError


DEFAULT_SCHEMA = "policy-schema/v1"


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PolicyError(f"Invalid JSON policy file: {path}") from exc


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def default_base_policy_document() -> dict[str, Any]:
    """Return default base policy document for split storage layout."""
    return {
        "schema": DEFAULT_SCHEMA,
        "metadata": {
            "description": "Principal-based policy for agent-skill reviewer",
            "owner": "agent-skill",
            "tags": ["skills", "policy", "pep", "pdp", "pap"],
        },
        "registered_resources": {
            "skillsets": [],
            "skills": [],
            "tools": [],
            "actions": ["skillset.select", "skill.use", "tool.invoke"],
        },
    }


def default_principals_document() -> dict[str, Any]:
    """Return default principal policy records.

    default: permissive baseline for backward compatibility.
    restricted_python_quality: sample restricted principal.
    """
    return {
        "principals": {
            "default": {
                "layer": "application",
                "allowed_skillsets": ["*"],
                "allowed_skills": ["*"],
                "excluded_skills": [],
                "allowed_tools": ["*"],
            },
            "restricted_python_quality": {
                "layer": "application",
                "allowed_skillsets": ["python_quality"],
                "allowed_skills": ["code_review"],
                "excluded_skills": [],
                "allowed_tools": ["read_project_file", "list_project_files", "list_skills"],
            },
        }
    }


def default_runtime_policy_document() -> dict[str, Any]:
    """Return combined runtime policy document for selection and profile policy."""
    return {
        "active_profile": "default",
        "selection": {
            "mode": "skill_file",
            "skill_file": "skills/python_quality/code_review.json",
            "skillset": "",
        },
        "routes": {
            "route_a": {
                "label": "FormIO",
                "profile": "route_a_formio",
                "skillset": "form_quality",
                "skills": [
                    "component_quality",
                    "form_structure_quality",
                    "field_logic_quality",
                    "run_time_quality",
                ],
            },
            "route_b": {
                "label": "Backoffice",
                "profile": "route_b_backoffice",
                "skillset": "back_office_quality",
                "skills": [
                    "review_back_office",
                ],
            },
        },
        "profiles": {
            "default": {
                "layer": "application",
                "allowed_skillsets": ["*"],
                "allowed_skills": ["*"],
                "excluded_skills": [],
                "allowed_tools": ["*"],
            },
            "restricted_python_quality": {
                "layer": "application",
                "allowed_skillsets": ["python_quality"],
                "allowed_skills": ["code_review"],
                "excluded_skills": ["bug_fix"],
                "allowed_tools": ["read_project_file", "list_project_files", "list_skills"],
            },
            "route_a_formio": {
                "layer": "application",
                "allowed_skillsets": ["form_quality"],
                "allowed_skills": [
                    "component_quality",
                    "form_structure_quality",
                    "field_logic_quality",
                    "run_time_quality",
                ],
                "excluded_skills": [],
                "allowed_tools": ["read_project_file", "list_project_files", "list_skills", "load_skill", "get_hyperparameters"],
            },
            "route_b_backoffice": {
                "layer": "application",
                "allowed_skillsets": ["back_office_quality"],
                "allowed_skills": ["review_back_office"],
                "excluded_skills": [],
                "allowed_tools": ["read_project_file", "list_project_files", "list_skills", "load_skill", "get_hyperparameters"],
            },
        },
    }


def resolve_storage_root(policy_path_or_dir: Path) -> Path:
    """Resolve policy storage directory from either a file or policy root directory."""
    path = Path(policy_path_or_dir)
    if path.is_file() or path.suffix.lower() == ".json":
        return path.parent
    if path.name == "storage":
        return path
    return path / "storage"


def _migrate_from_legacy_if_needed(storage_root: Path) -> None:
    legacy_path = storage_root / "policy.json"
    base_path = storage_root / "base.json"
    principals_dir = storage_root / "principals"
    principals_path = principals_dir / "application.json"

    if not legacy_path.exists():
        return
    if base_path.exists() and principals_path.exists():
        return

    legacy_doc = read_json(legacy_path)
    base_doc = default_base_policy_document()

    pap = legacy_doc.get("pap", {})
    resource_skillsets = [str(item.get("name", "")) for item in pap.get("skillsets", []) if str(item.get("name", ""))]
    resource_skills = [str(item.get("name", "")) for item in pap.get("skills", []) if str(item.get("name", ""))]
    resource_tools = [str(item) for item in pap.get("tools", []) if str(item)]

    base_doc["registered_resources"]["skillsets"] = sorted(set(resource_skillsets))
    base_doc["registered_resources"]["skills"] = sorted(set(resource_skills))
    base_doc["registered_resources"]["tools"] = sorted(set(resource_tools))

    pep = legacy_doc.get("pep", {})
    allowed_skillsets = [str(item) for item in pep.get("allowed_skillsets", ["*"])]
    allowed_tools = [str(item) for item in pep.get("allowed_tools", ["*"])]
    allowed_skill_files = [str(item) for item in pep.get("allowed_skill_files", ["*"])]

    if "*" in allowed_skill_files:
        allowed_skills = ["*"]
    else:
        allowed_skills = sorted({Path(item).stem for item in allowed_skill_files if item})

    principals_doc = {
        "principals": {
            "default": {
                "layer": "application",
                "allowed_skillsets": allowed_skillsets or ["*"],
                "allowed_skills": allowed_skills or ["*"],
                "excluded_skills": [],
                "allowed_tools": allowed_tools or ["*"],
            }
        }
    }

    write_json(base_path, base_doc)
    write_json(principals_path, principals_doc)


def _ensure_runtime_policy(storage_root: Path) -> Path:
    runtime_policy_path = storage_root / "runtime_policy.json"
    if runtime_policy_path.exists():
        return runtime_policy_path

    principals_path = storage_root / "principals" / "application.json"
    if principals_path.exists():
        payload = read_json(principals_path)
        principals = payload.get("principals", {})
        runtime_doc = default_runtime_policy_document()
        if isinstance(principals, dict) and principals:
            migrated_profiles: dict[str, Any] = {}
            for name, principal in principals.items():
                if not isinstance(principal, dict):
                    continue
                migrated_profiles[name] = {
                    "layer": str(principal.get("layer", "application")),
                    "allowed_skillsets": [str(item) for item in principal.get("allowed_skillsets", ["*"])],
                    "allowed_skills": [str(item) for item in principal.get("allowed_skills", ["*"])],
                    "excluded_skills": [],
                    "allowed_tools": [str(item) for item in principal.get("allowed_tools", ["*"])],
                }
            if migrated_profiles:
                runtime_doc["profiles"] = migrated_profiles
                runtime_doc["active_profile"] = "default" if "default" in migrated_profiles else sorted(migrated_profiles.keys())[0]
        write_json(runtime_policy_path, runtime_doc)
        return runtime_policy_path

    write_json(runtime_policy_path, default_runtime_policy_document())
    return runtime_policy_path


def read_runtime_policy(policy_path_or_dir: Path) -> dict[str, Any]:
    """Read runtime policy and validate basic required shape."""
    paths = ensure_policy_storage_layout(policy_path_or_dir)
    runtime_path = paths["runtime_policy_path"]
    payload = read_json(runtime_path)

    if not isinstance(payload.get("profiles"), dict) or not payload["profiles"]:
        raise PolicyError(f"Invalid runtime policy profiles in: {runtime_path}")

    active_profile = str(payload.get("active_profile", "")).strip()
    if not active_profile:
        raise PolicyError(f"Missing active_profile in: {runtime_path}")
    if active_profile not in payload["profiles"]:
        raise PolicyError(f"Unknown active_profile '{active_profile}' in: {runtime_path}")

    selection = payload.get("selection")
    if not isinstance(selection, dict):
        raise PolicyError(f"Missing selection object in: {runtime_path}")

    mode = str(selection.get("mode", "")).strip()
    if mode not in ("skill_file", "skillset"):
        raise PolicyError(f"Invalid selection.mode '{mode}' in: {runtime_path}")

    if mode == "skill_file" and not str(selection.get("skill_file", "")).strip():
        raise PolicyError(f"selection.skill_file is required for skill_file mode in: {runtime_path}")
    if mode == "skillset" and not str(selection.get("skillset", "")).strip():
        raise PolicyError(f"selection.skillset is required for skillset mode in: {runtime_path}")

    return payload


def get_active_profile(policy_path_or_dir: Path) -> tuple[str, dict[str, Any]]:
    """Return active profile id and profile object."""
    runtime_doc = read_runtime_policy(policy_path_or_dir)
    active_profile = str(runtime_doc["active_profile"])
    profile = runtime_doc["profiles"].get(active_profile, {})
    if not isinstance(profile, dict):
        raise PolicyError(f"Invalid profile object for '{active_profile}'")
    return active_profile, profile


def ensure_policy_storage_layout(policy_path_or_dir: Path) -> dict[str, Path]:
    """Ensure split policy storage exists and return key file paths."""
    storage_root = resolve_storage_root(policy_path_or_dir)
    storage_root.mkdir(parents=True, exist_ok=True)

    _migrate_from_legacy_if_needed(storage_root)

    base_path = storage_root / "base.json"
    principals_dir = storage_root / "principals"
    principals_path = principals_dir / "application.json"
    runtime_policy_path = storage_root / "runtime_policy.json"

    if not base_path.exists():
        write_json(base_path, default_base_policy_document())
    if not principals_path.exists():
        write_json(principals_path, default_principals_document())

    runtime_policy_path = _ensure_runtime_policy(storage_root)

    return {
        "storage_root": storage_root,
        "base_path": base_path,
        "principals_path": principals_path,
        "runtime_policy_path": runtime_policy_path,
    }


def ensure_policy_document(policy_path: Path) -> dict[str, Any]:
    """Backward-compatible helper for legacy call sites.

    Returns base.json document in split storage layout.
    """
    paths = ensure_policy_storage_layout(policy_path)
    try:
        return read_json(paths["base_path"])
    except PolicyError as exc:
        raise PolicyError(f"Invalid base policy file: {paths['base_path']}") from exc
