from __future__ import annotations

from dataclasses import dataclass, field

from sre_agent.domain.events.base import DomainEvent
from sre_agent.domain.value_objects import (
    BlastRadius,
    ConfidenceScore,
    IncidentId,
    ServiceName,
    Severity,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class IncidentDetected(DomainEvent):
    incident_id: IncidentId
    service: ServiceName
    initial_signal: str
    signal_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class IncidentTriaged(DomainEvent):
    incident_id: IncidentId
    severity: Severity
    blast_radius: BlastRadius
    rationale: str


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceGathered(DomainEvent):
    incident_id: IncidentId
    metric_snapshot_count: int
    log_line_count: int
    related_deployments: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True, kw_only=True)
class RCAHypothesis:
    description: str
    confidence: ConfidenceScore
    supporting_evidence: tuple[str, ...]
    referenced_runbook_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True, kw_only=True)
class RCAGenerated(DomainEvent):
    incident_id: IncidentId
    hypotheses: tuple[RCAHypothesis, ...]
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionProposed(DomainEvent):
    incident_id: IncidentId
    action_name: str
    action_parameters: tuple[tuple[str, str], ...]
    rationale: str
    blast_radius: BlastRadius
    confidence: ConfidenceScore
    requires_hil: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionExecuted(DomainEvent):
    incident_id: IncidentId
    action_name: str
    success: bool
    output: str
    executed_by: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionVerified(DomainEvent):
    incident_id: IncidentId
    metrics_returned_to_baseline: bool
    verification_summary: str


@dataclass(frozen=True, slots=True, kw_only=True)
class IncidentResolved(DomainEvent):
    incident_id: IncidentId
    resolution_summary: str
    mttr_seconds: float


@dataclass(frozen=True, slots=True, kw_only=True)
class PostmortemDrafted(DomainEvent):
    incident_id: IncidentId
    postmortem_id: str
    word_count: int
