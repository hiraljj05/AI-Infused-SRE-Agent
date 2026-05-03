from __future__ import annotations

from dataclasses import dataclass

from sre_agent.domain.entities.incident import Incident
from sre_agent.domain.entities.service import ServiceTier
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.ports.knowledge import ServiceCatalogPort
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import (
    BlastRadius,
    BlastRadiusLevel,
    IncidentId,
    Severity,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class TriageInput:
    incident_id: IncidentId
    observed_error_rate: float
    observed_latency_p99_ms: float
    estimated_users_affected: int


class TriageIncidentUseCase:
    def __init__(self, uow: UnitOfWork, service_catalog: ServiceCatalogPort) -> None:
        self._uow = uow
        self._catalog = service_catalog

    async def execute(self, command: TriageInput) -> Incident:
        async with self._uow as uow:
            incident = await uow.incidents.get(command.incident_id)
            if incident is None:
                raise IncidentStateError(f"Incident {command.incident_id} not found")

            service = await self._catalog.get(incident.service)

            tier_weight = service.tier.criticality_weight if service else ServiceTier.TIER_2.criticality_weight
            deps = service.dependencies if service else ()

            user_impact = min(1.0, command.observed_error_rate)
            blast_weight = min(1.0, 0.3 + 0.1 * len(deps))
            slo_burn = min(1.0, command.observed_latency_p99_ms / 2000.0)

            severity = Severity.from_score(
                user_impact=user_impact * tier_weight,
                blast_radius_weight=blast_weight,
                slo_burn=slo_burn,
            )

            level = self._blast_level(severity, command.estimated_users_affected, bool(deps))
            blast_radius = BlastRadius(
                level=level,
                affected_services=(str(incident.service),) + tuple(str(d) for d in deps),
                estimated_users_affected=command.estimated_users_affected,
                estimated_downtime_seconds=0,
                reversible=True,
            )

            rationale = (
                f"tier={tier_weight:.2f} errors={user_impact:.2f} "
                f"deps={len(deps)} latency_score={slo_burn:.2f} -> {severity.value}"
            )

            incident.triage(severity=severity, blast_radius=blast_radius, rationale=rationale)
            await uow.incidents.save(incident)
            await uow.events.append(incident.drain_events())
            await uow.commit()
            return incident

    @staticmethod
    def _blast_level(severity: Severity, users: int, has_deps: bool) -> BlastRadiusLevel:
        if severity == Severity.P1 or users > 10_000:
            return BlastRadiusLevel.CRITICAL
        if severity == Severity.P2 or has_deps:
            return BlastRadiusLevel.HIGH
        if severity == Severity.P3:
            return BlastRadiusLevel.MEDIUM
        return BlastRadiusLevel.LOW
