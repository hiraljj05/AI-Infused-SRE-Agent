from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from sre_agent.interface.rest.dependencies import get_container

router = APIRouter(prefix="/api/sla", tags=["sla"])


class SLATrackerView(BaseModel):
    id: str
    incident_id: str
    sla_type: str
    severity: str
    started_at: datetime
    due_at: datetime
    status: str
    satisfied_at: datetime | None
    elapsed_pct: float  # 0..1+ where >1 means breached


@router.get("", response_model=list[SLATrackerView])
async def list_sla(
    only_open: bool = Query(default=True),
    container=Depends(get_container),
) -> list[SLATrackerView]:
    from datetime import UTC

    async with container.uow_factory() as uow:
        if only_open:
            items = await uow.slas.list_open()
        else:
            # No global "list all" — derive from open + recently incidents
            items = await uow.slas.list_open()

    now = datetime.now(UTC)
    out: list[SLATrackerView] = []
    for t in items:
        total = (t.due_at - t.started_at).total_seconds() or 1
        elapsed = (now - t.started_at).total_seconds()
        pct = max(0.0, elapsed / total)
        out.append(
            SLATrackerView(
                id=t.id.value,
                incident_id=t.incident_id.value,
                sla_type=t.sla_type.value,
                severity=t.severity.value,
                started_at=t.started_at,
                due_at=t.due_at,
                status=t.status.value,
                satisfied_at=t.satisfied_at,
                elapsed_pct=round(pct, 3),
            )
        )
    return out
