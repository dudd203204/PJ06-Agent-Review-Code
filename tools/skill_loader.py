from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SkillLoadError(RuntimeError):
    """Raised when skill metadata or files cannot be loaded."""


REQUIRED_SKILL_FIELDS = {"skill", "description", "goal", "procedure", "output_style"}
DESCRIPTION_FILE_NAME = "description.json"


def _resolve_from_root(project_root: Path, relative_or_abs: str) -> Path:
    path = Path(relative_or_abs)
    if not path.is_absolute():
        path = (project_root / path).resolve()
    return path


def load_skill_file(skill_file: Path) -> dict[str, Any]:
    """Load and validate a skill definition JSON file."""
    try:
        skill = json.loads(skill_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SkillLoadError(f"Invalid skill JSON: {skill_file}") from exc

    missing = REQUIRED_SKILL_FIELDS.difference(skill)
    if missing:
        raise SkillLoadError(f"Skill file missing required fields {sorted(missing)}: {skill_file}")
    return skill


def resolve_response_format(skill_data: dict[str, Any]) -> dict[str, Any] | None:
    """Return the overall output_style.format object for a skill, when present."""
    output_style = skill_data.get("output_style")
    if not isinstance(output_style, dict) or "format" not in output_style:
        return None

    response_format = output_style.get("format")
    if not isinstance(response_format, dict) or not response_format:
        raise SkillLoadError("Skill output_style.format must be a non-empty object")
    return response_format


def _iter_skillset_dirs(skill_root: Path) -> list[Path]:
    return sorted([path for path in skill_root.iterdir() if path.is_dir()])


def _iter_skill_files(skillset_dir: Path) -> list[Path]:
    files = [
        path
        for path in sorted(skillset_dir.glob("*.json"))
        if path.name != DESCRIPTION_FILE_NAME
    ]
    return files


def _write_text_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def write_skillset_description(project_root: Path, skillset_dir: Path, skills: list[dict[str, str]]) -> None:
    """Write human-friendly description metadata for a skillset folder."""
    payload = {
        "skillset": skillset_dir.name,
        "description": f"Skillset {skillset_dir.name}",
        "skills": [
            {
                "skill_name": item["name"],
                "description": item["description"],
                "skill_file": item["skill_file"],
            }
            for item in skills
        ],
    }
    description_path = skillset_dir / DESCRIPTION_FILE_NAME
    _write_text_if_changed(description_path, json.dumps(payload, indent=2))


def build_skill_registry(project_root: Path, skill_root: Path, registry_path: Path) -> dict[str, Any]:
    """Discover skill JSON files in skillset folders and sync derived metadata files."""
    skill_root.mkdir(parents=True, exist_ok=True)

    skills: list[dict[str, str]] = []
    for skillset_dir in _iter_skillset_dirs(skill_root):
        skillset_entries: list[dict[str, str]] = []
        for skill_file in _iter_skill_files(skillset_dir):
            skill_data = load_skill_file(skill_file)
            entry = {
                "name": skill_file.stem,
                "description": str(skill_data["description"]),
                "skill_file": str(skill_file.relative_to(project_root)).replace("\\", "/"),
            }
            skills.append(entry)
            skillset_entries.append(entry)
        if skillset_entries:
            write_skillset_description(project_root, skillset_dir, skillset_entries)

    registry = {"skills": skills}
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    _write_text_if_changed(registry_path, json.dumps(registry, indent=2))
    return registry


def load_skill_registry(registry_path: Path) -> dict[str, Any]:
    """Load the skill registry JSON file."""
    if not registry_path.exists():
        raise SkillLoadError(f"Skill registry not found: {registry_path}")

    try:
        return json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SkillLoadError(f"Invalid JSON in skill registry: {registry_path}") from exc


def get_skill_metadata(registry: dict[str, Any], skill_name: str, skillset: str | None = None) -> dict[str, Any]:
    """Find a skill entry by name and optional skillset in the registry."""
    skills = registry.get("skills", [])
    if skillset:
        scoped = [
            item
            for item in skills
            if Path(str(item.get("skill_file", ""))).parent.name == skillset and item.get("name") == skill_name
        ]
        if scoped:
            return scoped[0]

    for skill in skills:
        if skill.get("name") == skill_name:
            return skill
    raise SkillLoadError(f"Skill not found in registry: {skill_name}")


def load_skill_bundle(project_root: Path, registry_path: Path, skill_name: str, skillset: str | None = None) -> dict[str, Any]:
    """Load a JSON skill definition for a given skill name."""
    registry = load_skill_registry(registry_path)
    metadata = get_skill_metadata(registry, skill_name, skillset=skillset)

    skill_file = _resolve_from_root(project_root, metadata["skill_file"])
    if not skill_file.exists():
        raise SkillLoadError(f"Skill file missing for: {skill_name}")

    skill_data = load_skill_file(skill_file)
    response_format = resolve_response_format(skill_data)

    return {
        "name": metadata.get("name"),
        "description": metadata.get("description", ""),
        "skill": skill_data.get("skill"),
        "goal": skill_data.get("goal"),
        "procedure": skill_data.get("procedure"),
        "output_style": skill_data.get("output_style"),
        "response_format": response_format,
        "skill_file": str(skill_file.relative_to(project_root)).replace("\\", "/"),
        "skillset": Path(str(metadata.get("skill_file", ""))).parent.name,
    }


def load_skillset_bundle(project_root: Path, skill_root: Path, skillset: str) -> dict[str, Any]:
    """Load the description metadata for a specific skillset folder."""
    skillset_dir = (skill_root / skillset).resolve()
    if not skillset_dir.exists() or not skillset_dir.is_dir():
        raise SkillLoadError(f"Skillset folder not found: {skillset}")

    description_path = skillset_dir / DESCRIPTION_FILE_NAME
    if not description_path.exists():
        raise SkillLoadError(f"Skillset description file not found: {description_path}")

    try:
        description_data = json.loads(description_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SkillLoadError(f"Invalid JSON in skillset description: {description_path}") from exc

    if "skills" not in description_data:
        raise SkillLoadError(f"Skillset description missing skills list: {description_path}")

    return {
        "mode": "skillset",
        "skillset": skillset,
        "description_file": str(description_path.relative_to(project_root)).replace("\\", "/"),
        "skills": description_data.get("skills", []),
    }


def resolve_skill_file_input(project_root: Path, registry_path: Path, skill_file_input: str) -> dict[str, str]:
    """Resolve user-provided skill file input to one registry entry."""
    registry = load_skill_registry(registry_path)
    skills = registry.get("skills", [])

    normalized = skill_file_input.replace("\\", "/")
    if normalized.endswith(".json"):
        normalized_no_ext = normalized[:-5]
    else:
        normalized_no_ext = normalized

    direct = Path(normalized)
    if not direct.is_absolute():
        direct = (project_root / normalized).resolve()
    if direct.exists() and direct.is_file():
        direct_rel = str(direct.relative_to(project_root)).replace("\\", "/")
        for item in skills:
            if item.get("skill_file") == direct_rel:
                return {
                    "name": str(item.get("name", "")),
                    "skill_file": str(item.get("skill_file", "")),
                    "skillset": Path(str(item.get("skill_file", ""))).parent.name,
                }

    leaf = Path(normalized_no_ext).name
    matches = [item for item in skills if str(item.get("name")) == leaf]
    if len(matches) == 1:
        match = matches[0]
        return {
            "name": str(match.get("name", "")),
            "skill_file": str(match.get("skill_file", "")),
            "skillset": Path(str(match.get("skill_file", ""))).parent.name,
        }
    if len(matches) > 1:
        options = ", ".join(str(item.get("skill_file")) for item in matches)
        raise SkillLoadError(f"Ambiguous skill file input '{skill_file_input}'. Matches: {options}")

    raise SkillLoadError(f"Skill file input not found: {skill_file_input}")


def make_skill_tools(project_root: Path, skill_root: Path, registry_path: Path):
    """Build LangChain-compatible skill tools."""
    from langchain_core.tools import tool

    @tool("load_skill")
    def load_skill(skill_name: str, skillset: str = "") -> str:
        """Load a skill by name from the registry and return JSON payload."""
        build_skill_registry(project_root, skill_root, registry_path)
        selected_skillset = skillset if skillset else None
        skill = load_skill_bundle(project_root, registry_path, skill_name, skillset=selected_skillset)
        return json.dumps(skill, indent=2)

    @tool("list_skills")
    def list_skills() -> str:
        """List available skills from the registry."""
        registry = build_skill_registry(project_root, skill_root, registry_path)
        skills = [
            {
                "name": item.get("name"),
                "description": item.get("description", ""),
                "skill_file": item.get("skill_file", ""),
                "skillset": Path(str(item.get("skill_file", ""))).parent.name,
            }
            for item in registry.get("skills", [])
        ]
        return json.dumps(skills, indent=2)

    return [load_skill, list_skills]
