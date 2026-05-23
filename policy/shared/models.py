from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    policy_id: str
    action: str
    target: str
    decision_id: str
    timestamp_utc: str


@dataclass(frozen=True)
class PolicyRequest:
    policy_id: str
    action: str
    target: str


class PolicyViolationError(PermissionError):
    def __init__(self, decision: PolicyDecision) -> None:
        self.decision = decision
        super().__init__(decision.reason)


def make_decision(*, allowed: bool, reason: str, policy_id: str, action: str, target: str) -> PolicyDecision:
    return PolicyDecision(
        allowed=allowed,
        reason=reason,
        policy_id=policy_id,
        action=action,
        target=target,
        decision_id=str(uuid4()),
        timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
