from __future__ import annotations

from sre_agent.domain.entities.app import App, AppId, AppOwner
from sre_agent.domain.entities.project import Project, ProjectId
from sre_agent.domain.entities.service import ServiceTier
from sre_agent.domain.value_objects import ServiceName
from sre_agent.infrastructure.persistence.models.orm import AppModel, ProjectModel


def project_to_model(p: Project) -> ProjectModel:
    return ProjectModel(
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


def project_from_model(m: ProjectModel) -> Project:
    return Project(
        id=ProjectId(value=m.id),
        key=m.key,
        name=m.name,
        description=m.description,
        teams_channel_id=m.teams_channel_id,
        jira_project_key=m.jira_project_key,
        email_distribution=m.email_distribution,
        incident_commander_group=m.incident_commander_group,
        created_at=m.created_at,
    )


def apply_project_to_model(p: Project, m: ProjectModel) -> None:
    m.key = p.key
    m.name = p.name
    m.description = p.description
    m.teams_channel_id = p.teams_channel_id
    m.jira_project_key = p.jira_project_key
    m.email_distribution = p.email_distribution
    m.incident_commander_group = p.incident_commander_group


def app_to_model(a: App) -> AppModel:
    return AppModel(
        id=a.id.value,
        project_id=a.project_id.value,
        name=str(a.name),
        namespace=a.namespace,
        tier=a.tier.value,
        owners=[{"email": o.email, "role": o.role} for o in a.owners],
        runbook_template_id=a.runbook_template_id,
        grafana_dashboard_uid=a.grafana_dashboard_uid,
        enabled=a.enabled,
        created_at=a.created_at,
        extra_metadata=a.metadata,
    )


def app_from_model(m: AppModel) -> App:
    owners = tuple(
        AppOwner(email=o["email"], role=o["role"]) for o in (m.owners or [])
    )
    return App(
        id=AppId(value=m.id),
        project_id=ProjectId(value=m.project_id),
        name=ServiceName(m.name),
        namespace=m.namespace,
        tier=ServiceTier(m.tier),
        owners=owners,
        runbook_template_id=m.runbook_template_id,
        grafana_dashboard_uid=m.grafana_dashboard_uid,
        enabled=m.enabled,
        created_at=m.created_at,
        metadata=dict(m.extra_metadata or {}),
    )


def apply_app_to_model(a: App, m: AppModel) -> None:
    m.project_id = a.project_id.value
    m.name = str(a.name)
    m.namespace = a.namespace
    m.tier = a.tier.value
    m.owners = [{"email": o.email, "role": o.role} for o in a.owners]
    m.runbook_template_id = a.runbook_template_id
    m.grafana_dashboard_uid = a.grafana_dashboard_uid
    m.enabled = a.enabled
    m.extra_metadata = a.metadata
