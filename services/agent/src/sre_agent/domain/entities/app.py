from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sre_agent.domain.entities.project import ProjectId
from sre_agent.domain.entities.service import ServiceTier
from sre_agent.domain.value_objects import ServiceName


@dataclass(frozen=True, slots=True)
class AppId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.startswith("app_"):
            raise ValueError(f"AppId must start with 'app_', got {self.value!r}")

    @classmethod
    def new(cls) -> AppId:
        return cls(value=f"app_{uuid.uuid4().hex[:12]}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True, kw_only=True)
class AppOwner:
    email: str
    role: str  # primary | secondary

    def __post_init__(self) -> None:
        if "@" not in self.email:
            raise ValueError(f"Invalid email: {self.email!r}")
        if self.role not in ("primary", "secondary"):
            raise ValueError(f"role must be primary or secondary, got {self.role!r}")


@dataclass(slots=True, kw_only=True)
class App:
    """A deployed application registered with the SRE agent.

    Linked to a Project for routing context (Teams channel, Jira project, email list).
    """

    id: AppId
    project_id: ProjectId
    name: ServiceName
    namespace: str
    tier: ServiceTier
    owners: tuple[AppOwner, ...] = field(default_factory=tuple)
    runbook_template_id: str = "default-web-service"
    grafana_dashboard_uid: str | None = None  # set after onboarding generates one
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, str] = field(default_factory=dict)

    def primary_owner(self) -> AppOwner | None:
        for o in self.owners:
            if o.role == "primary":
                return o
        return None

    def secondary_owner(self) -> AppOwner | None:
        for o in self.owners:
            if o.role == "secondary":
                return o
        return None
