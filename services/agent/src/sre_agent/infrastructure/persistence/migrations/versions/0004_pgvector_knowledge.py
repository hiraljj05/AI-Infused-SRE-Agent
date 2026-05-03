"""pgvector-backed knowledge base + lessons similarity tables

Replaces the external Qdrant collections (`sre_knowledge`, `lessons_learnt`) with
two Postgres tables in the same database, using the pgvector extension. Embeddings
are 384-dim (sentence-transformers/all-MiniLM-L6-v2). HNSW indexes are created with
cosine distance to match the previous Qdrant configuration.

The Qdrant adapters remain in the codebase behind the VECTOR_BACKEND config flag,
so this migration is purely additive and reversible.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-23
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


EMBED_DIM = 384


def upgrade() -> None:
    # Extension. On managed Postgres (Azure / RDS) this also requires the
    # extension to be allowlisted at the server level — handled out-of-band.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Knowledge base table (replaces Qdrant `sre_knowledge` collection).
    op.execute(
        f"""
        CREATE TABLE knowledge_docs (
            id          TEXT PRIMARY KEY,
            kind        VARCHAR(32) NOT NULL,
            service     VARCHAR(64),
            title       TEXT NOT NULL DEFAULT '',
            content     TEXT NOT NULL,
            metadata    JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            embedding   vector({EMBED_DIM}) NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.create_index("ix_knowledge_docs_kind", "knowledge_docs", ["kind"])
    op.create_index("ix_knowledge_docs_service", "knowledge_docs", ["service"])
    # HNSW for cosine similarity. m=16, ef_construction=64 are pgvector defaults
    # and work well up to ~1M vectors.
    op.execute(
        "CREATE INDEX ix_knowledge_docs_embedding "
        "ON knowledge_docs USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # Lessons-learnt vector index (replaces Qdrant `lessons_learnt` collection).
    # Note: this is *separate* from the relational `lessons_learnt` table created
    # in 0001 — that one stores the canonical record. This table stores the
    # embedding + denormalized payload optimized for ANN search.
    op.execute(
        f"""
        CREATE TABLE lessons_vec (
            id              VARCHAR(64) PRIMARY KEY,
            incident_id     VARCHAR(32) NOT NULL,
            app_id          VARCHAR(64),
            project_id      VARCHAR(64),
            issue_category  VARCHAR(32) NOT NULL,
            payload         JSONB NOT NULL,
            embedding       vector({EMBED_DIM}) NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.create_index("ix_lessons_vec_app_id", "lessons_vec", ["app_id"])
    op.create_index("ix_lessons_vec_project_id", "lessons_vec", ["project_id"])
    op.create_index("ix_lessons_vec_issue_category", "lessons_vec", ["issue_category"])
    op.execute(
        "CREATE INDEX ix_lessons_vec_embedding "
        "ON lessons_vec USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # Silence "unused import" noise from auto-generated revisions.
    _ = sa, JSONB


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS lessons_vec")
    op.execute("DROP TABLE IF EXISTS knowledge_docs")
    # Leave the extension installed — other tables/users may rely on it.
