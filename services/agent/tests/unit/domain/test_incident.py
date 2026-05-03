from __future__ import annotations

import pytest

from sre_agent.domain.entities.incident import Incident, IncidentStatus, ProposedAction
from sre_agent.domain.events.incident_events import (
    ActionExecuted,
    ActionProposed,
    ActionVerified,
    EvidenceGathered,
    IncidentDetected,
    IncidentResolved,
    IncidentTriaged,
    RCAGenerated,
    RCAHypothesis,
)
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.value_objects import (
    BlastRadius,
    BlastRadiusLevel,
    ConfidenceScore,
    ServiceName,
    Severity,
)


def _make_incident() -> Incident:
    return Incident.detect(
        service=ServiceName("payments-api"),
        initial_signal="error rate spike",
        signal_sources=("prometheus",),
    )


class TestIncidentLifecycle:
    def test_detect_emits_event(self) -> None:
        inc = _make_incident()
        events = inc.drain_events()
        assert len(events) == 1
        assert isinstance(events[0], IncidentDetected)
        assert inc.status == IncidentStatus.DETECTED

    def test_full_happy_path(self) -> None:
        inc = _make_incident()
        inc.drain_events()
        inc.triage(
            severity=Severity.P2,
            blast_radius=BlastRadius(level=BlastRadiusLevel.LOW),
            rationale="test",
        )
        assert inc.status == IncidentStatus.TRIAGED

        inc.record_evidence(metric_snapshot_count=4, log_line_count=50)
        assert inc.status == IncidentStatus.DIAGNOSING

        hyp = RCAHypothesis(
            description="pod OOM",
            confidence=ConfidenceScore(0.8),
            supporting_evidence=("mem 100%",),
        )
        inc.record_rca(hypotheses=(hyp,), model="x")

        action = ProposedAction(
            name="restart_pod",
            parameters={"namespace": "ns", "pod_name": "p"},
            rationale="OOM",
            blast_radius=BlastRadius.low("payments-api"),
            confidence=ConfidenceScore(0.8),
            requires_hil=False,
        )
        inc.propose_action(action)
        assert inc.status == IncidentStatus.EXECUTING

        inc.record_execution_result(success=True, output="ok", executed_by="agent")
        assert inc.status == IncidentStatus.VERIFYING

        inc.record_verification(metrics_returned_to_baseline=True, summary="ok")
        inc.resolve(summary="done")
        assert inc.status == IncidentStatus.RESOLVED
        assert inc.resolved_at is not None

        events = inc.drain_events()
        types = [type(e).__name__ for e in events]
        assert "IncidentTriaged" in types
        assert "EvidenceGathered" in types
        assert "RCAGenerated" in types
        assert "ActionProposed" in types
        assert "ActionExecuted" in types
        assert "ActionVerified" in types
        assert "IncidentResolved" in types

    def test_triage_blocked_after_resolution(self) -> None:
        inc = _make_incident()
        inc.triage(
            severity=Severity.P2,
            blast_radius=BlastRadius(level=BlastRadiusLevel.LOW),
            rationale="t",
        )
        with pytest.raises(IncidentStateError):
            inc.triage(
                severity=Severity.P1,
                blast_radius=BlastRadius(level=BlastRadiusLevel.LOW),
                rationale="t",
            )

    def test_rca_without_diagnosis_fails(self) -> None:
        inc = _make_incident()
        with pytest.raises(IncidentStateError):
            inc.record_rca(
                hypotheses=(
                    RCAHypothesis(
                        description="x",
                        confidence=ConfidenceScore(0.5),
                        supporting_evidence=(),
                    ),
                ),
                model="x",
            )

    def test_requires_hil_moves_to_awaiting_approval(self) -> None:
        inc = _make_incident()
        inc.triage(severity=Severity.P2, blast_radius=BlastRadius(level=BlastRadiusLevel.HIGH), rationale="t")
        inc.record_evidence(metric_snapshot_count=1, log_line_count=1)
        inc.record_rca(
            hypotheses=(
                RCAHypothesis(
                    description="x", confidence=ConfidenceScore(0.9), supporting_evidence=()
                ),
            ),
            model="x",
        )
        inc.propose_action(
            ProposedAction(
                name="rollback_deployment",
                parameters={},
                rationale="risky",
                blast_radius=BlastRadius(level=BlastRadiusLevel.HIGH),
                confidence=ConfidenceScore(0.9),
                requires_hil=True,
            )
        )
        assert inc.status == IncidentStatus.AWAITING_APPROVAL

    def test_failed_verification_retries(self) -> None:
        inc = _make_incident()
        inc.triage(severity=Severity.P3, blast_radius=BlastRadius(level=BlastRadiusLevel.LOW), rationale="t")
        inc.record_evidence(metric_snapshot_count=1, log_line_count=1)
        inc.record_rca(
            hypotheses=(RCAHypothesis(description="x", confidence=ConfidenceScore(0.8), supporting_evidence=()),),
            model="x",
        )
        inc.propose_action(
            ProposedAction(
                name="restart_pod",
                parameters={"namespace": "n", "pod_name": "p"},
                rationale="x",
                blast_radius=BlastRadius.low("payments-api"),
                confidence=ConfidenceScore(0.8),
                requires_hil=False,
            )
        )
        inc.record_execution_result(success=True, output="ok", executed_by="a")
        inc.record_verification(metrics_returned_to_baseline=False, summary="still hot")
        assert inc.status == IncidentStatus.DIAGNOSING
