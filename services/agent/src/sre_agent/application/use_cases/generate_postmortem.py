from __future__ import annotations

import json
from dataclasses import dataclass

from sre_agent.domain.entities.postmortem import CorrectiveAction, Postmortem, TimelineEntry
from sre_agent.domain.events.base import DomainEvent
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.ports.llm import LLMMessage, LLMPort
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import IncidentId


POSTMORTEM_SYSTEM_PROMPT = """You are an SRE postmortem author. Produce a blameless, factual postmortem
from the provided event timeline. Be concise but comprehensive. Stick to evidence in the timeline —
do not invent details. Structure output as JSON matching the schema.
"""


POSTMORTEM_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": [
        "title",
        "summary",
        "root_cause",
        "impact",
        "lessons_learned",
        "corrective_actions",
    ],
    "properties": {
        "title": {"type": "string", "minLength": 5},
        "summary": {"type": "string", "minLength": 20},
        "root_cause": {"type": "string", "minLength": 20},
        "impact": {"type": "string", "minLength": 10},
        "lessons_learned": {"type": "string", "minLength": 20},
        "corrective_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["description", "owner"],
                "properties": {
                    "description": {"type": "string"},
                    "owner": {"type": "string"},
                },
            },
        },
    },
}


@dataclass(frozen=True, slots=True, kw_only=True)
class GeneratePostmortemInput:
    incident_id: IncidentId


class GeneratePostmortemUseCase:
    def __init__(self, *, uow: UnitOfWork, llm: LLMPort) -> None:
        self._uow = uow
        self._llm = llm

    async def execute(self, input_: GeneratePostmortemInput) -> Postmortem:
        async with self._uow as uow:
            incident = await uow.incidents.get(input_.incident_id)
            if incident is None:
                raise IncidentStateError(f"Incident {input_.incident_id} not found")
            events = await uow.events.load_for_incident(input_.incident_id)

        timeline_entries = tuple(
            TimelineEntry(at=e.occurred_at, event=self._describe(e)) for e in events
        )
        timeline_text = "\n".join(
            f"- {e.at.isoformat()} {e.event}" for e in timeline_entries
        )

        user_prompt = (
            f"Incident: {incident.id} service={incident.service} "
            f"severity={incident.severity} status={incident.status}\n\n"
            f"# Event timeline\n{timeline_text}\n\n"
            "Write the postmortem as structured JSON."
        )
        response = await self._llm.complete_structured(
            messages=[
                LLMMessage(role="system", content=POSTMORTEM_SYSTEM_PROMPT),
                LLMMessage(role="user", content=user_prompt),
            ],
            json_schema=POSTMORTEM_SCHEMA,
            temperature=0.2,
            max_tokens=2000,
        )
        data = response.structured or json.loads(response.content)
        corrective = tuple(
            CorrectiveAction(description=a["description"], owner=a["owner"])
            for a in data.get("corrective_actions", [])
        )
        pm = Postmortem(
            incident_id=incident.id,
            title=data["title"],
            summary=data["summary"],
            timeline=timeline_entries,
            root_cause=data["root_cause"],
            impact=data["impact"],
            corrective_actions=corrective,
            lessons_learned=data["lessons_learned"],
        )
        async with self._uow as uow:
            await uow.postmortems.add(pm)
            incident = await uow.incidents.get(input_.incident_id)
            if incident is None:
                raise IncidentStateError("Incident vanished between load and save")
            incident.record_postmortem_drafted(postmortem_id=pm.id, word_count=pm.word_count)
            await uow.incidents.save(incident)
            await uow.events.append(incident.drain_events())
            await uow.commit()
        return pm

    @staticmethod
    def _describe(event: DomainEvent) -> str:
        return f"{event.event_type}({event.event_id})"
