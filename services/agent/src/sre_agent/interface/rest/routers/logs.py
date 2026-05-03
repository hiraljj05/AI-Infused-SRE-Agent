from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from sre_agent.domain.value_objects import ServiceName, TimeWindow
from sre_agent.interface.rest.dependencies import get_container

router = APIRouter(prefix="/api/logs", tags=["logs"])


class LogLineView(BaseModel):
    timestamp: datetime
    level: str
    message: str
    source: str


class LogsResponse(BaseModel):
    service: str | None
    logql: str | None
    minutes: int
    count: int
    lines: list[LogLineView]


@router.get("", response_model=LogsResponse)
async def query_logs(
    service: str | None = Query(default=None, description="Service/app label filter"),
    logql: str | None = Query(default=None, description="Raw LogQL query (overrides service)"),
    minutes: int = Query(default=15, ge=1, le=1440),
    level: str = Query(default="DEBUG", description="Min level: DEBUG/INFO/WARN/ERROR/FATAL"),
    limit: int = Query(default=200, ge=1, le=1000),
    container=Depends(get_container),
) -> LogsResponse:
    end = datetime.now(UTC)
    window = TimeWindow(start=end - timedelta(minutes=minutes), end=end)

    if logql:
        lines = await container.logs.query_logql(logql=logql, window=window, limit=limit)
    elif service:
        # Promtail emits an `app` label per docker-compose service; the Loki adapter
        # expects `app="..."` so this matches transparently.
        lines = await container.logs.query_service(
            service=ServiceName(service), window=window, level_at_least=level, limit=limit
        )
    else:
        lines = await container.logs.query_logql(
            logql='{job="docker"}', window=window, limit=limit
        )

    return LogsResponse(
        service=service,
        logql=logql,
        minutes=minutes,
        count=len(lines),
        lines=[
            LogLineView(
                timestamp=ln.timestamp,
                level=ln.level.value,
                message=ln.message,
                source=ln.source,
            )
            for ln in lines
        ],
    )
