from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sre_agent.domain.entities.sla_tracker import (
    SLAStatus,
    SLATracker,
    SLATrackerId,
    SLAType,
)
from sre_agent.domain.ports.sla import SLATrackerRepository
from sre_agent.domain.value_objects import IncidentId, Severity
from sre_agent.infrastructure.persistence.models.orm import SLATrackerModel


def _to_model(t: SLATracker) -> SLATrackerModel:
    return SLATrackerModel(
        id=t.id.value,
        incident_id=t.incident_id.value,
        sla_type=t.sla_type.value,
        severity=t.severity.value,
        started_at=t.started_at,
        due_at=t.due_at,
        status=t.status.value,
        satisfied_at=t.satisfied_at,
    )


def _from_model(m: SLATrackerModel) -> SLATracker:
    return SLATracker(
        id=SLATrackerId(value=m.id),
        incident_id=IncidentId(value=m.incident_id),
        sla_type=SLAType(m.sla_type),
        severity=Severity(m.severity),
        started_at=m.started_at,
        due_at=m.due_at,
        status=SLAStatus(m.status),
        satisfied_at=m.satisfied_at,
    )


def _apply(t: SLATracker, m: SLATrackerModel) -> None:
    m.status = t.status.value
    m.satisfied_at = t.satisfied_at
    m.due_at = t.due_at
    m.severity = t.severity.value


class SqlAlchemySLATrackerRepository(SLATrackerRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, tracker: SLATracker) -> None:
        self._s.add(_to_model(tracker))

    async def get(self, tracker_id: SLATrackerId) -> SLATracker | None:
        m = await self._s.get(SLATrackerModel, tracker_id.value)
        return _from_model(m) if m else None

    async def save(self, tracker: SLATracker) -> None:
        m = await self._s.get(SLATrackerModel, tracker.id.value)
        if m is None:
            self._s.add(_to_model(tracker))
        else:
            _apply(tracker, m)

    async def list_for_incident(self, incident_id: IncidentId) -> list[SLATracker]:
        stmt = (
            select(SLATrackerModel)
            .where(SLATrackerModel.incident_id == incident_id.value)
            .order_by(SLATrackerModel.due_at)
        )
        result = await self._s.execute(stmt)
        return [_from_model(m) for m in result.scalars().all()]

    async def get_for_incident_and_type(
        self, incident_id: IncidentId, sla_type: SLAType
    ) -> SLATracker | None:
        stmt = (
            select(SLATrackerModel)
            .where(
                SLATrackerModel.incident_id == incident_id.value,
                SLATrackerModel.sla_type == sla_type.value,
            )
            .limit(1)
        )
        result = await self._s.execute(stmt)
        m = result.scalar_one_or_none()
        return _from_model(m) if m else None

    async def list_open(self) -> list[SLATracker]:
        open_states = [SLAStatus.PENDING.value, SLAStatus.WARNED.value, SLAStatus.BREACHED.value]
        stmt = select(SLATrackerModel).where(SLATrackerModel.status.in_(open_states))
        result = await self._s.execute(stmt)
        return [_from_model(m) for m in result.scalars().all()]
