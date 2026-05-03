"""track jira ticket workflow status on incidents

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("jira_ticket_status", sa.String(64), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column(
            "jira_ticket_status_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("incidents", "jira_ticket_status_updated_at")
    op.drop_column("incidents", "jira_ticket_status")
