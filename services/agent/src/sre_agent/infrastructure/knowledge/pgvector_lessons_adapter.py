"""pgvector-backed implementation of SimilarLessonsPort.

Stores embeddings + denormalized payload in the `lessons_vec` table on the same
Postgres database as the relational `lessons_learnt` table. The two are kept
in sync by ExtractLessonsLearntUseCase, which writes to the relational repo
(via the UoW) and to this adapter as part of the same lesson-creation flow.

Drop-in replacement for QdrantLessonsAdapter so we no longer need to operate
a separate vector database.
"""
from __future__ import annotations

from datetime import datetime
from typing import cast

import structlog
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from sre_agent.domain.entities.app import AppId
from sre_agent.domain.entities.lesson_learnt import IssueCategory, LessonId, LessonLearnt
from sre_agent.domain.entities.project import ProjectId
from sre_agent.domain.ports.embeddings import EmbeddingsPort
from sre_agent.domain.ports.lessons import SimilarLessonsPort
from sre_agent.domain.value_objects import IncidentId, ServiceName
from sre_agent.infrastructure.knowledge.pgvector_adapter import _vector_literal

log = structlog.get_logger(__name__)


class PgVectorLessonsAdapter(SimilarLessonsPort):
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        embeddings: EmbeddingsPort,
        table: str = "lessons_vec",
    ) -> None:
        self._engine = engine
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=engine, expire_on_commit=False
        )
        self._embeddings = embeddings
        self._table = table

    async def ensure_collection(self) -> None:
        """No-op for pgvector — schema managed by Alembic."""
        return None

    async def upsert(self, lesson: LessonLearnt) -> None:
        vec = await self._embeddings.embed_one(lesson.to_search_text())
        payload = {
            "lesson_id": lesson.id.value,
            "incident_id": lesson.incident_id.value,
            "issue_category": lesson.issue_category.value,
            "root_cause": lesson.root_cause,
            "fix_applied": lesson.fix_applied,
            "resolver": lesson.resolver,
            "resolution_minutes": lesson.resolution_minutes,
            "tags": list(lesson.tags),
            "confidence": lesson.confidence,
            "human_verified": lesson.human_verified,
            "created_at": lesson.created_at.isoformat(),
            "app_id": lesson.app_id.value if lesson.app_id else None,
            "project_id": lesson.project_id.value if lesson.project_id else None,
        }
        sql = text(
            f"""
            INSERT INTO {self._table}
                (id, incident_id, app_id, project_id, issue_category, payload, embedding)
            VALUES
                (:id, :incident_id, :app_id, :project_id, :issue_category, :payload,
                 CAST(:vec AS vector))
            ON CONFLICT (id) DO UPDATE SET
                incident_id = EXCLUDED.incident_id,
                app_id = EXCLUDED.app_id,
                project_id = EXCLUDED.project_id,
                issue_category = EXCLUDED.issue_category,
                payload = EXCLUDED.payload,
                embedding = EXCLUDED.embedding
            """
        ).bindparams(bindparam("payload", type_=JSONB))
        async with self._sessionmaker() as session:
            await session.execute(
                sql,
                {
                    "id": lesson.id.value,
                    "incident_id": lesson.incident_id.value,
                    "app_id": payload["app_id"],
                    "project_id": payload["project_id"],
                    "issue_category": lesson.issue_category.value,
                    "payload": payload,
                    "vec": _vector_literal(vec),
                },
            )
            await session.commit()
        log.info("pgvector lesson upsert", lesson_id=lesson.id.value)

    async def search(
        self,
        *,
        query_text: str,
        service: ServiceName | None = None,
        project_id: ProjectId | None = None,
        limit: int = 5,
    ) -> list[tuple[LessonLearnt, float]]:
        vec = await self._embeddings.embed_one(query_text)
        where: list[str] = []
        params: dict[str, object] = {"limit": limit, "vec": _vector_literal(vec)}
        # The Qdrant adapter intentionally ignores `service` (it lives inside the
        # tags list, not as a top-level filter). We mirror that behavior so
        # call-sites don't see a behavioral change when swapping backends.
        _ = service
        if project_id is not None:
            where.append("project_id = :project_id")
            params["project_id"] = project_id.value
        where_clause = ("WHERE " + " AND ".join(where)) if where else ""
        sql = text(
            f"""
            SELECT payload, 1 - (embedding <=> CAST(:vec AS vector)) AS score
            FROM {self._table}
            {where_clause}
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :limit
            """
        )
        async with self._sessionmaker() as session:
            rows = (await session.execute(sql, params)).mappings().all()

        results: list[tuple[LessonLearnt, float]] = []
        for row in rows:
            payload = cast(dict, row["payload"] or {})
            try:
                lesson = LessonLearnt(
                    id=LessonId(value=str(payload["lesson_id"])),
                    incident_id=IncidentId(value=str(payload["incident_id"])),
                    app_id=AppId(value=str(payload["app_id"])) if payload.get("app_id") else None,
                    project_id=(
                        ProjectId(value=str(payload["project_id"]))
                        if payload.get("project_id")
                        else None
                    ),
                    issue_category=IssueCategory(payload.get("issue_category", "other")),
                    root_cause=str(payload.get("root_cause", "")),
                    fix_applied=str(payload.get("fix_applied", "")),
                    resolver=str(payload.get("resolver", "agent")),
                    resolution_minutes=int(payload.get("resolution_minutes", 0)),
                    tags=tuple(payload.get("tags", [])),
                    confidence=float(payload.get("confidence", 0.0)),
                    human_verified=bool(payload.get("human_verified", False)),
                    created_at=datetime.fromisoformat(payload["created_at"]),
                )
                results.append((lesson, float(row["score"])))
            except Exception:
                log.warning("malformed lesson payload", lesson_id=payload.get("lesson_id"))
        return results
