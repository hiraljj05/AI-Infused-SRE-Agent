from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, select

from sre_agent.infrastructure.persistence.models.orm import EventModel
from sre_agent.interface.rest.dependencies import get_container

router = APIRouter(prefix="/api/events", tags=["events"])


class EventView(BaseModel):
    event_id: str
    incident_id: str
    event_type: str
    occurred_at: datetime
    caused_by: str
    payload: dict[str, Any]


@router.get("", response_model=list[EventView])
async def list_events(
    incident_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    container=Depends(get_container),
) -> list[EventView]:
    """Recent domain events. Pass `incident_id` to scope; otherwise returns global stream."""
    async with container.uow_factory() as uow:
        session = uow._session  # type: ignore[attr-defined]
        stmt = select(EventModel).order_by(desc(EventModel.occurred_at)).limit(limit)
        if incident_id:
            stmt = stmt.where(EventModel.incident_id == incident_id)
        result = await session.execute(stmt)
        rows = result.scalars().all()

    return [
        EventView(
            event_id=str(r.event_id),
            incident_id=r.incident_id,
            event_type=r.event_type,
            occurred_at=r.occurred_at,
            caused_by=r.caused_by,
            payload=r.payload or {},
        )
        for r in rows
    ]
