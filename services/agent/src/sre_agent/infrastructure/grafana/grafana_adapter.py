from __future__ import annotations

import base64
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)


class GrafanaAdapter:
    """Talks to Grafana's HTTP API.

    Auth: either an API key (`api_key`) or basic auth (`username`+`password`).
    For local dev with anonymous viewer enabled, basic auth (admin/admin) works.
    """

    def __init__(
        self,
        *,
        url: str,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._url = url.rstrip("/")
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        elif username and password:
            token = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"
        self._client = httpx.AsyncClient(headers=headers, timeout=timeout_seconds)

    async def close(self) -> None:
        await self._client.aclose()

    async def list_dashboards(self) -> list[dict[str, Any]]:
        r = await self._client.get(f"{self._url}/api/search?type=dash-db")
        r.raise_for_status()
        return r.json()

    async def get_dashboard(self, uid: str) -> dict[str, Any]:
        r = await self._client.get(f"{self._url}/api/dashboards/uid/{uid}")
        r.raise_for_status()
        return r.json()

    async def upsert_dashboard(self, dashboard: dict[str, Any], folder_uid: str | None = None) -> str:
        body: dict[str, Any] = {"dashboard": dashboard, "overwrite": True}
        if folder_uid:
            body["folderUid"] = folder_uid
        r = await self._client.post(f"{self._url}/api/dashboards/db", json=body)
        r.raise_for_status()
        data = r.json()
        log.info("grafana dashboard upserted", uid=data.get("uid"), url=data.get("url"))
        return data["uid"]

    async def list_alert_rules(self) -> list[dict[str, Any]]:
        r = await self._client.get(f"{self._url}/api/v1/provisioning/alert-rules")
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json()

    async def delete_dashboard(self, uid: str) -> bool:
        r = await self._client.delete(f"{self._url}/api/dashboards/uid/{uid}")
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return True


def build_app_dashboard_template(*, app_name: str, namespace: str) -> dict[str, Any]:
    """Generates a starter Grafana dashboard for a registered app.

    Panels: up, request rate, p99 latency, error rate, app errors, process CPU,
    process memory, plus a live Loki logs panel scoped to the service.

    The metric queries match what the Flask demo apps expose via prometheus_client:
      - up{instance=~".*<svc>:.*"}
      - http_requests_total{service="<svc>", code="..."}
      - http_request_duration_seconds_bucket{service="<svc>"}
      - app_errors_total{service="<svc>", kind="..."}
      - process_resident_memory_bytes / process_cpu_seconds_total (Prometheus default)
    Loki labels match Promtail's docker_sd config (`app=<compose service>`).
    """
    return {
        "uid": f"app-{app_name}",
        "title": f"App: {app_name}",
        "tags": ["sre-agent", "app", app_name],
        "timezone": "browser",
        "schemaVersion": 38,
        "version": 1,
        "refresh": "30s",
        "time": {"from": "now-30m", "to": "now"},
        "panels": [
            # Row 1 — Up + request rate
            {
                "type": "stat",
                "title": "Up",
                "gridPos": {"h": 4, "w": 4, "x": 0, "y": 0},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {"expr": f'max(up{{instance=~"{app_name}:.*"}})', "refId": "A"}
                ],
                "fieldConfig": {
                    "defaults": {
                        "mappings": [
                            {
                                "type": "value",
                                "options": {
                                    "0": {"text": "DOWN", "color": "red"},
                                    "1": {"text": "UP", "color": "green"},
                                },
                            }
                        ]
                    }
                },
            },
            {
                "type": "stat",
                "title": "Total requests (5m)",
                "gridPos": {"h": 4, "w": 4, "x": 4, "y": 0},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {
                        "expr": f'sum(increase(http_requests_total{{service="{app_name}"}}[5m]))',
                        "refId": "A",
                    }
                ],
                "fieldConfig": {"defaults": {"decimals": 0}},
            },
            {
                "type": "timeseries",
                "title": "Request rate by status code (req/sec)",
                "gridPos": {"h": 8, "w": 16, "x": 8, "y": 0},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {
                        "expr": f'sum by (code) (rate(http_requests_total{{service="{app_name}"}}[2m]))',
                        "legendFormat": "{{code}}",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {"defaults": {"unit": "reqps"}},
            },
            # Row 2 — latency + error rate
            {
                "type": "timeseries",
                "title": "P99 / P50 latency (ms)",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {
                        "expr": (
                            "histogram_quantile(0.99, "
                            f"sum by (le) (rate(http_request_duration_seconds_bucket{{service=\"{app_name}\"}}[2m]))) * 1000"
                        ),
                        "legendFormat": "p99",
                        "refId": "A",
                    },
                    {
                        "expr": (
                            "histogram_quantile(0.50, "
                            f"sum by (le) (rate(http_request_duration_seconds_bucket{{service=\"{app_name}\"}}[2m]))) * 1000"
                        ),
                        "legendFormat": "p50",
                        "refId": "B",
                    },
                ],
                "fieldConfig": {"defaults": {"unit": "ms"}},
            },
            {
                "type": "timeseries",
                "title": "5xx error rate (%) + app errors",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {
                        "expr": (
                            f'sum(rate(http_requests_total{{service="{app_name}",code=~"5.."}}[2m])) '
                            f'/ clamp_min(sum(rate(http_requests_total{{service="{app_name}"}}[2m])), 1) * 100'
                        ),
                        "legendFormat": "5xx %",
                        "refId": "A",
                    },
                    {
                        "expr": f'sum by (kind) (rate(app_errors_total{{service="{app_name}"}}[2m]))',
                        "legendFormat": "{{kind}}",
                        "refId": "B",
                    },
                ],
                "fieldConfig": {"defaults": {"unit": "short"}},
            },
            # Row 3 — process CPU + memory
            {
                "type": "timeseries",
                "title": "Process CPU (cores)",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {
                        "expr": f'rate(process_cpu_seconds_total{{instance=~"{app_name}:.*"}}[2m])',
                        "legendFormat": "cpu cores",
                        "refId": "A",
                    }
                ],
            },
            {
                "type": "timeseries",
                "title": "Process memory (RSS)",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {
                        "expr": f'process_resident_memory_bytes{{instance=~"{app_name}:.*"}}',
                        "legendFormat": "rss",
                        "refId": "A",
                    }
                ],
                "fieldConfig": {"defaults": {"unit": "decbytes"}},
            },
            # Row 4 — Loki logs panel scoped to this service
            {
                "type": "logs",
                "title": "Live logs (Loki)",
                "gridPos": {"h": 12, "w": 24, "x": 0, "y": 24},
                "datasource": {"type": "loki", "uid": "loki"},
                "targets": [
                    {
                        "expr": f'{{app="{app_name}"}}',
                        "refId": "A",
                    }
                ],
                "options": {
                    "showTime": True,
                    "showLabels": False,
                    "showCommonLabels": False,
                    "wrapLogMessage": True,
                    "sortOrder": "Descending",
                    "dedupStrategy": "none",
                    "enableLogDetails": True,
                },
            },
        ],
    }
