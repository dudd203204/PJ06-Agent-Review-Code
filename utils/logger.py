from __future__ import annotations

import inspect
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


VIETNAM_TZ = timezone(timedelta(hours=7))


def _is_meaningful(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=VIETNAM_TZ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        def add_if_present(key: str, value: Any) -> None:
            if _is_meaningful(value):
                payload[key] = value

        add_if_present("skill_name", getattr(record, "skill_name", None))

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def _resolve_log_file() -> Path:
    logs_dir = Path.cwd() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return logs_dir / f"{timestamp}.logs"


def _infer_logger_name() -> str:
    frame = inspect.currentframe()
    caller = frame.f_back if frame is not None else None
    workspace_root = Path.cwd().resolve()
    try:
        while caller is not None:
            caller_path = Path(caller.f_code.co_filename).resolve()
            if caller_path != Path(__file__).resolve():
                try:
                    relative_parts = caller_path.relative_to(workspace_root).with_suffix("").parts
                    return ".".join(relative_parts) or "agent_skill"
                except ValueError:
                    return caller_path.stem or "agent_skill"
            caller = caller.f_back
    finally:
        del frame
    return "agent_skill"


def get_logger(name: str | None = None, level: int = logging.INFO) -> logging.Logger:
    """Create or return a configured console logger."""
    if name is None:
        name = _infer_logger_name()
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    stream_handler = logging.StreamHandler()
    file_handler = logging.FileHandler(_resolve_log_file(), encoding="utf-8", delay=True)
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger
