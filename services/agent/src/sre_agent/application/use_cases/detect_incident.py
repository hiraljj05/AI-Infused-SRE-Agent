from __future__ import annotations

from dataclasses import dataclass

from sre_agent.domain.entities.incident import Incident
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import ServiceName


@dataclass(frozen=True, slots=True, kw_only=True)
class DetectIncidentCommand:
    service: ServiceName
    initial_signal: str
    signal_sources: tuple[str, ...]


class DetectIncidentUseCase:
    """Deduplicates signals against any active incident for the service; creates a new one if none exists."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: DetectIncidentCommand) -> Incident:
        async with self._uow as uow:
            existing = await uow.incidents.find_active_for_service(command.service)
            if existing is not None:
                return existing

            incident = Incident.detect(
                service=command.service,
                initial_signal=command.initial_signal,
                signal_sources=command.signal_sources,
            )
            await uow.incidents.add(incident)
            await uow.events.append(incident.drain_events())
            await uow.commit()
            return incident
