from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from sre_agent.domain.entities.approval import Approval
from sre_agent.domain.entities.incident import Incident


class RCAHypothesisView(BaseModel):
    description: str
    confidence: float
    confidence_label: str
    supporting_evidence: list[str]
    referenced_runbook_ids: list[str]


class ActionView(BaseModel):
    name: str
    parameters: dict[str, str]
    rationale: str
    confidence: float
    requires_hil: bool
    blast_radius_level: str


class ApprovalView(BaseModel):
    approval_id: str
    state: str
    current_approver: str | None
    decision: str | None
    decided_by: str | None
    decided_at: datetime | None
    requested_at: datetime


class IncidentView(BaseModel):
    id: str
    service: str
    status: str
    severity: str | None
    initial_signal: str
    signal_sources: list[str]
    detected_at: datetime
    resolved_at: datetime | None
    rca_hypotheses: list[RCAHypothesisView]
    proposed_action: ActionView | None
    blast_radius_summary: str | None
    jira_ticket_key: str | None = None
    jira_ticket_url: str | None = None
    jira_ticket_status: str | None = None
    jira_ticket_status_updated_at: datetime | None = None

    @classmethod
    def from_domain(cls, incident: Incident) -> IncidentView:
        return cls(
            id=incident.id.value,
            service=str(incident.service),
            status=incident.status.value,
            severity=incident.severity.value if incident.severity else None,
            initial_signal=incident.initial_signal,
            signal_sources=list(incident.signal_sources),
            detected_at=incident.detected_at,
            resolved_at=incident.resolved_at,
            jira_ticket_key=incident.jira_ticket_key,
            jira_ticket_url=incident.jira_ticket_url,
            jira_ticket_status=incident.jira_ticket_status,
            jira_ticket_status_updated_at=incident.jira_ticket_status_updated_at,
            rca_hypotheses=[
                RCAHypothesisView(
                    description=h.description,
                    confidence=h.confidence.value,
                    confidence_label=h.confidence.label,
                    supporting_evidence=list(h.supporting_evidence),
                    referenced_runbook_ids=list(h.referenced_runbook_ids),
                )
                for h in incident.rca_hypotheses
            ],
            proposed_action=(
                ActionView(
                    name=incident.proposed_action.name,
                    parameters=incident.proposed_action.parameters,
                    rationale=incident.proposed_action.rationale,
                    confidence=incident.proposed_action.confidence.value,
                    requires_hil=incident.proposed_action.requires_hil,
                    blast_radius_level=incident.proposed_action.blast_radius.level.value,
                )
                if incident.proposed_action
                else None
            ),
            blast_radius_summary=(
                incident.blast_radius.human_readable if incident.blast_radius else None
            ),
        )


def approval_to_view(approval: Approval) -> ApprovalView:
    return ApprovalView(
        approval_id=approval.id.value,
        state=approval.state.value,
        current_approver=approval.current_approver,
        decision=approval.decision.value if approval.decision else None,
        decided_by=approval.decided_by,
        decided_at=approval.decided_at,
        requested_at=approval.requested_at,
    )
