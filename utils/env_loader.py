from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional, TypeVar, Union

from dotenv import load_dotenv

T = TypeVar("T")


def load_environment(env_file: Union[Path, str] = ".env") -> None:
    """Load environment variables from a dotenv file if it exists."""
    load_dotenv(dotenv_path=env_file, override=False)


def get_env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    """Return an environment variable with optional required validation."""
    value = os.getenv(name, default)
    if required and (value is None or value.strip() == ""):
        raise ValueError(f"Missing required environment variable: {name}")
    return "" if value is None else value


def get_env_cast(name: str, cast: Callable[[str], T], default: T) -> T:
    """Read and cast an environment variable, falling back to default."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return cast(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid value for {name}: {raw}") from exc


def resolve_project_path(project_root: Path, raw_path: Optional[str], fallback: str) -> Path:
    """Resolve a path from env/config relative to the project root."""
    source = raw_path if raw_path else fallback
    candidate = Path(source)
    if not candidate.is_absolute():
        candidate = (project_root / candidate).resolve()
    return candidate
