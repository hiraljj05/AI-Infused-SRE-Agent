from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


_PROJECT_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9-]{1,30}[A-Z0-9]$")


@dataclass(frozen=True, slots=True)
class ProjectId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.startswith("proj_"):
            raise ValueError(f"ProjectId must start with 'proj_', got {self.value!r}")

    @classmethod
    def new(cls) -> ProjectId:
        return cls(value=f"proj_{uuid.uuid4().hex[:12]}")

    def __str__(self) -> str:
        return self.value


@dataclass(slots=True, kw_only=True)
class Project:
    """A logical grouping of applications owned by one team.

    Routing for incidents flows from Project — Teams channel, Jira project key,
    email distribution list, and incident commander group are all per-project.
    """

    id: ProjectId
    key: str  # short, uppercase, used as Jira project key (e.g., "CHK")
    name: str  # human display name (e.g., "Checkout Platform")
    description: str = ""
    teams_channel_id: str | None = None
    jira_project_key: str | None = None
    email_distribution: str | None = None
    incident_commander_group: str = "incident-commanders"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not _PROJECT_KEY_PATTERN.match(self.key):
            raise ValueError(
                f"Project key must be uppercase alphanumeric with hyphens, 2-32 chars, got {self.key!r}"
            )
        if not self.name.strip():
            raise ValueError("Project name is required")
        if self.jira_project_key is None:
            self.jira_project_key = self.key
