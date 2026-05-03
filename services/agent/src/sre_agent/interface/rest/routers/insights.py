from __future__ import annotations

import asyncio
import os
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from sre_agent.domain.value_objects import ServiceName
from sre_agent.interface.rest.dependencies import get_container

router = APIRouter(prefix="/api/insights", tags=["insights"])


class InsightView(BaseModel):
    severity: str
    headline: str
    evidence: str


class InsightSummary(BaseModel):
    service: str
    window_minutes: int
    line_count: int
    error_count: int
    warn_count: int
    insights: list[InsightView]
    generated_at: datetime
    model: str


class InsightsListResponse(BaseModel):
    services: list[InsightSummary]


def _to_view(r) -> InsightSummary:
    return InsightSummary(
        service=r.service,
        window_minutes=r.window_minutes,
        line_count=r.line_count,
        error_count=r.error_count,
        warn_count=r.warn_count,
        insights=[
            InsightView(severity=i.severity, headline=i.headline, evidence=i.evidence)
            for i in r.insights
        ],
        generated_at=r.generated_at,
        model=r.model,
    )


@router.get("", response_model=InsightsListResponse)
async def list_insights(container=Depends(get_container)) -> InsightsListResponse:
    """Returns the cached log insights for every monitored service."""
    cache = container.insights_monitor.cache
    return InsightsListResponse(
        services=sorted(
            (_to_view(r) for r in cache.values()),
            key=_severity_sort_key,
            reverse=True,
        )
    )


def _severity_sort_key(s: InsightSummary) -> tuple[int, int]:
    sev_rank = {"critical": 3, "warn": 2, "info": 1}
    top = max((sev_rank.get(i.severity, 0) for i in s.insights), default=0)
    return (top, s.error_count)


@router.get("/{service}", response_model=InsightSummary)
async def insight_for_service(
    service: str,
    refresh: bool = Query(default=False),
    container=Depends(get_container),
) -> InsightSummary:
    """Get cached insights for a service. Pass ?refresh=true to force a fresh LLM call."""
    cache = container.insights_monitor.cache
    if refresh or service not in cache:
        result = await container.insights_uc.execute(
            service=ServiceName(service), minutes=15
        )
        cache[service] = result
    return _to_view(cache[service])


@router.get("/embed/{service}/grafana-url")
async def grafana_embed_url(service: str, container=Depends(get_container)) -> dict:
    """Returns a Grafana panel iframe URL for the service.

    Tries to use the per-app provisioned dashboard if known, else falls back to
    Grafana Explore for the service. Uses the GRAFANA_URL setting (default: http://localhost:3001).
    """
    grafana_base = container.settings.grafana_url.rstrip("/")
    # If we're running in docker the agent sees http://grafana:3000 — that's not browser-reachable.
    # Translate to the host-published port.
    public_base = os.environ.get("GRAFANA_PUBLIC_URL", "http://localhost:3001")
    async with container.uow_factory() as uow:
        app = await uow.apps.get_by_name(ServiceName(service))
    uid = app.grafana_dashboard_uid if app else None
    if uid:
        url = f"{public_base}/d/{uid}?theme=light&kiosk&refresh=10s"
    else:
        # Loki Explore for the service
        from urllib.parse import quote

        loki_query = f'{{app="{service}"}}'
        params = (
            "left="
            + quote(
                '{"datasource":"loki","queries":[{"refId":"A","datasource":"loki","expr":"'
                + loki_query
                + '"}],"range":{"from":"now-1h","to":"now"}}'
            )
        )
        url = f"{public_base}/explore?{params}&theme=light"
    return {"service": service, "url": url, "kind": "dashboard" if uid else "explore"}


@router.post("/refresh")
async def refresh_all(container=Depends(get_container)) -> dict:
    """Force-refresh insights for every app right now."""
    async with container.uow_factory() as uow:
        apps = await uow.apps.list_all()
    services = sorted({str(a.name) for a in apps} | {"agent"})
    results = await asyncio.gather(
        *[container.insights_uc.execute(service=ServiceName(s)) for s in services],
        return_exceptions=True,
    )
    refreshed = 0
    for s, r in zip(services, results):
        if not isinstance(r, Exception):
            container.insights_monitor.cache[s] = r
            refreshed += 1
    return {"refreshed": refreshed, "services": services}
