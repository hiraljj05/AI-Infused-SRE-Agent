from __future__ import annotations

import hashlib
import uuid

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from sre_agent.domain.entities.app import AppId
from sre_agent.domain.entities.lesson_learnt import IssueCategory, LessonId, LessonLearnt
from sre_agent.domain.entities.project import ProjectId
from sre_agent.domain.ports.embeddings import EmbeddingsPort
from sre_agent.domain.ports.lessons import SimilarLessonsPort
from sre_agent.domain.value_objects import IncidentId, ServiceName

log = structlog.get_logger(__name__)


class QdrantLessonsAdapter(SimilarLessonsPort):
    """Vector search over the `lessons_learnt` collection.

    Separate from the runbooks collection so we can filter and rank independently.
    """

    def __init__(
        self,
        *,
        url: str,
        collection: str,
        embeddings: EmbeddingsPort,
        api_key: str | None = None,
    ) -> None:
        self._client = AsyncQdrantClient(url=url, api_key=api_key or None)
        self._collection = collection
        self._embeddings = embeddings

    async def ensure_collection(self) -> None:
        if not await self._client.collection_exists(self._collection):
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=qmodels.VectorParams(
                    size=self._embeddings.dimension,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            for field in ("service", "project_id", "issue_category", "human_verified"):
                await self._client.create_payload_index(
                    collection_name=self._collection,
                    field_name=field,
                    field_schema=qmodels.PayloadSchemaType.KEYWORD,
                )
            log.info("qdrant lessons collection created", name=self._collection)

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
            "human_verified": str(lesson.human_verified),
            "created_at": lesson.created_at.isoformat(),
        }
        if lesson.app_id:
            payload["app_id"] = lesson.app_id.value
        if lesson.project_id:
            payload["project_id"] = lesson.project_id.value
        await self._client.upsert(
            collection_name=self._collection,
            points=[
                qmodels.PointStruct(
                    id=self._point_id(lesson.id.value),
                    vector=vec,
                    payload=payload,
                )
            ],
        )

    async def search(
        self,
        *,
        query_text: str,
        service: ServiceName | None = None,
        project_id: ProjectId | None = None,
        limit: int = 5,
    ) -> list[tuple[LessonLearnt, float]]:
        vec = await self._embeddings.embed_one(query_text)
        must: list[qmodels.FieldCondition] = []
        if service is not None:
            # Service-name filter is stored as 'service' tag inside tags list — we keep
            # only project-level filter on the indexed key.
            pass
        if project_id is not None:
            must.append(
                qmodels.FieldCondition(
                    key="project_id", match=qmodels.MatchValue(value=project_id.value)
                )
            )
        query_filter = qmodels.Filter(must=must) if must else None
        hits = await self._client.search(
            collection_name=self._collection,
            query_vector=vec,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        results: list[tuple[LessonLearnt, float]] = []
        for h in hits:
            payload = dict(h.payload or {})
            from datetime import datetime as _dt

            try:
                lesson = LessonLearnt(
                    id=LessonId(value=str(payload["lesson_id"])),
                    incident_id=IncidentId(value=str(payload["incident_id"])),
                    app_id=AppId(value=str(payload["app_id"])) if payload.get("app_id") else None,
                    project_id=ProjectId(value=str(payload["project_id"]))
                    if payload.get("project_id")
                    else None,
                    issue_category=IssueCategory(payload.get("issue_category", "other")),
                    root_cause=str(payload.get("root_cause", "")),
                    fix_applied=str(payload.get("fix_applied", "")),
                    resolver=str(payload.get("resolver", "agent")),
                    resolution_minutes=int(payload.get("resolution_minutes", 0)),
                    tags=tuple(payload.get("tags", [])),
                    confidence=float(payload.get("confidence", 0.0)),
                    human_verified=str(payload.get("human_verified", "False")) == "True",
                    created_at=_dt.fromisoformat(payload["created_at"]),
                )
                results.append((lesson, float(h.score)))
            except Exception:
                log.warning("malformed lesson payload", lesson_id=payload.get("lesson_id"))
        return results

    @staticmethod
    def _point_id(doc_id: str) -> str:
        digest = hashlib.sha1(doc_id.encode()).digest()
        return str(uuid.UUID(bytes=digest[:16]))
