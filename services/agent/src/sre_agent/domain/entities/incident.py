from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sre_agent.domain.events.incident_events import (
    ActionExecuted,
    ActionProposed,
    ActionVerified,
    EvidenceGathered,
    IncidentDetected,
    IncidentResolved,
    IncidentTriaged,
    PostmortemDrafted,
    RCAGenerated,
    RCAHypothesis,
)
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.value_objects import (
    BlastRadius,
    ConfidenceScore,
    IncidentId,
    ServiceName,
    Severity,
)

if TYPE_CHECKING:
    from sre_agent.domain.events.base import DomainEvent


class IncidentStatus(str, Enum):
    DETECTED = "detected"
    TRIAGED = "triaged"
    DIAGNOSING = "diagnosing"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    FAILED = "failed"


@dataclass(slots=True, kw_only=True)
class ProposedAction:
    name: str
    parameters: dict[str, str]
    rationale: str
    blast_radius: BlastRadius
    confidence: ConfidenceScore
    requires_hil: bool


@dataclass(slots=True, kw_only=True)
class Incident:
    """Aggregate root for the incident lifecycle.

    Mutations produce domain events (appended to `pending_events`). The application
    layer is responsible for persisting events and clearing the buffer.
    """

    id: IncidentId
    service: ServiceName
    status: IncidentStatus
    severity: Severity | None = None
    blast_radius: BlastRadius | None = None
    initial_signal: str = ""
    signal_sources: tuple[str, ...] = field(default_factory=tuple)
    rca_hypotheses: tuple[RCAHypothesis, ...] = field(default_factory=tuple)
    proposed_action: ProposedAction | None = None
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    jira_ticket_key: str | None = None
    jira_ticket_url: str | None = None
    jira_ticket_status: str | None = None
    jira_ticket_status_updated_at: datetime | None = None
    pending_events: list[DomainEvent] = field(default_factory=list)

    @classmethod
    def detect(
        cls,
        *,
        service: ServiceName,
        initial_signal: str,
        signal_sources: tuple[str, ...],
    ) -> Incident:
        incident_id = IncidentId.new()
        incident = cls(
            id=incident_id,
            service=service,
            status=IncidentStatus.DETECTED,
            initial_signal=initial_signal,
            signal_sources=signal_sources,
        )
        incident.pending_events.append(
            IncidentDetected(
                incident_id=incident_id,
                service=service,
                initial_signal=initial_signal,
                signal_sources=signal_sources,
            )
        )
        return incident

    def triage(self, *, severity: Severity, blast_radius: BlastRadius, rationale: str) -> None:
        if self.status != IncidentStatus.DETECTED:
            raise IncidentStateError(f"Cannot triage incident in status {self.status}")
        self.severity = severity
        self.blast_radius = blast_radius
        self.status = IncidentStatus.TRIAGED
        self.pending_events.append(
            IncidentTriaged(
                incident_id=self.id,
                severity=severity,
                blast_radius=blast_radius,
                rationale=rationale,
            )
        )

    def record_evidence(
        self,
        *,
        metric_snapshot_count: int,
        log_line_count: int,
        related_deployments: tuple[str, ...] = (),
    ) -> None:
        if self.status not in (IncidentStatus.TRIAGED, IncidentStatus.DIAGNOSING):
            raise IncidentStateError(f"Cannot record evidence in status {self.status}")
        self.status = IncidentStatus.DIAGNOSING
        self.pending_events.append(
            EvidenceGathered(
                incident_id=self.id,
                metric_snapshot_count=metric_snapshot_count,
                log_line_count=log_line_count,
                related_deployments=related_deployments,
            )
        )

    def record_rca(
        self,
        *,
        hypotheses: tuple[RCAHypothesis, ...],
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        if self.status != IncidentStatus.DIAGNOSING:
            raise IncidentStateError(f"Cannot record RCA in status {self.status}")
        if not hypotheses:
            raise IncidentStateError("RCA must contain at least one hypothesis")
        self.rca_hypotheses = hypotheses
        self.pending_events.append(
            RCAGenerated(
                incident_id=self.id,
                hypotheses=hypotheses,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        )

    def propose_action(self, action: ProposedAction) -> None:
        if self.status != IncidentStatus.DIAGNOSING:
            raise IncidentStateError(f"Cannot propose action in status {self.status}")
        self.proposed_action = action
        self.status = (
            IncidentStatus.AWAITING_APPROVAL if action.requires_hil else IncidentStatus.EXECUTING
        )
        self.pending_events.append(
            ActionProposed(
                incident_id=self.id,
                action_name=action.name,
                action_parameters=tuple(action.parameters.items()),
                rationale=action.rationale,
                blast_radius=action.blast_radius,
                confidence=action.confidence,
                requires_hil=action.requires_hil,
            )
        )

    def start_execution(self) -> None:
        if self.status not in (IncidentStatus.AWAITING_APPROVAL, IncidentStatus.EXECUTING):
            raise IncidentStateError(f"Cannot execute in status {self.status}")
        self.status = IncidentStatus.EXECUTING

    def record_execution_result(self, *, success: bool, output: str, executed_by: str) -> None:
        if self.status != IncidentStatus.EXECUTING:
            raise IncidentStateError(f"Cannot record execution in status {self.status}")
        self.status = IncidentStatus.VERIFYING if success else IncidentStatus.FAILED
        action_name = self.proposed_action.name if self.proposed_action else "unknown"
        self.pending_events.append(
            ActionExecuted(
                incident_id=self.id,
                action_name=action_name,
                success=success,
                output=output,
                executed_by=executed_by,
            )
        )

    def record_verification(
        self, *, metrics_returned_to_baseline: bool, summary: str
    ) -> None:
        if self.status != IncidentStatus.VERIFYING:
            raise IncidentStateError(f"Cannot verify in status {self.status}")
        self.pending_events.append(
            ActionVerified(
                incident_id=self.id,
                metrics_returned_to_baseline=metrics_returned_to_baseline,
                verification_summary=summary,
            )
        )
        if not metrics_returned_to_baseline:
            self.status = IncidentStatus.DIAGNOSING

    def resolve(self, *, summary: str) -> None:
        if self.status not in (IncidentStatus.VERIFYING, IncidentStatus.EXECUTING):
            raise IncidentStateError(f"Cannot resolve in status {self.status}")
        self.status = IncidentStatus.RESOLVED
        self.resolved_at = datetime.now(UTC)
        mttr = (self.resolved_at - self.detected_at).total_seconds()
        self.pending_events.append(
            IncidentResolved(
                incident_id=self.id,
                resolution_summary=summary,
                mttr_seconds=mttr,
            )
        )

    def attach_ticket(self, *, key: str, url: str | None) -> None:
        self.jira_ticket_key = key
        self.jira_ticket_url = url

    def update_ticket_status(self, *, status: str, fetched_at: datetime | None = None) -> None:
        """Refresh the Jira workflow status (e.g. 'To Do', 'In Progress', 'Done').

        Independent of `IncidentStatus` — the ticket can be 'Done' in Jira while
        the agent's incident is still 'awaiting_approval', and vice versa.
        """
        self.jira_ticket_status = status
        self.jira_ticket_status_updated_at = fetched_at or datetime.now(UTC)

    def escalate(self, *, reason: str) -> None:
        self.status = IncidentStatus.ESCALATED
        _ = reason  # recorded via an approval event elsewhere

    def record_postmortem_drafted(self, *, postmortem_id: str, word_count: int) -> None:
        self.pending_events.append(
            PostmortemDrafted(
                incident_id=self.id, postmortem_id=postmortem_id, word_count=word_count
            )
        )

    def drain_events(self) -> list[DomainEvent]:
        events = list(self.pending_events)
        self.pending_events.clear()
        return events

    @property
    def top_hypothesis(self) -> RCAHypothesis | None:
        if not self.rca_hypotheses:
            return None
        return max(self.rca_hypotheses, key=lambda h: h.confidence.value)

    @property
    def is_active(self) -> bool:
        return self.status not in (
            IncidentStatus.RESOLVED,
            IncidentStatus.FAILED,
            IncidentStatus.ESCALATED,
        )
