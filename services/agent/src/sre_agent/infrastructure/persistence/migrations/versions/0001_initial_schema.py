"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-22

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("service", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(4), nullable=True),
        sa.Column("initial_signal", sa.Text, server_default=""),
        sa.Column("signal_sources", JSONB, server_default="[]"),
        sa.Column("blast_radius", JSONB, nullable=True),
        sa.Column("rca_hypotheses", JSONB, server_default="[]"),
        sa.Column("proposed_action", JSONB, nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_incidents_service", "incidents", ["service"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_severity", "incidents", ["severity"])

    op.create_table(
        "approvals",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "incident_id",
            sa.String(32),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_name", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("current_approver", sa.String(128), nullable=True),
        sa.Column("primary_user", sa.String(128), nullable=False),
        sa.Column("secondary_user", sa.String(128), nullable=True),
        sa.Column("commander_group", sa.String(128), nullable=False),
        sa.Column("decision", sa.String(16), nullable=True),
        sa.Column("decided_by", sa.String(128), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("modifications", sa.Text, nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_approvals_incident_id", "approvals", ["incident_id"])
    op.create_index("ix_approvals_state", "approvals", ["state"])

    op.create_table(
        "postmortems",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "incident_id",
            sa.String(32),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("root_cause", sa.Text, nullable=False),
        sa.Column("impact", sa.Text, nullable=False),
        sa.Column("lessons_learned", sa.Text, nullable=False),
        sa.Column("timeline", JSONB, server_default="[]"),
        sa.Column("corrective_actions", JSONB, server_default="[]"),
        sa.Column("drafted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_off_by", sa.String(128), nullable=True),
    )
    op.create_index("ix_postmortems_incident_id", "postmortems", ["incident_id"])

    op.create_table(
        "incident_events",
        sa.Column("event_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "incident_id",
            sa.String(32),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("causation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("caused_by", sa.String(128), server_default="agent"),
        sa.Column("payload", JSONB, server_default="{}"),
    )
    op.create_index("ix_events_incident_id", "incident_events", ["incident_id"])
    op.create_index("ix_events_event_type", "incident_events", ["event_type"])
    op.create_index("ix_events_occurred_at", "incident_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("incident_events")
    op.drop_table("postmortems")
    op.drop_table("approvals")
    op.drop_table("incidents")
