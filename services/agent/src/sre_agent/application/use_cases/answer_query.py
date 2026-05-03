from __future__ import annotations

from dataclasses import dataclass, field

from sre_agent.domain.ports.knowledge import KnowledgePort
from sre_agent.domain.ports.llm import LLMMessage, LLMPort
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import ServiceName


CHAT_SYSTEM_PROMPT = """You are an operational SRE assistant. Answer the user's question using ONLY
the provided context (runbooks, incidents, active system state). If the information is not in the
context, say so explicitly. Be concise. Cite document IDs in square brackets, e.g., [RB-042].
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class AnswerQueryInput:
    question: str
    service_filter: ServiceName | None = None


@dataclass(slots=True, kw_only=True)
class AnswerQueryResult:
    answer: str
    cited_docs: list[str] = field(default_factory=list)
    model: str = ""


class AnswerOperationalQueryUseCase:
    """Natural-language queries for the dashboard chat and Teams bot."""

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        llm: LLMPort,
        knowledge: KnowledgePort,
    ) -> None:
        self._uow = uow
        self._llm = llm
        self._knowledge = knowledge

    async def execute(self, input_: AnswerQueryInput) -> AnswerQueryResult:
        docs = await self._knowledge.search(query=input_.question, service=input_.service_filter, limit=5)

        async with self._uow as uow:
            active = await uow.incidents.list_active()
        active_block = "\n".join(
            f"- {i.id} service={i.service} severity={i.severity} status={i.status.value}"
            for i in active
        ) or "(no active incidents)"

        kb_block = "\n\n".join(
            f"[{d.id}] ({d.kind}) {d.title}\n{d.content[:600]}" for d in docs
        ) or "(no matching knowledge base docs)"

        user_prompt = (
            f"# Active incidents\n{active_block}\n\n"
            f"# Retrieved knowledge base\n{kb_block}\n\n"
            f"# Question\n{input_.question}"
        )
        response = await self._llm.complete(
            messages=[
                LLMMessage(role="system", content=CHAT_SYSTEM_PROMPT),
                LLMMessage(role="user", content=user_prompt),
            ],
            temperature=0.2,
            max_tokens=800,
        )
        return AnswerQueryResult(
            answer=response.content,
            cited_docs=[d.id for d in docs],
            model=response.model,
        )
