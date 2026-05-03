from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from sre_agent.domain.entities.lesson_learnt import IssueCategory, LessonId, LessonLearnt
from sre_agent.domain.entities.sla_tracker import SLAType
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.ports.lessons import SimilarLessonsPort
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import IncidentId

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class CloseIncidentCommand:
    incident_id: IncidentId
    actor_email: str  # human who closed it
    issue_category: IssueCategory
    fix_description: str  # what they did
    fix_rationale: str  # why it worked
    could_agent_handle: str  # "yes" | "no" | "with_approval"
    tags: tuple[str, ...] = ()


class CloseIncidentWithHumanResolutionUseCase:
    """Closes a human-resolved incident and captures the resolution as a structured lesson.

    Triggered from the dashboard "Close Incident" form by SRE leads / on-call engineers.

    Side effects:
      1. Marks the incident RESOLVED in the domain.
      2. Satisfies the RESOLVE SLA tracker.
      3. Creates a LessonLearnt entity (human_verified=True, confidence=1.0).
      4. Indexes the lesson into Qdrant for future similarity lookup.
    """

    def __init__(
        self, *, uow: UnitOfWork, similar_lessons: SimilarLessonsPort
    ) -> None:
        self._uow = uow
        self._similar = similar_lessons

    async def execute(self, cmd: CloseIncidentCommand) -> LessonLearnt:
        async with self._uow as uow:
            incident = await uow.incidents.get(cmd.incident_id)
            if incident is None:
                raise IncidentStateError(f"Incident {cmd.incident_id} not found")
            app = await uow.apps.get_by_name(incident.service)

            # Compute resolution time from detection
            resolution_minutes = max(
                1, int((datetime.now(UTC) - incident.detected_at).total_seconds() // 60)
            )

            # Mark RESOLVE SLA satisfied
            sla = await uow.slas.get_for_incident_and_type(cmd.incident_id, SLAType.RESOLVE)
            if sla is not None and sla.satisfied_at is None:
                sla.satisfy()
                await uow.slas.save(sla)

            lesson = LessonLearnt(
                id=LessonId.new(),
                incident_id=cmd.incident_id,
                app_id=app.id if app else None,
                project_id=app.project_id if app else None,
                issue_category=cmd.issue_category,
                root_cause=cmd.fix_rationale,
                fix_applied=cmd.fix_description,
                resolver=f"user:{cmd.actor_email}",
                resolution_minutes=resolution_minutes,
                tags=cmd.tags + (f"can_auto:{cmd.could_agent_handle}",),
                confidence=1.0,
                human_verified=True,
            )
            existing = await uow.lessons.get_for_incident(cmd.incident_id)
            if existing is not None:
                # Replace contents but keep id
                existing.issue_category = lesson.issue_category
                existing.root_cause = lesson.root_cause
                existing.fix_applied = lesson.fix_applied
                existing.resolver = lesson.resolver
                existing.resolution_minutes = lesson.resolution_minutes
                existing.tags = lesson.tags
                existing.confidence = lesson.confidence
                existing.human_verified = True
                await uow.lessons.save(existing)
                lesson = existing
            else:
                await uow.lessons.add(lesson)

            await uow.commit()

        # Index into vector store for similarity lookup
        try:
            await self._similar.upsert(lesson)
        except Exception:
            log.warning("vector upsert of human lesson failed", lesson_id=str(lesson.id))

        log.info(
            "incident closed by human",
            incident_id=cmd.incident_id.value,
            actor=cmd.actor_email,
            issue=cmd.issue_category.value,
        )
        return lesson
