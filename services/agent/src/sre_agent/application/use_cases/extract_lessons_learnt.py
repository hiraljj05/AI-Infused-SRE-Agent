from __future__ import annotations

import json
from dataclasses import dataclass

import structlog

from sre_agent.domain.entities.lesson_learnt import IssueCategory, LessonId, LessonLearnt
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.ports.lessons import LessonsRepository, SimilarLessonsPort
from sre_agent.domain.ports.llm import LLMMessage, LLMPort
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import IncidentId

log = structlog.get_logger(__name__)


EXTRACTION_SYSTEM_PROMPT = """You extract structured lessons-learnt from a postmortem document.
Given the postmortem text, produce a JSON object with these fields:
  issue_category: one of [connection_pool, oom, latency, deploy_regression, network,
                          upstream_dependency, db_lock, queue_backup, config_error,
                          cert_expiry, crash_loop, other]
  root_cause: 1-2 sentence factual cause
  fix_applied: 1-2 sentence description of what was done
  resolver: "agent" or "user:<email>" if known, else "agent"
  resolution_minutes: integer, the time from detection to resolution in minutes (estimate if unclear)
  tags: array of 1-5 short tags (e.g., ["redis","retries","payments"])
  confidence: float [0.0, 1.0] - how confident you are in this extraction

Use only what is in the postmortem. Do not fabricate. If a field is not in the postmortem,
pick the closest issue_category and tag with "low-confidence-extraction".
"""

EXTRACTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": [
        "issue_category",
        "root_cause",
        "fix_applied",
        "resolver",
        "resolution_minutes",
        "tags",
        "confidence",
    ],
    "properties": {
        "issue_category": {
            "type": "string",
            "enum": [c.value for c in IssueCategory],
        },
        "root_cause": {"type": "string", "minLength": 5},
        "fix_applied": {"type": "string", "minLength": 5},
        "resolver": {"type": "string"},
        "resolution_minutes": {"type": "integer", "minimum": 0},
        "tags": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
}


@dataclass(frozen=True, slots=True, kw_only=True)
class ExtractLessonsCommand:
    incident_id: IncidentId
    postmortem_id: str  # to look up the source postmortem


class ExtractLessonsLearntUseCase:
    """Reads a postmortem, extracts a structured LessonLearnt, persists + indexes for vector search."""

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        llm: LLMPort,
        similar_lessons: SimilarLessonsPort,
    ) -> None:
        self._uow = uow
        self._llm = llm
        self._similar = similar_lessons

    async def execute(self, cmd: ExtractLessonsCommand) -> LessonLearnt | None:
        async with self._uow as uow:
            incident = await uow.incidents.get(cmd.incident_id)
            postmortem = await uow.postmortems.get(cmd.postmortem_id)
            app = (
                await uow.apps.get_by_name(incident.service)
                if incident is not None
                else None
            )
        if incident is None or postmortem is None:
            raise IncidentStateError("incident or postmortem missing for extraction")

        # Compose source text
        source = (
            f"Title: {postmortem.title}\n\n"
            f"Summary: {postmortem.summary}\n\n"
            f"Root cause: {postmortem.root_cause}\n\n"
            f"Impact: {postmortem.impact}\n\n"
            f"Lessons learned: {postmortem.lessons_learned}\n\n"
        )

        try:
            response = await self._llm.complete_structured(
                messages=[
                    LLMMessage(role="system", content=EXTRACTION_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=source),
                ],
                json_schema=EXTRACTION_SCHEMA,
                temperature=0.1,
                max_tokens=600,
            )
            data = response.structured or json.loads(response.content)
        except Exception as exc:
            log.warning("lesson extraction failed", error=str(exc))
            return None

        # Save lesson
        lesson = LessonLearnt(
            id=LessonId.new(),
            incident_id=cmd.incident_id,
            app_id=app.id if app else None,
            project_id=app.project_id if app else None,
            issue_category=IssueCategory(data["issue_category"]),
            root_cause=data["root_cause"],
            fix_applied=data["fix_applied"],
            resolver=data.get("resolver", "agent"),
            resolution_minutes=int(data["resolution_minutes"]),
            tags=tuple(data.get("tags", [])),
            confidence=float(data["confidence"]),
            human_verified=False,
        )

        # Persist via lessons repo (uses its own session)
        async with self._uow as uow:
            existing = await uow.lessons.get_for_incident(cmd.incident_id)
            if existing is not None:
                # Update in place
                existing.issue_category = lesson.issue_category
                existing.root_cause = lesson.root_cause
                existing.fix_applied = lesson.fix_applied
                existing.resolver = lesson.resolver
                existing.resolution_minutes = lesson.resolution_minutes
                existing.tags = lesson.tags
                existing.confidence = lesson.confidence
                await uow.lessons.save(existing)
                lesson = existing
            else:
                await uow.lessons.add(lesson)
            await uow.commit()

        # Index for vector search
        try:
            await self._similar.upsert(lesson)
        except Exception:
            log.warning("lessons vector upsert failed", lesson_id=str(lesson.id))

        log.info(
            "lesson extracted",
            lesson_id=str(lesson.id),
            issue=lesson.issue_category.value,
            confidence=lesson.confidence,
        )
        return lesson
