from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from sre_agent.domain.ports.knowledge import KnowledgePort
from sre_agent.domain.ports.llm import LLMMessage, LLMPort

ADVISORY_SYSTEM_PROMPT = """You are an SRE advisor for teams launching a new application.
Your goal is to recommend a production-ready stack and produce an SRE-readiness checklist.

You will receive:
- A short profile of the project (cloud, workload type, scale, compliance, latency target)
- Snippets retrieved from a `recommended_stacks` knowledge base

Your job:
1. Recommend a stack: hosting platform, observability, CI/CD, alerting, on-call rotation, capacity baseline
2. Produce a markdown SRE-readiness checklist organized into: Observability, Reliability, Security, Operational Excellence
3. Be specific (e.g., "Prometheus + Grafana", not just "metrics") and cite the docs you used in [DOC-ID] form
4. End with a "Risks to monitor" section

Format the response as well-structured markdown with H2 (##) section headings.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class AdvisoryProfile:
    cloud: Literal["azure", "aws", "gcp", "on-prem", "multi"]
    workload_type: Literal["web", "api", "batch", "ml", "data-pipeline", "iot", "other"]
    scale: Literal["startup", "growth", "enterprise"]
    compliance: list[str] = field(default_factory=list)  # e.g., "HIPAA", "PCI-DSS", "SOC2"
    latency_target_ms: int = 200
    extra_context: str = ""


@dataclass(slots=True, kw_only=True)
class AdvisoryResult:
    recommendation_markdown: str
    cited_docs: list[str]
    model: str


class RunAdvisoryConversationUseCase:
    """One-shot advisory: takes a project profile, returns an SRE-readiness recommendation.

    Multi-turn refinement is left to the dashboard UI; the backend is stateless.
    """

    def __init__(self, *, llm: LLMPort, knowledge: KnowledgePort) -> None:
        self._llm = llm
        self._knowledge = knowledge

    async def execute(self, profile: AdvisoryProfile) -> AdvisoryResult:
        query = (
            f"{profile.cloud} {profile.workload_type} {profile.scale} "
            f"{' '.join(profile.compliance)} latency {profile.latency_target_ms}ms"
        )
        docs = await self._knowledge.search(query=query, limit=6)

        kb_block = (
            "\n\n".join(
                f"[{d.id}] ({d.kind}) {d.title}\n{d.content[:1000]}"
                for d in docs
            )
            or "(no recommended_stacks docs found — answer from general SRE knowledge)"
        )

        profile_block = (
            f"- Cloud: {profile.cloud}\n"
            f"- Workload type: {profile.workload_type}\n"
            f"- Scale: {profile.scale}\n"
            f"- Compliance: {', '.join(profile.compliance) or 'none'}\n"
            f"- Latency target: {profile.latency_target_ms}ms\n"
            f"- Extra context: {profile.extra_context or '(none)'}"
        )

        user_prompt = (
            f"# Project profile\n{profile_block}\n\n"
            f"# Reference stacks\n{kb_block}\n\n"
            "# Task\nProduce the recommendation and checklist now."
        )
        response = await self._llm.complete(
            messages=[
                LLMMessage(role="system", content=ADVISORY_SYSTEM_PROMPT),
                LLMMessage(role="user", content=user_prompt),
            ],
            temperature=0.3,
            max_tokens=1800,
        )
        return AdvisoryResult(
            recommendation_markdown=response.content,
            cited_docs=[d.id for d in docs],
            model=response.model,
        )
