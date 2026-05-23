from __future__ import annotations


def build_numbered_source_text(raw_source_text: str) -> str:
    """Render source text with stable 1-based line prefixes for review prompts."""
    lines = raw_source_text.splitlines()
    if not lines:
        lines = [""]

    width = max(4, len(str(len(lines))))
    return "\n".join(f"{index:0{width}d}: {line}" for index, line in enumerate(lines, start=1))
