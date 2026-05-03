from __future__ import annotations

import hashlib
import uuid
from typing import cast

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from sre_agent.domain.ports.embeddings import EmbeddingsPort
from sre_agent.domain.ports.knowledge import DocumentKind, KnowledgeDocument, KnowledgePort
from sre_agent.domain.value_objects import ServiceName


log = structlog.get_logger(__name__)


class QdrantKnowledgeAdapter(KnowledgePort):
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
        exists = await self._client.collection_exists(self._collection)
        if not exists:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=qmodels.VectorParams(
                    size=self._embeddings.dimension,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            for field in ("kind", "service"):
                await self._client.create_payload_index(
                    collection_name=self._collection,
                    field_name=field,
                    field_schema=qmodels.PayloadSchemaType.KEYWORD,
                )
            log.info("qdrant collection created", name=self._collection)

    async def search(
        self,
        *,
        query: str,
        kinds: tuple[DocumentKind, ...] | None = None,
        service: ServiceName | None = None,
        limit: int = 5,
    ) -> list[KnowledgeDocument]:
        vector = await self._embeddings.embed_one(query)
        must: list[qmodels.FieldCondition] = []
        if kinds:
            must.append(
                qmodels.FieldCondition(
                    key="kind",
                    match=qmodels.MatchAny(any=list(kinds)),
                )
            )
        if service is not None:
            must.append(
                qmodels.FieldCondition(
                    key="service",
                    match=qmodels.MatchValue(value=str(service)),
                )
            )
        query_filter = qmodels.Filter(must=must) if must else None
        hits = await self._client.search(
            collection_name=self._collection,
            query_vector=vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        results: list[KnowledgeDocument] = []
        for h in hits:
            payload = cast(dict, h.payload or {})
            results.append(
                KnowledgeDocument(
                    id=str(payload.get("doc_id", h.id)),
                    kind=cast(DocumentKind, payload.get("kind", "runbook")),
                    title=str(payload.get("title", "")),
                    content=str(payload.get("content", "")),
                    metadata={
                        k: str(v)
                        for k, v in payload.items()
                        if k not in ("doc_id", "kind", "title", "content")
                    },
                    score=float(h.score),
                )
            )
        return results

    async def upsert(self, docs: list[KnowledgeDocument]) -> None:
        if not docs:
            return
        vectors = await self._embeddings.embed_many([d.content for d in docs])
        points: list[qmodels.PointStruct] = []
        for doc, vec in zip(docs, vectors, strict=True):
            points.append(
                qmodels.PointStruct(
                    id=self._point_id(doc.id),
                    vector=vec,
                    payload={
                        "doc_id": doc.id,
                        "kind": doc.kind,
                        "title": doc.title,
                        "content": doc.content,
                        **doc.metadata,
                    },
                )
            )
        await self._client.upsert(collection_name=self._collection, points=points)

    async def delete(self, *, doc_id: str) -> None:
        await self._client.delete(
            collection_name=self._collection,
            points_selector=qmodels.PointIdsList(points=[self._point_id(doc_id)]),
        )

    @staticmethod
    def _point_id(doc_id: str) -> str:
        digest = hashlib.sha1(doc_id.encode("utf-8")).digest()
        return str(uuid.UUID(bytes=digest[:16]))
