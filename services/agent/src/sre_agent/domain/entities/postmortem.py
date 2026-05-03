from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sre_agent.domain.value_objects import IncidentId


@dataclass(frozen=True, slots=True, kw_only=True)
class TimelineEntry:
    at: datetime
    event: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CorrectiveAction:
    description: str
    owner: str
    due_date: datetime | None = None
    jira_ticket: str | None = None


@dataclass(slots=True, kw_only=True)
class Postmortem:
    id: str = field(default_factory=lambda: f"PM-{uuid.uuid4().hex[:10].upper()}")
    incident_id: IncidentId
    title: str
    summary: str
    timeline: tuple[TimelineEntry, ...]
    root_cause: str
    impact: str
    corrective_actions: tuple[CorrectiveAction, ...]
    lessons_learned: str
    drafted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = None
    signed_off_by: str | None = None

    @property
    def word_count(self) -> int:
        texts = [self.summary, self.root_cause, self.impact, self.lessons_learned]
        return sum(len(t.split()) for t in texts)

    @property
    def is_published(self) -> bool:
        return self.published_at is not None

    def sign_off(self, *, by: str) -> None:
        self.signed_off_by = by
        self.published_at = datetime.now(UTC)
