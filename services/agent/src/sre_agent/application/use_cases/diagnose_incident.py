from __future__ import annotations

import json
from dataclasses import dataclass

from sre_agent.application.use_cases.gather_evidence import GatheredEvidence
from sre_agent.domain.entities.incident import Incident
from sre_agent.domain.events.incident_events import RCAHypothesis
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.ports.knowledge import KnowledgePort
from sre_agent.domain.ports.llm import LLMMessage, LLMPort
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import ConfidenceScore, IncidentId


RCA_SYSTEM_PROMPT = """You are an SRE incident diagnosis expert. Given evidence (metrics, logs, K8s state,
recent deployments) and relevant runbooks, produce ranked root cause hypotheses.

Rules:
- Only cite evidence that appears in the provided context. Do not fabricate.
- Each hypothesis must include:
  - description: one sentence, specific
  - confidence: float in [0.0, 1.0]
  - supporting_evidence: list of evidence strings you used
  - referenced_runbook_ids: list of runbook IDs from the retrieved runbooks you relied on
- Return at most 3 hypotheses. If evidence is insufficient, return 1 hypothesis with confidence <= 0.3.
- Be objective. No speculation beyond what evidence supports.
"""


RCA_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["hypotheses"],
    "properties": {
        "hypotheses": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": ["description", "confidence", "supporting_evidence"],
                "properties": {
                    "description": {"type": "string", "minLength": 10},
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "supporting_evidence": {"type": "array", "items": {"type": "string"}},
                    "referenced_runbook_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}


@dataclass(frozen=True, slots=True, kw_only=True)
class DiagnoseInput:
    incident_id: IncidentId
    evidence: GatheredEvidence


class DiagnoseIncidentUseCase:
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

    async def execute(self, input_: DiagnoseInput) -> Incident:
        async with self._uow as uow:
            incident = await uow.incidents.get(input_.incident_id)
            if incident is None:
                raise IncidentStateError(f"Incident {input_.incident_id} not found")

            from sre_agent.application.use_cases.gather_evidence import GatherEvidenceUseCase

            evidence_summary = GatherEvidenceUseCase.summarize_for_llm(input_.evidence)
            query = f"{incident.service} {incident.initial_signal}"
            runbooks = await self._knowledge.search(
                query=query,
                kinds=("runbook", "incident", "postmortem"),
                service=incident.service,
                limit=5,
            )
            runbook_block = "\n\n".join(
                f"[{r.kind}:{r.id}] {r.title}\n{r.content[:800]}" for r in runbooks
            ) or "(no relevant documents found)"

            user_prompt = (
                f"# Evidence\n{evidence_summary}\n\n"
                f"# Retrieved runbooks and similar incidents\n{runbook_block}\n\n"
                "Produce the RCA hypotheses as specified."
            )

            response = await self._llm.complete_structured(
                messages=[
                    LLMMessage(role="system", content=RCA_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=user_prompt),
                ],
                json_schema=RCA_JSON_SCHEMA,
                temperature=0.1,
                max_tokens=1500,
            )

            data = response.structured or json.loads(response.content)
            hypotheses = tuple(
                RCAHypothesis(
                    description=h["description"],
                    confidence=ConfidenceScore(float(h["confidence"])),
                    supporting_evidence=tuple(h.get("supporting_evidence", [])),
                    referenced_runbook_ids=tuple(h.get("referenced_runbook_ids", [])),
                )
                for h in data.get("hypotheses", [])
            )

            incident.record_rca(
                hypotheses=hypotheses,
                model=response.model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
            )
            await uow.incidents.save(incident)
            await uow.events.append(incident.drain_events())
            await uow.commit()
            return incident
