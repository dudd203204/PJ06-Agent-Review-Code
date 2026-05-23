from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

from config.settings import ensure_standard_hyperparams


class ModelSettings(BaseModel):
    name: str = Field(min_length=1)
    temperature: float = Field(ge=0, le=2)
    timeout: int = Field(gt=0)
    provider: str = Field(default="openai", description="LLM provider: 'openai' or 'custom'")
    custom_endpoint: Optional[str] = Field(default=None, description="Custom LLM endpoint URL")
    custom_subscription_id: Optional[str] = Field(default=None, description="Custom LLM subscription ID")


class RuntimeSettings(BaseModel):
    max_agent_iterations: int = Field(default=6, gt=0)
    verbose: bool = True


class PathSettings(BaseModel):
    skill_registry: str = "skills/skill_registry.json"
    skill_root: str = "skills"
    policy_root: str = "policy"
    policy_file: str = "policy/storage/policy.json"
    input_root: str = "input"
    proceed_root: str = "input/proceed"
    output_root: str = "output"


class HyperParams(BaseModel):
    model: ModelSettings
    runtime: RuntimeSettings
    paths: PathSettings


class HyperParamLoadError(RuntimeError):
    """Raised when hyperparameter configuration cannot be loaded."""


def load_hyperparams(path: str | Path) -> HyperParams:
    """Load and validate hyperparameters from JSON."""
    config_path = Path(path)
    ensure_standard_hyperparams(config_path)

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return HyperParams.model_validate(data)
    except json.JSONDecodeError as exc:
        raise HyperParamLoadError(f"Invalid JSON in hyperparameter file: {config_path}") from exc
    except ValidationError as exc:
        raise HyperParamLoadError(f"Invalid hyperparameter schema in {config_path}: {exc}") from exc
