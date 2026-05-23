from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class PolicyRegistry(ABC):
    @abstractmethod
    def load(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def get_registered_resources(self) -> dict[str, list[str]]:
        raise NotImplementedError

    @abstractmethod
    def get_runtime_policy(self) -> dict[str, Any]:
        raise NotImplementedError


class JsonPolicyRegistry(PolicyRegistry):
    """JSON-backed PAP registry loader for base + principals split layout."""

    def __init__(self, root_path: str | Path) -> None:
        from policy.PAP.storage_access import resolve_policy_storage_root

        self._root_path = Path(root_path)
        self._storage_root = resolve_policy_storage_root(self._root_path)
        self._cache: dict[str, Any] = {}
        self._fingerprint: tuple[tuple[str, int, int], ...] = ()

    @property
    def storage_root(self) -> Path:
        return self._storage_root

    def load(self) -> None:
        from policy.PAP.storage_access import compute_policy_fingerprint

        raw = self._load_raw()
        self._validate(raw)
        self._cache = raw
        self._fingerprint = compute_policy_fingerprint(self._storage_root)

    def ensure_fresh(self) -> bool:
        from policy.PAP.storage_access import compute_policy_fingerprint

        current_fingerprint = compute_policy_fingerprint(self._storage_root)
        if self._cache and current_fingerprint == self._fingerprint:
            return False

        raw = self._load_raw()
        self._validate(raw)
        self._cache = raw
        self._fingerprint = current_fingerprint
        return True

    def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        return self._cache.get("principals", {}).get(policy_id)

    def get_registered_resources(self) -> dict[str, list[str]]:
        return self._cache.get("registered_resources", {})

    def get_runtime_policy(self) -> dict[str, Any]:
        payload = self._cache.get("runtime_policy", {})
        return payload if isinstance(payload, dict) else {}

    def _load_raw(self) -> dict[str, Any]:
        if self._root_path.is_file():
            return self._read_json(self._root_path)

        root = self._root_path
        if (root / "storage").exists():
            root = root / "storage"

        base_path = root / "base.json"
        principals_path = root / "principals"
        runtime_policy_path = root / "runtime_policy.json"

        if not base_path.exists():
            raise FileNotFoundError(f"Policy base file not found: {base_path}")

        base = self._read_json(base_path)
        if runtime_policy_path.exists():
            runtime_policy = self._read_json(runtime_policy_path)
            profiles = runtime_policy.get("profiles", {})
            if not isinstance(profiles, dict) or not profiles:
                raise ValueError(f"Invalid profiles in {runtime_policy_path}")
            base["runtime_policy"] = runtime_policy
            base["principals"] = profiles
            return base

        if not principals_path.exists():
            raise FileNotFoundError(f"Policy principals folder not found: {principals_path}")

        base["runtime_policy"] = {}
        base["principals"] = self._load_principals(principals_path)
        return base

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        if not isinstance(data, dict):
            raise ValueError(f"Policy JSON must be an object: {path}")
        return data

    def _load_principals(self, principals_path: Path) -> dict[str, Any]:
        merged_principals: dict[str, Any] = {}
        for file_path in sorted(principals_path.glob("*.json")):
            payload = self._read_json(file_path)
            file_principals = payload.get("principals", {})
            if not isinstance(file_principals, dict):
                raise ValueError(f"Invalid principals object in {file_path}")

            for principal_id, principal_data in file_principals.items():
                if principal_id in merged_principals:
                    raise ValueError(f"Duplicate principal '{principal_id}' across policy files")
                if not isinstance(principal_data, dict):
                    raise ValueError(f"Principal '{principal_id}' must be an object")
                principal_data.setdefault("excluded_skills", [])
                merged_principals[principal_id] = principal_data

        if not merged_principals:
            raise ValueError("No principals found in policy files")

        return merged_principals

    def _validate(self, data: dict[str, Any]) -> None:
        def _ensure_list(value: Any, field_name: str) -> list[Any]:
            if not isinstance(value, list):
                raise ValueError(f"{field_name} must be a list")
            return value

        schema_marker = data.get("schema")
        if schema_marker != "policy-schema/v1":
            raise ValueError("Invalid policy schema marker. Expected 'policy-schema/v1'")

        resources = data.get("registered_resources")
        if not isinstance(resources, dict):
            raise ValueError("'registered_resources' must be an object")

        resource_keys = ("skillsets", "skills", "tools", "actions")
        for key in resource_keys:
            values = _ensure_list(resources.get(key), f"registered_resources.{key}")
            if len(values) != len(set(values)):
                raise ValueError(f"registered_resources.{key} contains duplicates")

        principals = data.get("principals")
        if not isinstance(principals, dict) or not principals:
            raise ValueError("'principals' must be a non-empty object")

        registered_skillsets = set(resources.get("skillsets", []))
        registered_skills = set(resources.get("skills", []))
        registered_tools = set(resources.get("tools", []))

        required_fields = {
            "layer",
            "allowed_skillsets",
            "allowed_skills",
            "excluded_skills",
            "allowed_tools",
        }

        for principal_id, principal in principals.items():
            if not isinstance(principal, dict):
                raise ValueError(f"Principal '{principal_id}' must be an object")

            missing = required_fields - set(principal.keys())
            if missing:
                raise ValueError(f"Principal '{principal_id}' is missing fields: {sorted(missing)}")

            allowed_skillsets = _ensure_list(principal.get("allowed_skillsets"), f"principal.{principal_id}.allowed_skillsets")
            allowed_skills = _ensure_list(principal.get("allowed_skills"), f"principal.{principal_id}.allowed_skills")
            excluded_skills = _ensure_list(principal.get("excluded_skills"), f"principal.{principal_id}.excluded_skills")
            allowed_tools = _ensure_list(principal.get("allowed_tools"), f"principal.{principal_id}.allowed_tools")

            unknown_skillsets = [item for item in allowed_skillsets if item != "*" and item not in registered_skillsets]
            if unknown_skillsets:
                raise ValueError(f"Principal '{principal_id}' has unknown skillsets: {sorted(unknown_skillsets)}")

            unknown_skills = [item for item in allowed_skills if item != "*" and item not in registered_skills]
            if unknown_skills:
                raise ValueError(f"Principal '{principal_id}' has unknown skills: {sorted(unknown_skills)}")

            unknown_excluded = [item for item in excluded_skills if item not in registered_skills]
            if unknown_excluded:
                raise ValueError(f"Principal '{principal_id}' has unknown excluded skills: {sorted(unknown_excluded)}")

            unknown_tools = [item for item in allowed_tools if item != "*" and item not in registered_tools]
            if unknown_tools:
                raise ValueError(f"Principal '{principal_id}' has unknown tools: {sorted(unknown_tools)}")
