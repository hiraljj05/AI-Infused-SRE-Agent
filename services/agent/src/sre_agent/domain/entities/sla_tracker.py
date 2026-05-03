from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

from sre_agent.domain.value_objects import IncidentId, Severity


class SLAType(str, Enum):
    ACK = "ack"  # acknowledgement deadline
    RCA = "rca"  # root cause analysis deadline
    RESOLVE = "resolve"  # resolution deadline


class SLAStatus(str, Enum):
    PENDING = "pending"
    WARNED = "warned"  # 50% breached
    BREACHED = "breached"
    SATISFIED = "satisfied"


# Per-priority SLAs in seconds (ack, rca, resolve).
SLA_MATRIX: dict[Severity, tuple[int, int, int]] = {
    Severity.P1: (120, 600, 1800),  # P0/P1 critical → tightest
    Severity.P2: (300, 900, 3600),
    Severity.P3: (900, 1800, 14400),
    Severity.P4: (3600, 14400, 86400),
}


@dataclass(frozen=True, slots=True)
class SLATrackerId:
    value: str

    @classmethod
    def new(cls) -> SLATrackerId:
        return cls(value=f"sla_{uuid.uuid4().hex[:12]}")

    def __str__(self) -> str:
        return self.value


@dataclass(slots=True, kw_only=True)
class SLATracker:
    id: SLATrackerId
    incident_id: IncidentId
    sla_type: SLAType
    severity: Severity
    started_at: datetime
    due_at: datetime
    status: SLAStatus = SLAStatus.PENDING
    satisfied_at: datetime | None = None

    @classmethod
    def for_incident(
        cls,
        *,
        incident_id: IncidentId,
        sla_type: SLAType,
        severity: Severity,
        started_at: datetime | None = None,
    ) -> SLATracker:
        now = started_at or datetime.now(UTC)
        ack_s, rca_s, resolve_s = SLA_MATRIX.get(severity, SLA_MATRIX[Severity.P3])
        seconds = {SLAType.ACK: ack_s, SLAType.RCA: rca_s, SLAType.RESOLVE: resolve_s}[sla_type]
        return cls(
            id=SLATrackerId.new(),
            incident_id=incident_id,
            sla_type=sla_type,
            severity=severity,
            started_at=now,
            due_at=now + timedelta(seconds=seconds),
        )

    def satisfy(self) -> None:
        self.status = SLAStatus.SATISFIED
        self.satisfied_at = datetime.now(UTC)

    def evaluate(self, *, now: datetime | None = None) -> SLAStatus:
        """Recompute status from elapsed time. Idempotent."""
        if self.status == SLAStatus.SATISFIED:
            return self.status
        n = now or datetime.now(UTC)
        if n >= self.due_at:
            self.status = SLAStatus.BREACHED
        elif n >= self.started_at + (self.due_at - self.started_at) / 2:
            if self.status == SLAStatus.PENDING:
                self.status = SLAStatus.WARNED
        return self.status

    @property
    def percent_elapsed(self) -> float:
        total = (self.due_at - self.started_at).total_seconds()
        if total <= 0:
            return 100.0
        elapsed = (datetime.now(UTC) - self.started_at).total_seconds()
        return min(100.0, max(0.0, 100.0 * elapsed / total))
