from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sre_agent.domain.entities.incident import Incident
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.ports.metrics import MetricsPort
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import IncidentId, TimeWindow


@dataclass(frozen=True, slots=True, kw_only=True)
class VerifyResolutionInput:
    incident_id: IncidentId
    wait_seconds: int = 60
    metrics_to_check: tuple[str, ...] = (
        "http_requests_total:error_rate",
        "http_request_duration_seconds:p99",
    )


class VerifyResolutionUseCase:
    def __init__(self, *, uow: UnitOfWork, metrics: MetricsPort) -> None:
        self._uow = uow
        self._metrics = metrics

    async def execute(self, input_: VerifyResolutionInput) -> Incident:
        async with self._uow as uow:
            incident = await uow.incidents.get(input_.incident_id)
            if incident is None:
                raise IncidentStateError(f"Incident {input_.incident_id} not found")

        await asyncio.sleep(input_.wait_seconds)

        window = TimeWindow.last_minutes(5)
        snapshots = await asyncio.gather(
            *[
                self._metrics.query_service(
                    service=incident.service, metric=m, window=window
                )
                for m in input_.metrics_to_check
            ]
        )
        anomalous = [s for s in snapshots if s.is_anomalous(threshold_zscore=3.0)]
        to_baseline = len(anomalous) == 0
        summary = (
            f"checked {len(snapshots)} metrics, {len(anomalous)} still anomalous"
            if snapshots
            else "no metrics available for verification"
        )

        async with self._uow as uow:
            incident = await uow.incidents.get(input_.incident_id)
            if incident is None:
                raise IncidentStateError("Incident not found during verification write-back")
            incident.record_verification(
                metrics_returned_to_baseline=to_baseline, summary=summary
            )
            if to_baseline:
                incident.resolve(summary=f"Auto-verified after remediation: {summary}")
            await uow.incidents.save(incident)
            await uow.events.append(incident.drain_events())
            await uow.commit()
            return incident
