from __future__ import annotations

from pathlib import Path


def build_langchain_tools(
    project_root: Path,
    skill_root: Path,
    registry_path: Path,
    hyperparams_path: Path,
    allowed_tool_names: list[str] | None = None,
):
    """Assemble all custom tools for the agent runtime."""
    from tools.file_tools import make_file_tools
    from tools.hyperparam_tools import make_hyperparam_tools
    from tools.skill_loader import make_skill_tools

    tools = []
    tools.extend(make_file_tools(project_root))
    tools.extend(make_skill_tools(project_root, skill_root, registry_path))
    tools.extend(make_hyperparam_tools(hyperparams_path))
    if allowed_tool_names is not None and "*" not in set(allowed_tool_names):
        allow = set(allowed_tool_names)
        tools = [tool for tool in tools if getattr(tool, "name", "") in allow]
    return tools


def list_all_tool_names(project_root: Path, skill_root: Path, registry_path: Path, hyperparams_path: Path) -> list[str]:
    """Return all available tool names before policy filtering."""
    tools = build_langchain_tools(
        project_root=project_root,
        skill_root=skill_root,
        registry_path=registry_path,
        hyperparams_path=hyperparams_path,
        allowed_tool_names=None,
    )
    names = sorted({getattr(tool, "name", "") for tool in tools if getattr(tool, "name", "")})
    return names
