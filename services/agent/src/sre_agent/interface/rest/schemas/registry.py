from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from sre_agent.domain.entities.app import App
from sre_agent.domain.entities.project import Project


class ProjectIn(BaseModel):
    key: str = Field(..., min_length=2, max_length=32)
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    teams_channel_id: str | None = None
    jira_project_key: str | None = None
    email_distribution: EmailStr | None = None
    incident_commander_group: str = "incident-commanders"


class ProjectView(BaseModel):
    id: str
    key: str
    name: str
    description: str
    teams_channel_id: str | None
    jira_project_key: str | None
    email_distribution: str | None
    incident_commander_group: str
    created_at: datetime

    @classmethod
    def from_domain(cls, p: Project) -> ProjectView:
        return cls(
            id=p.id.value,
            key=p.key,
            name=p.name,
            description=p.description,
            teams_channel_id=p.teams_channel_id,
            jira_project_key=p.jira_project_key,
            email_distribution=p.email_distribution,
            incident_commander_group=p.incident_commander_group,
            created_at=p.created_at,
        )


class AppOwnerIn(BaseModel):
    email: EmailStr
    role: Literal["primary", "secondary"]


class AppIn(BaseModel):
    project_id: str
    name: str = Field(..., min_length=2, max_length=64)
    namespace: str = Field(..., min_length=1, max_length=64)
    tier: Literal["tier-0", "tier-1", "tier-2", "tier-3"]
    owners: list[AppOwnerIn] = Field(default_factory=list, max_length=10)
    runbook_template_id: str = "default-web-service"


class AppView(BaseModel):
    id: str
    project_id: str
    name: str
    namespace: str
    tier: str
    owners: list[AppOwnerIn]
    runbook_template_id: str
    grafana_dashboard_uid: str | None
    enabled: bool
    created_at: datetime
    metadata: dict[str, str]

    @classmethod
    def from_domain(cls, a: App) -> AppView:
        return cls(
            id=a.id.value,
            project_id=a.project_id.value,
            name=str(a.name),
            namespace=a.namespace,
            tier=a.tier.value,
            owners=[AppOwnerIn(email=o.email, role=o.role) for o in a.owners],
            runbook_template_id=a.runbook_template_id,
            grafana_dashboard_uid=a.grafana_dashboard_uid,
            enabled=a.enabled,
            created_at=a.created_at,
            metadata=a.metadata,
        )
