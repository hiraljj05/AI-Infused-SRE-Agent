from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from sre_agent.domain.entities.app import AppId
from sre_agent.domain.entities.project import ProjectId
from sre_agent.domain.value_objects import IncidentId


class IssueCategory(str, Enum):
    CONNECTION_POOL = "connection_pool"
    OOM = "oom"
    LATENCY = "latency"
    DEPLOY_REGRESSION = "deploy_regression"
    NETWORK = "network"
    UPSTREAM_DEPENDENCY = "upstream_dependency"
    DB_LOCK = "db_lock"
    QUEUE_BACKUP = "queue_backup"
    CONFIG_ERROR = "config_error"
    CERT_EXPIRY = "cert_expiry"
    CRASH_LOOP = "crash_loop"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class LessonId:
    value: str

    @classmethod
    def new(cls) -> LessonId:
        return cls(value=f"lesson_{uuid.uuid4().hex[:12]}")

    def __str__(self) -> str:
        return self.value


@dataclass(slots=True, kw_only=True)
class LessonLearnt:
    """A structured, searchable record of how an incident was resolved.

    Auto-extracted from postmortems by an LLM, optionally human-verified.
    Stored in both Postgres (for filtering / reporting) and Qdrant (for similarity search).
    """

    id: LessonId
    incident_id: IncidentId
    app_id: AppId | None
    project_id: ProjectId | None
    issue_category: IssueCategory
    root_cause: str
    fix_applied: str
    resolver: str  # "agent" or "user:<email>"
    resolution_minutes: int
    tags: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0  # LLM extraction confidence
    human_verified: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_search_text(self) -> str:
        """The text we embed for vector similarity search."""
        return (
            f"{self.issue_category.value}: {self.root_cause}\n"
            f"Fix: {self.fix_applied}\n"
            f"Tags: {', '.join(self.tags)}"
        )
