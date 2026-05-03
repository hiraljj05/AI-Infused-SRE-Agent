from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sre_agent.domain.entities.postmortem import Postmortem
from sre_agent.domain.value_objects import IncidentId
from sre_agent.interface.rest.dependencies import get_container

router = APIRouter(prefix="/postmortems", tags=["postmortems"])


class TimelineEntryView(BaseModel):
    at: datetime
    event: str


class CorrectiveActionView(BaseModel):
    description: str
    owner: str
    due_date: datetime | None = None
    jira_ticket: str | None = None


class PostmortemView(BaseModel):
    id: str
    incident_id: str
    title: str
    summary: str
    root_cause: str
    impact: str
    lessons_learned: str
    timeline: list[TimelineEntryView]
    corrective_actions: list[CorrectiveActionView]
    drafted_at: datetime
    published_at: datetime | None
    signed_off_by: str | None
    word_count: int
    is_published: bool
    # convenience fields enriched from the linked incident, when available
    service: str | None = None
    severity: str | None = None
    initial_signal: str | None = None
    detected_at: datetime | None = None
    resolved_at: datetime | None = None

    @classmethod
    def from_domain(
        cls, pm: Postmortem, *, incident: Any | None = None
    ) -> "PostmortemView":
        return cls(
            id=pm.id,
            incident_id=pm.incident_id.value,
            title=pm.title,
            summary=pm.summary,
            root_cause=pm.root_cause,
            impact=pm.impact,
            lessons_learned=pm.lessons_learned,
            timeline=[TimelineEntryView(at=t.at, event=t.event) for t in pm.timeline],
            corrective_actions=[
                CorrectiveActionView(
                    description=a.description,
                    owner=a.owner,
                    due_date=a.due_date,
                    jira_ticket=a.jira_ticket,
                )
                for a in pm.corrective_actions
            ],
            drafted_at=pm.drafted_at,
            published_at=pm.published_at,
            signed_off_by=pm.signed_off_by,
            word_count=pm.word_count,
            is_published=pm.is_published,
            service=str(incident.service) if incident else None,
            severity=(incident.severity.value if incident and incident.severity else None),
            initial_signal=incident.initial_signal if incident else None,
            detected_at=incident.detected_at if incident else None,
            resolved_at=incident.resolved_at if incident else None,
        )


@router.get("", response_model=list[PostmortemView])
async def list_postmortems(
    limit: int = 100,
    container=Depends(get_container),
) -> list[PostmortemView]:
    """All postmortems with full content (most recent first), enriched with the
    parent incident's service / severity / signal so the dashboard can render
    rich postmortem cards without a second round-trip per postmortem."""
    async with container.uow_factory() as uow:
        postmortems = await uow.postmortems.list_recent(limit=limit)
        out: list[PostmortemView] = []
        for pm in postmortems:
            incident = await uow.incidents.get(pm.incident_id)
            out.append(PostmortemView.from_domain(pm, incident=incident))
        return out


@router.get("/by-incident/{incident_id}", response_model=PostmortemView)
async def get_postmortem_for_incident(
    incident_id: str,
    container=Depends(get_container),
) -> PostmortemView:
    iid = IncidentId(value=incident_id)
    async with container.uow_factory() as uow:
        pm = await uow.postmortems.get_for_incident(iid)
        if pm is None:
            raise HTTPException(404, f"no postmortem for incident {incident_id}")
        incident = await uow.incidents.get(iid)
    return PostmortemView.from_domain(pm, incident=incident)


@router.get("/{postmortem_id}", response_model=PostmortemView)
async def get_postmortem(
    postmortem_id: str,
    container=Depends(get_container),
) -> PostmortemView:
    async with container.uow_factory() as uow:
        pm = await uow.postmortems.get(postmortem_id)
        if pm is None:
            raise HTTPException(404, f"postmortem {postmortem_id} not found")
        incident = await uow.incidents.get(pm.incident_id)
    return PostmortemView.from_domain(pm, incident=incident)
