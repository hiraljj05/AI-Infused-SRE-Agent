from __future__ import annotations

import pytest

from sre_agent.domain.value_objects import (
    BlastRadius,
    BlastRadiusLevel,
    ConfidenceScore,
    IncidentId,
    PodIdentifier,
    ServiceName,
    Severity,
)


class TestSeverity:
    def test_p1_for_high_scores(self) -> None:
        assert Severity.from_score(user_impact=1.0, blast_radius_weight=1.0, slo_burn=0.8) == Severity.P1

    def test_p4_for_low_scores(self) -> None:
        assert Severity.from_score(user_impact=0.05, blast_radius_weight=0.05, slo_burn=0.01) == Severity.P4

    def test_mttd_targets_ordered(self) -> None:
        assert Severity.P1.mttd_target_seconds < Severity.P2.mttd_target_seconds
        assert Severity.P2.mttd_target_seconds < Severity.P3.mttd_target_seconds

    def test_p1_p2_require_commander(self) -> None:
        assert Severity.P1.requires_incident_commander
        assert Severity.P2.requires_incident_commander
        assert not Severity.P3.requires_incident_commander


class TestConfidenceScore:
    def test_rejects_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            ConfidenceScore(-0.1)
        with pytest.raises(ValueError):
            ConfidenceScore(1.1)

    def test_is_actionable_threshold(self) -> None:
        assert ConfidenceScore(0.70).is_actionable
        assert not ConfidenceScore(0.69).is_actionable

    def test_labels(self) -> None:
        assert ConfidenceScore(0.9).label == "high"
        assert ConfidenceScore(0.7).label == "medium"
        assert ConfidenceScore(0.4).label == "low"
        assert ConfidenceScore(0.1).label == "very-low"


class TestBlastRadius:
    def test_low_is_reversible(self) -> None:
        br = BlastRadius.low("payments-api")
        assert br.level == BlastRadiusLevel.LOW
        assert br.reversible
        assert not br.requires_hil

    def test_critical_requires_hil(self) -> None:
        br = BlastRadius.critical(services=("a", "b"), users=50_000, downtime=300)
        assert br.level == BlastRadiusLevel.CRITICAL
        assert br.requires_hil


class TestIdentifiers:
    def test_incident_id_format(self) -> None:
        i = IncidentId.new()
        assert i.value.startswith("INC-")
        assert len(i.value) > 5

    def test_incident_id_rejects_bad_prefix(self) -> None:
        with pytest.raises(ValueError):
            IncidentId(value="BAD-123")

    def test_service_name_dns_rule(self) -> None:
        ServiceName("payments-api")
        with pytest.raises(ValueError):
            ServiceName("Payments_API")

    def test_pod_identifier_qualified(self) -> None:
        pid = PodIdentifier(namespace="demo-store", name="payments-api-7f9c")
        assert pid.qualified == "demo-store/payments-api-7f9c"
