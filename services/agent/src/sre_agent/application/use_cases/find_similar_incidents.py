from __future__ import annotations

from dataclasses import dataclass

import structlog

from sre_agent.domain.entities.lesson_learnt import LessonLearnt
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.ports.lessons import SimilarLessonsPort
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import IncidentId

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class FindSimilarCommand:
    incident_id: IncidentId
    limit: int = 5


@dataclass(slots=True, kw_only=True)
class SimilarMatch:
    lesson: LessonLearnt
    similarity: float  # 0..1


@dataclass(slots=True, kw_only=True)
class FindSimilarResult:
    matches: list[SimilarMatch]
    top_match: SimilarMatch | None
    confident_match: bool  # True if top score >= 0.85


class FindSimilarIncidentsUseCase:
    """Memory-first: before full diagnosis, look up similar past resolutions.

    If a high-confidence match (>= 0.85) is found, the agent can short-circuit and
    propose the same fix as last time (still subject to HIL on non-LOW actions).
    """

    def __init__(self, *, uow: UnitOfWork, similar: SimilarLessonsPort) -> None:
        self._uow = uow
        self._similar = similar

    async def execute(self, cmd: FindSimilarCommand) -> FindSimilarResult:
        async with self._uow as uow:
            incident = await uow.incidents.get(cmd.incident_id)
            if incident is None:
                raise IncidentStateError(f"Incident {cmd.incident_id} not found")
            app = await uow.apps.get_by_name(incident.service)
        project_id = app.project_id if app else None

        query = f"{incident.service} {incident.initial_signal}"
        try:
            raw = await self._similar.search(
                query_text=query,
                project_id=project_id,
                service=incident.service,
                limit=cmd.limit,
            )
        except Exception as exc:
            log.warning("similar incident search failed", error=str(exc))
            raw = []

        matches = [SimilarMatch(lesson=lesson, similarity=score) for lesson, score in raw]
        top = matches[0] if matches else None
        confident = bool(top and top.similarity >= 0.85)
        return FindSimilarResult(matches=matches, top_match=top, confident_match=confident)
