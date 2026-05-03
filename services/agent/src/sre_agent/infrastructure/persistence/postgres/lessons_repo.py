from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sre_agent.domain.entities.app import AppId
from sre_agent.domain.entities.lesson_learnt import IssueCategory, LessonId, LessonLearnt
from sre_agent.domain.entities.project import ProjectId
from sre_agent.domain.ports.lessons import LessonsRepository
from sre_agent.domain.value_objects import IncidentId
from sre_agent.infrastructure.persistence.models.orm import LessonLearntModel


def _to_model(lesson: LessonLearnt) -> LessonLearntModel:
    return LessonLearntModel(
        id=lesson.id.value,
        incident_id=lesson.incident_id.value,
        app_id=lesson.app_id.value if lesson.app_id else None,
        project_id=lesson.project_id.value if lesson.project_id else None,
        issue_category=lesson.issue_category.value,
        root_cause=lesson.root_cause,
        fix_applied=lesson.fix_applied,
        resolver=lesson.resolver,
        resolution_minutes=lesson.resolution_minutes,
        tags=list(lesson.tags),
        confidence=lesson.confidence,
        human_verified=lesson.human_verified,
        created_at=lesson.created_at,
    )


def _from_model(m: LessonLearntModel) -> LessonLearnt:
    return LessonLearnt(
        id=LessonId(value=m.id),
        incident_id=IncidentId(value=m.incident_id),
        app_id=AppId(value=m.app_id) if m.app_id else None,
        project_id=ProjectId(value=m.project_id) if m.project_id else None,
        issue_category=IssueCategory(m.issue_category),
        root_cause=m.root_cause,
        fix_applied=m.fix_applied,
        resolver=m.resolver,
        resolution_minutes=m.resolution_minutes,
        tags=tuple(m.tags or []),
        confidence=m.confidence,
        human_verified=m.human_verified,
        created_at=m.created_at,
    )


class SqlAlchemyLessonsRepository(LessonsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, lesson: LessonLearnt) -> None:
        self._s.add(_to_model(lesson))

    async def get(self, lesson_id: LessonId) -> LessonLearnt | None:
        m = await self._s.get(LessonLearntModel, lesson_id.value)
        return _from_model(m) if m else None

    async def save(self, lesson: LessonLearnt) -> None:
        m = await self._s.get(LessonLearntModel, lesson.id.value)
        if m is None:
            self._s.add(_to_model(lesson))
        else:
            new = _to_model(lesson)
            for col in (
                "issue_category",
                "root_cause",
                "fix_applied",
                "resolver",
                "resolution_minutes",
                "tags",
                "confidence",
                "human_verified",
            ):
                setattr(m, col, getattr(new, col))

    async def get_for_incident(self, incident_id: IncidentId) -> LessonLearnt | None:
        stmt = (
            select(LessonLearntModel)
            .where(LessonLearntModel.incident_id == incident_id.value)
            .limit(1)
        )
        result = await self._s.execute(stmt)
        m = result.scalar_one_or_none()
        return _from_model(m) if m else None

    async def list_for_app(self, app_id: AppId, *, limit: int = 50) -> list[LessonLearnt]:
        stmt = (
            select(LessonLearntModel)
            .where(LessonLearntModel.app_id == app_id.value)
            .order_by(LessonLearntModel.created_at.desc())
            .limit(limit)
        )
        result = await self._s.execute(stmt)
        return [_from_model(m) for m in result.scalars().all()]

    async def list_recent(self, *, limit: int = 100) -> list[LessonLearnt]:
        stmt = (
            select(LessonLearntModel)
            .order_by(LessonLearntModel.created_at.desc())
            .limit(limit)
        )
        result = await self._s.execute(stmt)
        return [_from_model(m) for m in result.scalars().all()]
