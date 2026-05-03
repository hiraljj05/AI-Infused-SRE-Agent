from __future__ import annotations

from typing import Protocol

from sre_agent.domain.value_objects import MetricSnapshot, ServiceName, TimeWindow


class MetricsPort(Protocol):
    async def query_service(
        self,
        *,
        service: ServiceName,
        metric: str,
        window: TimeWindow,
        step_seconds: int = 30,
    ) -> MetricSnapshot:
        ...

    async def query_range(
        self,
        *,
        promql: str,
        window: TimeWindow,
        step_seconds: int = 30,
    ) -> MetricSnapshot:
        ...
