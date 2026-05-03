"""Load all knowledge_base content into Qdrant.

Runs against a live Qdrant instance (local dev via docker-compose, or in-cluster).
Reads markdown/YAML from the knowledge_base directory and upserts one document per file.

Usage:
    python scripts/seed_knowledge_base.py
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

import yaml

from sre_agent.common.config import get_settings
from sre_agent.domain.ports.knowledge import KnowledgeDocument, KnowledgePort
from sre_agent.infrastructure.embeddings import SentenceTransformersEmbeddingsAdapter
from sre_agent.infrastructure.knowledge import (
    PgVectorKnowledgeAdapter,
    QdrantKnowledgeAdapter,
)
from sre_agent.infrastructure.persistence.postgres.uow import make_engine


KB_ROOT = Path(os.environ.get("KNOWLEDGE_BASE_ROOT", "knowledge_base")).resolve()


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_markdown(path: Path) -> KnowledgeDocument:
    raw = path.read_text()
    m = FRONTMATTER_RE.match(raw)
    if not m:
        raise ValueError(f"Missing frontmatter in {path}")
    fm = yaml.safe_load(m.group(1)) or {}
    body = m.group(2).strip()
    doc_id = str(fm["id"])
    kind = str(fm.get("kind", "runbook"))
    title = str(fm.get("title", doc_id))
    service = fm.get("service")
    metadata = {k: str(v) for k, v in fm.items() if k not in {"id", "kind", "title", "content"}}
    if service is not None:
        metadata["service"] = str(service)
    return KnowledgeDocument(
        id=doc_id,
        kind=kind,  # type: ignore[arg-type]
        title=title,
        content=body,
        metadata=metadata,
    )


def parse_service_yaml(path: Path) -> KnowledgeDocument:
    data = yaml.safe_load(path.read_text()) or {}
    name = str(data["name"])
    content = yaml.safe_dump(data, sort_keys=False)
    return KnowledgeDocument(
        id=f"SVC-{name}",
        kind="service",
        title=f"Service catalog: {name}",
        content=content,
        metadata={"service": name, "tier": str(data.get("tier", "tier-2"))},
    )


def collect_docs() -> list[KnowledgeDocument]:
    docs: list[KnowledgeDocument] = []
    for path in (KB_ROOT / "runbooks").glob("*.md"):
        docs.append(parse_markdown(path))
    for path in (KB_ROOT / "policies").glob("*.md"):
        docs.append(parse_markdown(path))
    for path in (KB_ROOT / "history").glob("*.md"):
        docs.append(parse_markdown(path))
    stacks_dir = KB_ROOT / "recommended_stacks"
    if stacks_dir.exists():
        for path in stacks_dir.glob("*.md"):
            docs.append(parse_markdown(path))
    for path in (KB_ROOT / "services").glob("*.yaml"):
        docs.append(parse_service_yaml(path))
    return docs


async def main() -> None:
    settings = get_settings()
    embeddings = SentenceTransformersEmbeddingsAdapter(
        model_name=settings.embeddings_model,
        expected_dim=settings.embeddings_dim,
    )
    kb: KnowledgePort
    if settings.vector_backend == "pgvector":
        engine = make_engine(settings.postgres_dsn)
        kb = PgVectorKnowledgeAdapter(engine=engine, embeddings=embeddings)
        target = "knowledge_docs (pgvector)"
    else:
        kb = QdrantKnowledgeAdapter(
            url=settings.qdrant_url,
            collection=settings.qdrant_collection,
            embeddings=embeddings,
            api_key=settings.qdrant_api_key,
        )
        target = f"qdrant collection '{settings.qdrant_collection}'"
    await kb.ensure_collection()  # type: ignore[attr-defined]

    docs = collect_docs()
    print(f"Loading {len(docs)} documents into {target}")
    batch = 16
    for i in range(0, len(docs), batch):
        await kb.upsert(docs[i : i + batch])
        print(f"  upserted {min(i + batch, len(docs))}/{len(docs)}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
