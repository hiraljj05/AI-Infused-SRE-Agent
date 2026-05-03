from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from sre_agent.domain.ports.metrics import MetricsPort
from sre_agent.domain.value_objects import (
    MetricSample,
    MetricSnapshot,
    ServiceName,
    TimeWindow,
)


# Canonical metric name -> Prometheus query template.
# Uses `$service` for substitution.
METRIC_TEMPLATES: dict[str, str] = {
    "http_requests_total:error_rate": (
        'sum(rate(http_requests_total{service="$service",code=~"5.."}[2m])) '
        '/ clamp_min(sum(rate(http_requests_total{service="$service"}[2m])), 1)'
    ),
    "http_request_duration_seconds:p99": (
        'histogram_quantile(0.99, '
        'sum by (le) (rate(http_request_duration_seconds_bucket{service="$service"}[2m]))) * 1000'
    ),
    "container_cpu_usage_seconds_total:rate": (
        'sum(rate(container_cpu_usage_seconds_total{pod=~"$service-.*"}[2m]))'
    ),
    "container_memory_working_set_bytes": (
        'sum(container_memory_working_set_bytes{pod=~"$service-.*"})'
    ),
}


class PrometheusMetricsAdapter(MetricsPort):
    def __init__(self, *, url: str, timeout_seconds: float = 10.0) -> None:
        self._url = url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def close(self) -> None:
        await self._client.aclose()

    async def query_service(
        self,
        *,
        service: ServiceName,
        metric: str,
        window: TimeWindow,
        step_seconds: int = 30,
    ) -> MetricSnapshot:
        template = METRIC_TEMPLATES.get(metric)
        if template is None:
            raise ValueError(f"Unknown canonical metric {metric!r}")
        promql = template.replace("$service", str(service))
        return await self.query_range(promql=promql, window=window, step_seconds=step_seconds)

    async def query_range(
        self,
        *,
        promql: str,
        window: TimeWindow,
        step_seconds: int = 30,
    ) -> MetricSnapshot:
        params = {
            "query": promql,
            "start": window.start.timestamp(),
            "end": window.end.timestamp(),
            "step": str(step_seconds),
        }
        response = await self._client.get(f"{self._url}/api/v1/query_range", params=params)
        response.raise_for_status()
        body = response.json()
        samples = self._extract_samples(body)
        return MetricSnapshot(name=promql, samples=tuple(samples))

    @staticmethod
    def _extract_samples(body: dict[str, Any]) -> list[MetricSample]:
        result = body.get("data", {}).get("result", [])
        if not result:
            return []
        series = result[0]
        labels = tuple(sorted(series.get("metric", {}).items()))
        samples: list[MetricSample] = []
        for ts, value in series.get("values", []):
            try:
                samples.append(
                    MetricSample(
                        timestamp=datetime.fromtimestamp(float(ts), tz=UTC),
                        value=float(value),
                        labels=labels,
                    )
                )
            except (TypeError, ValueError):
                continue
        return samples
