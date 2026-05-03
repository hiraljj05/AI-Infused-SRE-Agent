from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from sre_agent.domain.entities.service import Service
from sre_agent.domain.value_objects import ServiceName

DocumentKind = Literal[
    "runbook",
    "incident",
    "postmortem",
    "policy",
    "service",
    "escalation",
    "recommended_stack",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeDocument:
    id: str
    kind: DocumentKind
    title: str
    content: str
    metadata: dict[str, str] = field(default_factory=dict)
    score: float = 0.0


class KnowledgePort(Protocol):
    async def search(
        self,
        *,
        query: str,
        kinds: tuple[DocumentKind, ...] | None = None,
        service: ServiceName | None = None,
        limit: int = 5,
    ) -> list[KnowledgeDocument]:
        ...

    async def upsert(self, docs: list[KnowledgeDocument]) -> None:
        ...

    async def delete(self, *, doc_id: str) -> None:
        ...


class ServiceCatalogPort(Protocol):
    async def get(self, name: ServiceName) -> Service | None:
        ...

    async def list_all(self) -> list[Service]:
        ...


class EscalationLookupPort(Protocol):
    async def primary_for(self, service: ServiceName) -> str:
        ...

    async def secondary_for(self, service: ServiceName) -> str | None:
        ...

    async def commander_group(self) -> str:
        ...
