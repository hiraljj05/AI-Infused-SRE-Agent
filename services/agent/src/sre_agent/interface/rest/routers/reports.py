from __future__ import annotations

import csv
import dataclasses
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sre_agent.application.use_cases.generate_weekly_digest import (
    GenerateWeeklyDigestUseCase,
)
from sre_agent.interface.rest.dependencies import get_container

router = APIRouter(prefix="/api/reports", tags=["reports"])


class WeeklyDigestView(BaseModel):
    period_start: datetime
    period_end: datetime
    total_incidents: int
    new_incidents: int
    resolved_incidents: int
    by_severity: dict[str, int]
    by_service: list[tuple[str, int]]
    avg_mttr_minutes: float
    agent_resolutions: int
    human_resolutions: int
    agent_share_pct: int
    top_categories: list[tuple[str, int]]
    open_breached_slas: int
    summary_markdown: str


@router.get("/weekly", response_model=WeeklyDigestView)
async def weekly_digest(
    days: int = Query(default=7, ge=1, le=90),
    container=Depends(get_container),
) -> WeeklyDigestView:
    uc = GenerateWeeklyDigestUseCase(uow=container.uow_factory())
    digest = await uc.execute(days=days)
    return WeeklyDigestView(**dataclasses.asdict(digest))


@router.get("/incidents.csv")
async def incidents_csv(container=Depends(get_container)) -> StreamingResponse:
    """Export every incident as CSV (full-history, not date-filtered)."""
    async with container.uow_factory() as uow:
        from sre_agent.domain.entities.incident import IncidentStatus

        all_incidents: list = []
        for status in IncidentStatus:
            items = await uow.incidents.list_by_status(status)
            all_incidents.extend(items)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "service",
            "status",
            "severity",
            "initial_signal",
            "detected_at",
            "resolved_at",
            "top_rca",
            "proposed_action",
        ]
    )
    for i in all_incidents:
        top_rca = i.rca_hypotheses[0].description if i.rca_hypotheses else ""
        action = i.proposed_action.name if i.proposed_action else ""
        writer.writerow(
            [
                i.id.value,
                str(i.service),
                i.status.value,
                i.severity.value if i.severity else "",
                i.initial_signal,
                i.detected_at.isoformat(),
                i.resolved_at.isoformat() if i.resolved_at else "",
                top_rca,
                action,
            ]
        )

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=incidents.csv"},
    )
