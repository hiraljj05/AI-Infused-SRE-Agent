from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from sre_agent.domain.entities.app import AppId
from sre_agent.domain.entities.lesson_learnt import IssueCategory, LessonLearnt
from sre_agent.interface.rest.dependencies import get_container

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


class LessonView(BaseModel):
    id: str
    incident_id: str
    app_id: str | None
    project_id: str | None
    issue_category: str
    root_cause: str
    fix_applied: str
    resolver: str
    resolution_minutes: int
    tags: list[str]
    confidence: float
    human_verified: bool
    created_at: datetime

    @classmethod
    def from_domain(cls, l: LessonLearnt) -> "LessonView":
        return cls(
            id=l.id.value,
            incident_id=l.incident_id.value,
            app_id=l.app_id.value if l.app_id else None,
            project_id=l.project_id.value if l.project_id else None,
            issue_category=l.issue_category.value,
            root_cause=l.root_cause,
            fix_applied=l.fix_applied,
            resolver=l.resolver,
            resolution_minutes=l.resolution_minutes,
            tags=list(l.tags),
            confidence=l.confidence,
            human_verified=l.human_verified,
            created_at=l.created_at,
        )


@router.get("", response_model=list[LessonView])
async def list_lessons(
    category: str | None = Query(default=None),
    resolver: str | None = Query(default=None),
    app_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    container=Depends(get_container),
) -> list[LessonView]:
    async with container.uow_factory() as uow:
        if app_id:
            items = await uow.lessons.list_for_app(AppId(value=app_id), limit=limit)
        else:
            items = await uow.lessons.list_recent(limit=limit)

    if category:
        try:
            cat = IssueCategory(category)
            items = [l for l in items if l.issue_category == cat]
        except ValueError:
            items = []

    if resolver:
        rl = resolver.lower()
        if rl == "agent":
            items = [l for l in items if l.resolver == "agent"]
        elif rl == "human":
            items = [l for l in items if l.resolver != "agent"]
        else:
            items = [l for l in items if resolver in l.resolver]

    return [LessonView.from_domain(l) for l in items]
