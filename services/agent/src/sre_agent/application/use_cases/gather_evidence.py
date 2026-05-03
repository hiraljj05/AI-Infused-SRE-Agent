from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from sre_agent.domain.entities.incident import Incident
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.ports.k8s import KubernetesPort, PodInfo
from sre_agent.domain.ports.logs import LogsPort
from sre_agent.domain.ports.metrics import MetricsPort
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import (
    IncidentId,
    LogLine,
    MetricSnapshot,
    ServiceName,
    TimeWindow,
)


@dataclass(slots=True, kw_only=True)
class GatheredEvidence:
    incident: Incident
    metric_snapshots: list[MetricSnapshot] = field(default_factory=list)
    log_lines: list[LogLine] = field(default_factory=list)
    pods: list[PodInfo] = field(default_factory=list)
    recent_deployments: list[str] = field(default_factory=list)


class GatherEvidenceUseCase:
    """Parallel tool calls: metrics + logs + K8s state for the affected service."""

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        metrics: MetricsPort,
        logs: LogsPort,
        k8s: KubernetesPort,
        default_window_minutes: int = 10,
    ) -> None:
        self._uow = uow
        self._metrics = metrics
        self._logs = logs
        self._k8s = k8s
        self._window_minutes = default_window_minutes

    async def execute(self, *, incident_id: IncidentId, namespace: str) -> GatheredEvidence:
        async with self._uow as uow:
            incident = await uow.incidents.get(incident_id)
            if incident is None:
                raise IncidentStateError(f"Incident {incident_id} not found")

            window = TimeWindow.last_minutes(self._window_minutes)
            metric_names = (
                "http_requests_total:error_rate",
                "http_request_duration_seconds:p99",
                "container_cpu_usage_seconds_total:rate",
                "container_memory_working_set_bytes",
            )
            metric_tasks = [
                self._metrics.query_service(
                    service=incident.service, metric=m, window=window
                )
                for m in metric_names
            ]
            # Capture INFO+ so the LLM sees request context, not just warnings.
            # Healthy services may have zero WARN/ERROR but still meaningful traffic.
            log_task = self._logs.query_service(
                service=incident.service, window=window, level_at_least="INFO", limit=200
            )
            pods_task = self._k8s.list_pods(
                namespace=namespace, label_selector=f"app={incident.service}"
            )
            deploys_task = self._k8s.recent_deployments_for(
                service=incident.service, since_seconds=3600
            )

            metrics_r, logs_r, pods_r, deploys_r = await asyncio.gather(
                asyncio.gather(*metric_tasks, return_exceptions=False),
                log_task,
                pods_task,
                deploys_task,
            )

            evidence = GatheredEvidence(
                incident=incident,
                metric_snapshots=list(metrics_r),
                log_lines=logs_r,
                pods=pods_r,
                recent_deployments=[f"{d.name}@rev{d.revision}" for d in deploys_r],
            )

            incident.record_evidence(
                metric_snapshot_count=len(evidence.metric_snapshots),
                log_line_count=len(evidence.log_lines),
                related_deployments=tuple(evidence.recent_deployments),
            )
            await uow.incidents.save(incident)
            await uow.events.append(incident.drain_events())
            await uow.commit()
            return evidence

    @staticmethod
    def summarize_for_llm(evidence: GatheredEvidence) -> str:
        ms = evidence.metric_snapshots
        lines: list[str] = []
        lines.append(f"Service: {evidence.incident.service}")
        lines.append(f"Severity: {evidence.incident.severity}")
        lines.append("")
        lines.append("Metrics:")
        for snap in ms:
            if snap.samples:
                mean, stdev = snap.mean(), snap.stdev()
                latest = snap.latest.value if snap.latest else 0.0
                lines.append(
                    f"  - {snap.name}: latest={latest:.3f} mean={mean:.3f} "
                    f"stdev={stdev:.3f} samples={len(snap.samples)}"
                )
        lines.append("")
        lines.append(f"Pods ({len(evidence.pods)}):")
        for p in evidence.pods[:10]:
            lines.append(
                f"  - {p.identifier} phase={p.phase} ready={p.ready} restarts={p.restart_count}"
            )
        lines.append("")
        lines.append(f"Recent deployments: {evidence.recent_deployments or 'none'}")
        lines.append("")
        lines.append(f"Log lines (showing up to 20 of {len(evidence.log_lines)}):")
        for line in evidence.log_lines[:20]:
            safe = line.message[:240].replace("\n", " ")
            lines.append(f"  - [{line.level.value}] {safe}")
        return "\n".join(lines)


# Re-export for convenience in the agent graph
__all__ = ["GatherEvidenceUseCase", "GatheredEvidence", "ServiceName"]
