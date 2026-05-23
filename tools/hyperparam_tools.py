from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from utils.config_loader import HyperParams, load_hyperparams


def load_shared_hyperparams(hyperparams_path: Path) -> HyperParams:
    """Load validated shared hyperparameters from JSON."""
    return load_hyperparams(hyperparams_path)


def hyperparams_to_dict(hyperparams: HyperParams) -> dict[str, Any]:
    """Convert Pydantic model to plain dict."""
    return hyperparams.model_dump()


def make_hyperparam_tools(hyperparams_path: Path):
    """Build LangChain-compatible hyperparameter tool."""

    @tool("get_hyperparameters")
    def get_hyperparameters() -> str:
        """Get centralized runtime/model hyperparameters as JSON."""
        data = load_shared_hyperparams(hyperparams_path)
        return json.dumps(hyperparams_to_dict(data), indent=2)

    return [get_hyperparameters]
