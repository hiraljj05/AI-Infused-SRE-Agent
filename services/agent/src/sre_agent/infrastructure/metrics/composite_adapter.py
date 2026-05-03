from __future__ import annotations

import structlog

from sre_agent.domain.ports.metrics import MetricsPort
from sre_agent.domain.value_objects import (
    MetricSample,
    MetricSnapshot,
    ServiceName,
    TimeWindow,
)

log = structlog.get_logger(__name__)


class CompositeMetricsAdapter(MetricsPort):
    """Queries multiple metric backends in priority order.

    Returns the first non-empty MetricSnapshot. If all backends return empty
    (or fail), returns an empty MetricSnapshot. Backends earlier in the list
    take precedence — typically configure Prometheus first, Azure Monitor as
    fallback.
    """

    def __init__(self, *, backends: list[MetricsPort]) -> None:
        if not backends:
            raise ValueError("CompositeMetricsAdapter requires at least one backend")
        self._backends = backends

    async def close(self) -> None:
        for b in self._backends:
            close = getattr(b, "close", None)
            if callable(close):
                try:
                    await close()
                except Exception:
                    log.exception("composite metrics: backend close failed")

    async def query_service(
        self,
        *,
        service: ServiceName,
        metric: str,
        window: TimeWindow,
        step_seconds: int = 30,
    ) -> MetricSnapshot:
        last: MetricSnapshot = MetricSnapshot(name=metric, samples=())
        for b in self._backends:
            try:
                snap = await b.query_service(
                    service=service, metric=metric, window=window, step_seconds=step_seconds
                )
            except Exception:
                log.exception("composite metrics backend failed", backend=type(b).__name__)
                continue
            if snap.samples:
                return snap
            last = snap
        return last

    async def query_range(
        self,
        *,
        promql: str,
        window: TimeWindow,
        step_seconds: int = 30,
    ) -> MetricSnapshot:
        last: MetricSnapshot = MetricSnapshot(name=promql, samples=())
        for b in self._backends:
            try:
                snap = await b.query_range(promql=promql, window=window, step_seconds=step_seconds)
            except Exception:
                log.exception("composite metrics backend failed", backend=type(b).__name__)
                continue
            if snap.samples:
                return snap
            last = snap
        return last
