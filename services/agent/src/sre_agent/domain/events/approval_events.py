from __future__ import annotations

from dataclasses import dataclass

from sre_agent.domain.events.base import DomainEvent
from sre_agent.domain.value_objects import ApprovalId, IncidentId


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovalRequested(DomainEvent):
    approval_id: ApprovalId
    incident_id: IncidentId
    action_name: str
    notified_user: str
    channel: str
    timeout_seconds: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovalEscalated(DomainEvent):
    approval_id: ApprovalId
    incident_id: IncidentId
    from_user: str
    to_user: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovalGranted(DomainEvent):
    approval_id: ApprovalId
    incident_id: IncidentId
    approved_by: str
    modifications: str | None = None
    latency_seconds: float = 0.0


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovalRejected(DomainEvent):
    approval_id: ApprovalId
    incident_id: IncidentId
    rejected_by: str
    reason: str
    latency_seconds: float = 0.0


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovalTimedOut(DomainEvent):
    approval_id: ApprovalId
    incident_id: IncidentId
    timed_out_user: str
