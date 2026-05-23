from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from policy.errors import PolicyError
from policy.utils import read_runtime_policy


@dataclass(frozen=True)
class SkillExecutionPlan:
    skill_name: str
    criterion: str


@dataclass(frozen=True)
class RouteExecutionPlan:
    route: str
    workflow: str
    profile: str
    skillset: str
    skills: list[SkillExecutionPlan]
    allowed_tools: list[str] = field(default_factory=list)


def _registry_skillset_names(registry: Dict[str, Any]) -> Set[str]:
    return {
        str(item.get("skill_file", "")).replace("\\", "/").split("/")[-2]
        for item in registry.get("skills", [])
        if "/" in str(item.get("skill_file", "")).replace("\\", "/")
    }


def _registry_skill_names_for_skillset(registry: Dict[str, Any], skillset: str) -> Set[str]:
    names: set[str] = set()
    for item in registry.get("skills", []):
        skill_file = str(item.get("skill_file", "")).replace("\\", "/")
        if "/" not in skill_file:
            continue
        if skill_file.split("/")[-2] == skillset:
            names.add(str(item.get("name", "")))
    return {name for name in names if name}


def _normalize_skill_item(item: Any) -> SkillExecutionPlan:
    if isinstance(item, str):
        skill_name = item.strip()
        if not skill_name:
            raise PolicyError("Route skill entries must not be empty")
        return SkillExecutionPlan(skill_name=skill_name, criterion=skill_name)

    if isinstance(item, dict):
        skill_name = str(item.get("skill_name", "")).strip()
        criterion = str(item.get("criterion", skill_name)).strip() or skill_name
        if not skill_name:
            raise PolicyError("Route skill object missing skill_name")
        return SkillExecutionPlan(skill_name=skill_name, criterion=criterion)

    raise PolicyError(f"Unsupported route skill entry: {item!r}")


def resolve_route_execution_plan(policy_path, route: str, registry: Dict[str, Any]) -> RouteExecutionPlan:
    runtime_policy = read_runtime_policy(policy_path)
    routes = runtime_policy.get("routes")
    if not isinstance(routes, dict):
        raise PolicyError("runtime_policy.routes is required for batch execution")

    route_config = routes.get(route)
    if not isinstance(route_config, dict):
        raise PolicyError(f"Runtime policy route '{route}' is not configured")

    profiles = runtime_policy.get("profiles", {})
    if not isinstance(profiles, dict):
        raise PolicyError("runtime_policy.profiles must be an object")

    profile_name = str(route_config.get("profile") or runtime_policy.get("active_profile", "")).strip()
    if not profile_name or profile_name not in profiles:
        raise PolicyError(f"Route '{route}' references unknown profile '{profile_name}'")

    profile = profiles[profile_name]
    if not isinstance(profile, dict):
        raise PolicyError(f"Profile '{profile_name}' must be an object")

    skillset = str(route_config.get("skillset", "")).strip()
    if not skillset:
        raise PolicyError(f"Route '{route}' is missing skillset")

    registered_skillsets = _registry_skillset_names(registry)
    if skillset not in registered_skillsets:
        raise PolicyError(f"Route '{route}' references unknown skillset '{skillset}'")

    allowed_skillsets = {str(item) for item in profile.get("allowed_skillsets", [])}
    if "*" not in allowed_skillsets and skillset not in allowed_skillsets:
        raise PolicyError(f"Skillset '{skillset}' is not allowed for profile '{profile_name}'")

    raw_skills = route_config.get("skills", [])
    if not isinstance(raw_skills, list):
        raise PolicyError(f"Route '{route}'.skills must be a list")

    registered_skills = _registry_skill_names_for_skillset(registry, skillset)
    allowed_skills = {str(item) for item in profile.get("allowed_skills", [])}
    excluded_skills = {str(item) for item in profile.get("excluded_skills", [])}
    allowed_tools = [str(item) for item in profile.get("allowed_tools", [])]

    skills: list[SkillExecutionPlan] = []
    for raw_skill in raw_skills:
        skill = _normalize_skill_item(raw_skill)
        if skill.skill_name not in registered_skills:
            raise PolicyError(f"Route '{route}' references unknown skill '{skill.skill_name}' in skillset '{skillset}'")
        if "*" not in allowed_skills and skill.skill_name not in allowed_skills:
            raise PolicyError(f"Skill '{skill.skill_name}' is not allowed for profile '{profile_name}'")
        if skill.skill_name in excluded_skills:
            continue
        skills.append(skill)

    if not skills:
        raise PolicyError(f"Route '{route}' has no runnable skills after policy filtering")

    return RouteExecutionPlan(
        route=route,
        workflow=str(route_config.get("workflow", "generic_review")),
        profile=profile_name,
        skillset=skillset,
        skills=skills,
        allowed_tools=allowed_tools,
    )
