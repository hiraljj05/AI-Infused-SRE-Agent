"""pgvector-backed implementation of KnowledgePort.

Stores embeddings + metadata in the `knowledge_docs` table on the same Postgres
database as the relational data. Uses an HNSW index with cosine distance, so
semantic search is `ORDER BY embedding <=> $vec LIMIT k` (1 - cosine_distance).

Created as a drop-in replacement for QdrantKnowledgeAdapter so we no longer need
to operate a separate vector database. Shares no state with QdrantKnowledgeAdapter,
so the system can run either backend depending on the VECTOR_BACKEND setting.
"""
from __future__ import annotations

from typing import cast

import structlog
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from sre_agent.domain.ports.embeddings import EmbeddingsPort
from sre_agent.domain.ports.knowledge import DocumentKind, KnowledgeDocument, KnowledgePort
from sre_agent.domain.value_objects import ServiceName

log = structlog.get_logger(__name__)


def _vector_literal(vec: list[float]) -> str:
    """Render a Python list as the pgvector text literal: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{v:.7f}" for v in vec) + "]"


class PgVectorKnowledgeAdapter(KnowledgePort):
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        embeddings: EmbeddingsPort,
        table: str = "knowledge_docs",
    ) -> None:
        self._engine = engine
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=engine, expire_on_commit=False
        )
        self._embeddings = embeddings
        # Identifier interpolation is safe because `table` is a code constant, not user input.
        self._table = table

    async def ensure_collection(self) -> None:
        """No-op for pgvector — schema is managed by Alembic. Kept for symmetry
        with QdrantKnowledgeAdapter so callers can stay backend-agnostic."""
        return None

    async def search(
        self,
        *,
        query: str,
        kinds: tuple[DocumentKind, ...] | None = None,
        service: ServiceName | None = None,
        limit: int = 5,
    ) -> list[KnowledgeDocument]:
        vector = await self._embeddings.embed_one(query)
        where: list[str] = []
        params: dict[str, object] = {"limit": limit, "vec": _vector_literal(vector)}
        if kinds:
            where.append("kind = ANY(:kinds)")
            params["kinds"] = list(kinds)
        if service is not None:
            where.append("service = :service")
            params["service"] = str(service)
        where_clause = ("WHERE " + " AND ".join(where)) if where else ""
        # `<=>` is cosine distance (0 = identical, 2 = opposite). Convert to a
        # 0..1 similarity score to match Qdrant's semantics.
        sql = text(
            f"""
            SELECT id, kind, title, content, metadata,
                   1 - (embedding <=> CAST(:vec AS vector)) AS score
            FROM {self._table}
            {where_clause}
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :limit
            """
        )
        async with self._sessionmaker() as session:
            rows = (await session.execute(sql, params)).mappings().all()
        results: list[KnowledgeDocument] = []
        for row in rows:
            metadata = cast(dict, row["metadata"] or {})
            results.append(
                KnowledgeDocument(
                    id=str(row["id"]),
                    kind=cast(DocumentKind, row["kind"]),
                    title=str(row["title"] or ""),
                    content=str(row["content"] or ""),
                    metadata={k: str(v) for k, v in metadata.items()},
                    score=float(row["score"]),
                )
            )
        return results

    async def upsert(self, docs: list[KnowledgeDocument]) -> None:
        if not docs:
            return
        vectors = await self._embeddings.embed_many([d.content for d in docs])
        rows = []
        for doc, vec in zip(docs, vectors, strict=True):
            metadata = dict(doc.metadata)
            service = metadata.pop("service", None)
            rows.append(
                {
                    "id": doc.id,
                    "kind": doc.kind,
                    "service": service,
                    "title": doc.title,
                    "content": doc.content,
                    "metadata": dict(doc.metadata),
                    "vec": _vector_literal(vec),
                }
            )
        sql = text(
            f"""
            INSERT INTO {self._table}
                (id, kind, service, title, content, metadata, embedding)
            VALUES
                (:id, :kind, :service, :title, :content, :metadata, CAST(:vec AS vector))
            ON CONFLICT (id) DO UPDATE SET
                kind = EXCLUDED.kind,
                service = EXCLUDED.service,
                title = EXCLUDED.title,
                content = EXCLUDED.content,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding
            """
        ).bindparams(bindparam("metadata", type_=JSONB))
        async with self._sessionmaker() as session:
            await session.execute(sql, rows)
            await session.commit()
        log.info("pgvector upsert", table=self._table, count=len(rows))

    async def delete(self, *, doc_id: str) -> None:
        sql = text(f"DELETE FROM {self._table} WHERE id = :id")
        async with self._sessionmaker() as session:
            await session.execute(sql, {"id": doc_id})
            await session.commit()
