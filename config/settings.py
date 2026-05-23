from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_HYPERPARAMS: dict[str, Any] = {
    "model": {
        "name": "gpt-4o-mini-2024-07-18",
        "temperature": 0,
        "timeout": 60,
        "provider": "openai",  # "openai" or "custom"
        "custom_endpoint": None,
        "custom_subscription_id": None,
    },
    "runtime": {
        "max_agent_iterations": 6,
        "verbose": True,
    },
    "paths": {
        "skill_registry": "skills/skill_registry.json",
        "skill_root": "skills",
        "policy_root": "policy",
        "policy_file": "policy/storage/policy.json",
        "input_root": "input",
        "proceed_root": "input/proceed",
        "output_root": "output",
    },
}


def standard_hyperparams() -> dict[str, Any]:
    """Return a fresh copy of the default hyperparameter document."""
    return deepcopy(DEFAULT_HYPERPARAMS)



def write_standard_hyperparams(path: Path) -> None:
    """Write the standard hyperparameter file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(standard_hyperparams(), indent=2), encoding="utf-8")



def ensure_standard_hyperparams(path: Path | str) -> Path:
    """Ensure standard hyperparameter file with all required fields.
    
    If file exists but is missing new fields, merge with defaults.
    If file doesn't exist, create with defaults.
    """
    config_path = Path(path)
    defaults = standard_hyperparams()
    
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
            # Deep merge: ensure all default fields exist
            merged = defaults.copy()
            if "model" in existing:
                merged["model"] = {**defaults.get("model", {}), **existing.get("model", {})}
            if "runtime" in existing:
                merged["runtime"] = {**defaults.get("runtime", {}), **existing.get("runtime", {})}
            if "paths" in existing:
                merged["paths"] = {**defaults.get("paths", {}), **existing.get("paths", {})}
            config_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        except (json.JSONDecodeError, IOError):
            # If file is corrupted, recreate
            write_standard_hyperparams(config_path)
    else:
        write_standard_hyperparams(config_path)
    return config_path
