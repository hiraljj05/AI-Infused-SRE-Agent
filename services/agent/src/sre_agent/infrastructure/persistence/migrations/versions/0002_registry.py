"""project + app registry tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("key", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("teams_channel_id", sa.String(128), nullable=True),
        sa.Column("jira_project_key", sa.String(32), nullable=True),
        sa.Column("email_distribution", sa.String(256), nullable=True),
        sa.Column(
            "incident_commander_group",
            sa.String(128),
            server_default="incident-commanders",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_key", "projects", ["key"])

    op.create_table(
        "apps",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(32),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("namespace", sa.String(64), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("owners", JSONB, server_default="[]"),
        sa.Column(
            "runbook_template_id",
            sa.String(64),
            server_default="default-web-service",
        ),
        sa.Column("grafana_dashboard_uid", sa.String(64), nullable=True),
        sa.Column("enabled", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extra_metadata", JSONB, server_default="{}"),
    )
    op.create_index("ix_apps_project_id", "apps", ["project_id"])
    op.create_index("ix_apps_name", "apps", ["name"])
    op.create_index("ix_apps_namespace", "apps", ["namespace"])


def downgrade() -> None:
    op.drop_table("apps")
    op.drop_table("projects")
