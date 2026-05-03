from __future__ import annotations

from dataclasses import dataclass

from sre_agent.domain.entities.sla_tracker import SLATracker, SLAType
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import IncidentId


@dataclass(frozen=True, slots=True, kw_only=True)
class StartSLATrackersCommand:
    incident_id: IncidentId


class StartSLATrackersUseCase:
    """Creates ack/RCA/resolve trackers for an incident based on its severity.

    Idempotent: if a tracker for this (incident, sla_type) already exists, skip.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, cmd: StartSLATrackersCommand) -> list[SLATracker]:
        async with self._uow as uow:
            incident = await uow.incidents.get(cmd.incident_id)
            if incident is None:
                raise IncidentStateError(f"Incident {cmd.incident_id} not found")
            if incident.severity is None:
                # Cannot create SLAs without severity (must be triaged first)
                return []

            created: list[SLATracker] = []
            for sla_type in (SLAType.ACK, SLAType.RCA, SLAType.RESOLVE):
                existing = await uow.slas.get_for_incident_and_type(
                    cmd.incident_id, sla_type
                )
                if existing is not None:
                    continue
                t = SLATracker.for_incident(
                    incident_id=cmd.incident_id,
                    sla_type=sla_type,
                    severity=incident.severity,
                )
                await uow.slas.add(t)
                created.append(t)
            await uow.commit()
            return created


class SatisfySLAUseCase:
    """Marks a specific SLA tracker as satisfied (fired by the relevant domain event)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, incident_id: IncidentId, sla_type: SLAType) -> bool:
        async with self._uow as uow:
            t = await uow.slas.get_for_incident_and_type(incident_id, sla_type)
            if t is None:
                return False
            if t.satisfied_at is not None:
                return True
            t.satisfy()
            await uow.slas.save(t)
            await uow.commit()
            return True
