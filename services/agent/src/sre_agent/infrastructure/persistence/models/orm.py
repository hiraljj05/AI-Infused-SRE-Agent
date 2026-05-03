from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sre_agent.infrastructure.persistence.models.base import Base


class IncidentModel(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    service: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str | None] = mapped_column(String(4), nullable=True, index=True)
    initial_signal: Mapped[str] = mapped_column(Text, default="")
    signal_sources: Mapped[list[str]] = mapped_column(JSONB, default=list)
    blast_radius: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    rca_hypotheses: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    proposed_action: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    jira_ticket_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    jira_ticket_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    jira_ticket_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    jira_ticket_status_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ApprovalModel(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    action_name: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), index=True)
    current_approver: Mapped[str | None] = mapped_column(String(128), nullable=True)
    primary_user: Mapped[str] = mapped_column(String(128))
    secondary_user: Mapped[str | None] = mapped_column(String(128), nullable=True)
    commander_group: Mapped[str] = mapped_column(String(128))
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    modifications: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PostmortemModel(Base):
    __tablename__ = "postmortems"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(256))
    summary: Mapped[str] = mapped_column(Text)
    root_cause: Mapped[str] = mapped_column(Text)
    impact: Mapped[str] = mapped_column(Text)
    lessons_learned: Mapped[str] = mapped_column(Text)
    timeline: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    corrective_actions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    drafted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_off_by: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    key: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    teams_channel_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    jira_project_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email_distribution: Mapped[str | None] = mapped_column(String(256), nullable=True)
    incident_commander_group: Mapped[str] = mapped_column(String(128), default="incident-commanders")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AppModel(Base):
    __tablename__ = "apps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    namespace: Mapped[str] = mapped_column(String(64), index=True)
    tier: Mapped[str] = mapped_column(String(16))
    owners: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    runbook_template_id: Mapped[str] = mapped_column(String(64), default="default-web-service")
    grafana_dashboard_uid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class LessonLearntModel(Base):
    __tablename__ = "lessons_learnt"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    app_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    issue_category: Mapped[str] = mapped_column(String(32), index=True)
    root_cause: Mapped[str] = mapped_column(Text)
    fix_applied: Mapped[str] = mapped_column(Text)
    resolver: Mapped[str] = mapped_column(String(128))
    resolution_minutes: Mapped[int] = mapped_column(Integer)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    confidence: Mapped[float] = mapped_column(Float)
    human_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SLATrackerModel(Base):
    __tablename__ = "sla_trackers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    sla_type: Mapped[str] = mapped_column(String(16), index=True)
    severity: Mapped[str] = mapped_column(String(4))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    satisfied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EventModel(Base):
    __tablename__ = "incident_events"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    causation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    caused_by: Mapped[str] = mapped_column(String(128), default="agent")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
