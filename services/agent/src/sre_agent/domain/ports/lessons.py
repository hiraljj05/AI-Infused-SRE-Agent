from __future__ import annotations

from typing import Protocol

from sre_agent.domain.entities.app import AppId
from sre_agent.domain.entities.lesson_learnt import LessonId, LessonLearnt
from sre_agent.domain.entities.project import ProjectId
from sre_agent.domain.value_objects import IncidentId, ServiceName


class LessonsRepository(Protocol):
    async def add(self, lesson: LessonLearnt) -> None: ...
    async def get(self, lesson_id: LessonId) -> LessonLearnt | None: ...
    async def save(self, lesson: LessonLearnt) -> None: ...
    async def get_for_incident(self, incident_id: IncidentId) -> LessonLearnt | None: ...
    async def list_for_app(self, app_id: AppId, *, limit: int = 50) -> list[LessonLearnt]: ...
    async def list_recent(self, *, limit: int = 100) -> list[LessonLearnt]: ...


class SimilarLessonsPort(Protocol):
    """Vector-search lessons by semantic similarity to a query.

    Implemented by Qdrant adapter wrapping a separate `lessons_learnt` collection.
    """

    async def upsert(self, lesson: LessonLearnt) -> None: ...

    async def search(
        self,
        *,
        query_text: str,
        service: ServiceName | None = None,
        project_id: ProjectId | None = None,
        limit: int = 5,
    ) -> list[tuple[LessonLearnt, float]]:  # (lesson, similarity_score)
        ...
