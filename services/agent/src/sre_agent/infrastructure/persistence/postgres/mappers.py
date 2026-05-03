from __future__ import annotations

from typing import Any

from sre_agent.domain.entities.approval import Approval, ApprovalDecision, ApprovalSagaState
from sre_agent.domain.entities.incident import Incident, IncidentStatus, ProposedAction
from sre_agent.domain.entities.postmortem import CorrectiveAction, Postmortem, TimelineEntry
from sre_agent.domain.events.incident_events import RCAHypothesis
from sre_agent.domain.value_objects import (
    ApprovalId,
    BlastRadius,
    BlastRadiusLevel,
    ConfidenceScore,
    IncidentId,
    ServiceName,
    Severity,
)
from sre_agent.infrastructure.persistence.models.orm import (
    ApprovalModel,
    IncidentModel,
    PostmortemModel,
)


def incident_to_model(incident: Incident) -> IncidentModel:
    return IncidentModel(
        id=incident.id.value,
        service=str(incident.service),
        status=incident.status.value,
        severity=incident.severity.value if incident.severity else None,
        initial_signal=incident.initial_signal,
        signal_sources=list(incident.signal_sources),
        blast_radius=_blast_to_json(incident.blast_radius),
        rca_hypotheses=[_hypothesis_to_json(h) for h in incident.rca_hypotheses],
        proposed_action=_action_to_json(incident.proposed_action),
        detected_at=incident.detected_at,
        resolved_at=incident.resolved_at,
        jira_ticket_key=incident.jira_ticket_key,
        jira_ticket_url=incident.jira_ticket_url,
        jira_ticket_status=incident.jira_ticket_status,
        jira_ticket_status_updated_at=incident.jira_ticket_status_updated_at,
    )


def incident_from_model(model: IncidentModel) -> Incident:
    return Incident(
        id=IncidentId(value=model.id),
        service=ServiceName(model.service),
        status=IncidentStatus(model.status),
        severity=Severity(model.severity) if model.severity else None,
        blast_radius=_blast_from_json(model.blast_radius),
        initial_signal=model.initial_signal,
        signal_sources=tuple(model.signal_sources or []),
        rca_hypotheses=tuple(_hypothesis_from_json(h) for h in (model.rca_hypotheses or [])),
        proposed_action=_action_from_json(model.proposed_action),
        detected_at=model.detected_at,
        resolved_at=model.resolved_at,
        jira_ticket_key=model.jira_ticket_key,
        jira_ticket_url=model.jira_ticket_url,
        jira_ticket_status=model.jira_ticket_status,
        jira_ticket_status_updated_at=model.jira_ticket_status_updated_at,
    )


def apply_incident_to_model(incident: Incident, model: IncidentModel) -> None:
    model.service = str(incident.service)
    model.status = incident.status.value
    model.severity = incident.severity.value if incident.severity else None
    model.initial_signal = incident.initial_signal
    model.signal_sources = list(incident.signal_sources)
    model.blast_radius = _blast_to_json(incident.blast_radius)
    model.rca_hypotheses = [_hypothesis_to_json(h) for h in incident.rca_hypotheses]
    model.proposed_action = _action_to_json(incident.proposed_action)
    model.detected_at = incident.detected_at
    model.resolved_at = incident.resolved_at
    model.jira_ticket_key = incident.jira_ticket_key
    model.jira_ticket_url = incident.jira_ticket_url
    model.jira_ticket_status = incident.jira_ticket_status
    model.jira_ticket_status_updated_at = incident.jira_ticket_status_updated_at


def approval_to_model(approval: Approval) -> ApprovalModel:
    return ApprovalModel(
        id=approval.id.value,
        incident_id=approval.incident_id.value,
        action_name=approval.action_name,
        state=approval.state.value,
        current_approver=approval.current_approver,
        primary_user=approval.primary_user,
        secondary_user=approval.secondary_user,
        commander_group=approval.commander_group,
        decision=approval.decision.value if approval.decision else None,
        decided_by=approval.decided_by,
        decided_at=approval.decided_at,
        rejection_reason=approval.rejection_reason,
        modifications=approval.modifications,
        requested_at=approval.requested_at,
    )


def approval_from_model(model: ApprovalModel) -> Approval:
    return Approval(
        id=ApprovalId(value=model.id),
        incident_id=IncidentId(value=model.incident_id),
        action_name=model.action_name,
        state=ApprovalSagaState(model.state),
        current_approver=model.current_approver,
        primary_user=model.primary_user,
        secondary_user=model.secondary_user,
        commander_group=model.commander_group,
        decision=ApprovalDecision(model.decision) if model.decision else None,
        decided_by=model.decided_by,
        decided_at=model.decided_at,
        rejection_reason=model.rejection_reason,
        modifications=model.modifications,
        requested_at=model.requested_at,
    )


def apply_approval_to_model(approval: Approval, model: ApprovalModel) -> None:
    model.state = approval.state.value
    model.current_approver = approval.current_approver
    model.decision = approval.decision.value if approval.decision else None
    model.decided_by = approval.decided_by
    model.decided_at = approval.decided_at
    model.rejection_reason = approval.rejection_reason
    model.modifications = approval.modifications
    model.requested_at = approval.requested_at


def postmortem_to_model(pm: Postmortem) -> PostmortemModel:
    return PostmortemModel(
        id=pm.id,
        incident_id=pm.incident_id.value,
        title=pm.title,
        summary=pm.summary,
        root_cause=pm.root_cause,
        impact=pm.impact,
        lessons_learned=pm.lessons_learned,
        timeline=[{"at": e.at.isoformat(), "event": e.event} for e in pm.timeline],
        corrective_actions=[
            {"description": a.description, "owner": a.owner} for a in pm.corrective_actions
        ],
        drafted_at=pm.drafted_at,
        published_at=pm.published_at,
        signed_off_by=pm.signed_off_by,
    )


def postmortem_from_model(model: PostmortemModel) -> Postmortem:
    from datetime import datetime

    timeline = tuple(
        TimelineEntry(at=datetime.fromisoformat(e["at"]), event=e["event"])
        for e in (model.timeline or [])
    )
    corrective = tuple(
        CorrectiveAction(description=a["description"], owner=a["owner"])
        for a in (model.corrective_actions or [])
    )
    return Postmortem(
        id=model.id,
        incident_id=IncidentId(value=model.incident_id),
        title=model.title,
        summary=model.summary,
        timeline=timeline,
        root_cause=model.root_cause,
        impact=model.impact,
        corrective_actions=corrective,
        lessons_learned=model.lessons_learned,
        drafted_at=model.drafted_at,
        published_at=model.published_at,
        signed_off_by=model.signed_off_by,
    )


# Helpers ------------------------------------------------------------------


def _blast_to_json(b: BlastRadius | None) -> dict[str, Any] | None:
    if b is None:
        return None
    return {
        "level": b.level.value,
        "affected_services": list(b.affected_services),
        "estimated_users_affected": b.estimated_users_affected,
        "estimated_downtime_seconds": b.estimated_downtime_seconds,
        "reversible": b.reversible,
    }


def _blast_from_json(d: dict[str, Any] | None) -> BlastRadius | None:
    if not d:
        return None
    return BlastRadius(
        level=BlastRadiusLevel(d["level"]),
        affected_services=tuple(d.get("affected_services", [])),
        estimated_users_affected=int(d.get("estimated_users_affected", 0)),
        estimated_downtime_seconds=int(d.get("estimated_downtime_seconds", 0)),
        reversible=bool(d.get("reversible", True)),
    )


def _hypothesis_to_json(h: RCAHypothesis) -> dict[str, Any]:
    return {
        "description": h.description,
        "confidence": h.confidence.value,
        "supporting_evidence": list(h.supporting_evidence),
        "referenced_runbook_ids": list(h.referenced_runbook_ids),
    }


def _hypothesis_from_json(d: dict[str, Any]) -> RCAHypothesis:
    return RCAHypothesis(
        description=d["description"],
        confidence=ConfidenceScore(float(d["confidence"])),
        supporting_evidence=tuple(d.get("supporting_evidence", [])),
        referenced_runbook_ids=tuple(d.get("referenced_runbook_ids", [])),
    )


def _action_to_json(a: ProposedAction | None) -> dict[str, Any] | None:
    if a is None:
        return None
    return {
        "name": a.name,
        "parameters": a.parameters,
        "rationale": a.rationale,
        "blast_radius": _blast_to_json(a.blast_radius),
        "confidence": a.confidence.value,
        "requires_hil": a.requires_hil,
    }


def _action_from_json(d: dict[str, Any] | None) -> ProposedAction | None:
    if not d:
        return None
    return ProposedAction(
        name=d["name"],
        parameters=dict(d.get("parameters", {})),
        rationale=d["rationale"],
        blast_radius=_blast_from_json(d["blast_radius"]) or BlastRadius(level=BlastRadiusLevel.LOW),
        confidence=ConfidenceScore(float(d["confidence"])),
        requires_hil=bool(d["requires_hil"]),
    )
