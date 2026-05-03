"""attach jira ticket info to incidents

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("jira_ticket_key", sa.String(64), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("jira_ticket_url", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_incidents_jira_ticket_key", "incidents", ["jira_ticket_key"]
    )


def downgrade() -> None:
    op.drop_index("ix_incidents_jira_ticket_key", table_name="incidents")
    op.drop_column("incidents", "jira_ticket_url")
    op.drop_column("incidents", "jira_ticket_key")
