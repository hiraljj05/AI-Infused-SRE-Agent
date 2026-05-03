from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sre_agent.domain.ports.metrics import MetricsPort
from sre_agent.domain.value_objects import (
    MetricSample,
    MetricSnapshot,
    ServiceName,
    TimeWindow,
)


# Canonical metric -> Azure Monitor KQL template (Log Analytics).
# Templates use $service for substitution.
KQL_TEMPLATES: dict[str, str] = {
    "http_requests_total:error_rate": (
        "AppRequests "
        "| where AppRoleName == '$service' "
        "| summarize errors = countif(toint(ResultCode) >= 500), total = count() "
        "  by bin(TimeGenerated, $step) "
        "| extend value = todouble(errors) / todouble(iff(total == 0, 1, total)) "
        "| project TimeGenerated, value | order by TimeGenerated asc"
    ),
    "http_request_duration_seconds:p99": (
        "AppRequests "
        "| where AppRoleName == '$service' "
        "| summarize value = percentile(DurationMs, 99) "
        "  by bin(TimeGenerated, $step) "
        "| project TimeGenerated, value | order by TimeGenerated asc"
    ),
}


class AzureMonitorMetricsAdapter(MetricsPort):
    """MetricsPort implementation backed by Azure Monitor Log Analytics (KQL).

    Lazily imports the `azure-monitor-query` SDK + `azure-identity` so the
    adapter is only constructed when a workspace_id is configured. If the
    deps are not installed, construction raises a clear ImportError.
    """

    def __init__(
        self,
        *,
        workspace_id: str,
        credential: Any | None = None,
    ) -> None:
        try:
            from azure.identity.aio import DefaultAzureCredential
            from azure.monitor.query.aio import LogsQueryClient
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "azure-monitor-query and azure-identity are required for "
                "AzureMonitorMetricsAdapter. Install with "
                "`pip install azure-monitor-query azure-identity`."
            ) from exc

        self._workspace_id = workspace_id
        self._credential = credential or DefaultAzureCredential()
        self._client = LogsQueryClient(self._credential)

    async def close(self) -> None:
        try:
            await self._client.close()
        finally:
            close = getattr(self._credential, "close", None)
            if callable(close):
                await close()

    async def query_service(
        self,
        *,
        service: ServiceName,
        metric: str,
        window: TimeWindow,
        step_seconds: int = 30,
    ) -> MetricSnapshot:
        template = KQL_TEMPLATES.get(metric)
        if template is None:
            raise ValueError(
                f"Azure Monitor adapter has no KQL for metric {metric!r}. "
                "Add it to KQL_TEMPLATES or call query_range directly."
            )
        kql = template.replace("$service", str(service)).replace(
            "$step", f"{step_seconds}s"
        )
        return await self._run_kql(kql, window)

    async def query_range(
        self,
        *,
        promql: str,
        window: TimeWindow,
        step_seconds: int = 30,
    ) -> MetricSnapshot:
        """Treats `promql` as a KQL query string for cross-tool API compat."""
        return await self._run_kql(promql, window)

    async def _run_kql(self, kql: str, window: TimeWindow) -> MetricSnapshot:
        from azure.monitor.query import LogsQueryStatus

        try:
            response = await self._client.query_workspace(
                workspace_id=self._workspace_id,
                query=kql,
                timespan=(window.start, window.end),
            )
        except Exception:
            return MetricSnapshot(name=kql, samples=())

        if response.status == LogsQueryStatus.FAILURE:
            return MetricSnapshot(name=kql, samples=())

        tables = getattr(response, "tables", None) or []
        if not tables:
            return MetricSnapshot(name=kql, samples=())

        table = tables[0]
        # Find timestamp + value columns by name (we project them in KQL templates).
        col_names = [c.name if hasattr(c, "name") else c for c in table.columns]
        try:
            ts_idx = col_names.index("TimeGenerated")
            val_idx = col_names.index("value")
        except ValueError:
            return MetricSnapshot(name=kql, samples=())

        samples: list[MetricSample] = []
        for row in table.rows:
            try:
                ts = row[ts_idx]
                val = float(row[val_idx])
            except (TypeError, ValueError, IndexError):
                continue
            when = ts if isinstance(ts, datetime) else datetime.now(UTC)
            samples.append(MetricSample(timestamp=when, value=val, labels=()))
        return MetricSnapshot(name=kql, samples=tuple(samples))
