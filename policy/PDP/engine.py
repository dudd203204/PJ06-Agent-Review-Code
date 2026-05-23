from __future__ import annotations

from typing import Any

from policy.PAP.registry import PolicyRegistry
from policy.shared.models import PolicyDecision, make_decision


class PolicyEngine:
    def __init__(self, registry: PolicyRegistry) -> None:
        self.registry = registry

    def can_select_skillset(self, policy_id: str, skillset: str) -> PolicyDecision:
        action = "skillset.select"
        principal, denied = self._get_active_principal(policy_id, action, skillset)
        if denied is not None:
            return denied

        resources = self.registry.get_registered_resources()
        if skillset not in set(resources.get("skillsets", [])):
            return self._decision(False, policy_id, action, skillset, f"Unknown skillset '{skillset}'")

        allowed_skillsets = set(principal.get("allowed_skillsets", []))
        allowed = "*" in allowed_skillsets or skillset in allowed_skillsets
        reason = "Skillset selection permitted" if allowed else f"Skillset '{skillset}' is not allowed for '{policy_id}'"
        return self._decision(allowed, policy_id, action, skillset, reason)

    def can_use_skill(self, policy_id: str, skill_name: str) -> PolicyDecision:
        action = "skill.use"
        principal, denied = self._get_active_principal(policy_id, action, skill_name)
        if denied is not None:
            return denied

        resources = self.registry.get_registered_resources()
        if skill_name not in set(resources.get("skills", [])):
            return self._decision(False, policy_id, action, skill_name, f"Unknown skill '{skill_name}'")

        excluded_skills = set(principal.get("excluded_skills", []))
        if skill_name in excluded_skills:
            return self._decision(False, policy_id, action, skill_name, f"Skill '{skill_name}' is excluded for '{policy_id}'")

        allowed_skills = set(principal.get("allowed_skills", []))
        allowed = "*" in allowed_skills or skill_name in allowed_skills
        reason = "Skill usage permitted" if allowed else f"Skill '{skill_name}' is not allowed for '{policy_id}'"
        return self._decision(allowed, policy_id, action, skill_name, reason)

    def can_use_tool(self, policy_id: str, tool_name: str) -> PolicyDecision:
        action = "tool.invoke"
        principal, denied = self._get_active_principal(policy_id, action, tool_name)
        if denied is not None:
            return denied

        resources = self.registry.get_registered_resources()
        if tool_name not in set(resources.get("tools", [])):
            return self._decision(False, policy_id, action, tool_name, f"Unknown tool '{tool_name}'")

        allowed_tools = set(principal.get("allowed_tools", []))
        allowed = "*" in allowed_tools or tool_name in allowed_tools
        reason = "Tool usage permitted" if allowed else f"Tool '{tool_name}' is not allowed for '{policy_id}'"
        return self._decision(allowed, policy_id, action, tool_name, reason)

    def get_principal_allowed_tools(self, policy_id: str) -> list[str]:
        principal, denied = self._get_active_principal(policy_id, "tool.invoke", "*")
        if denied is not None:
            return []

        resources = self.registry.get_registered_resources()
        all_tools = sorted(set(resources.get("tools", [])))
        allowed_tools = set(principal.get("allowed_tools", []))
        if "*" in allowed_tools:
            return all_tools
        return sorted([name for name in all_tools if name in allowed_tools])

    def _get_active_principal(
        self,
        policy_id: str,
        action: str,
        target: str,
    ) -> tuple[dict[str, Any] | None, PolicyDecision | None]:
        principal = self.registry.get_policy(policy_id)
        if principal is None:
            return None, self._decision(False, policy_id, action, target, f"Unknown policy principal '{policy_id}'")

        return principal, None

    def _decision(self, allowed: bool, policy_id: str, action: str, target: str, reason: str) -> PolicyDecision:
        return make_decision(
            allowed=allowed,
            reason=reason,
            policy_id=policy_id,
            action=action,
            target=target,
        )
