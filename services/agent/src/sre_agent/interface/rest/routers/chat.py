from __future__ import annotations

from fastapi import APIRouter, Depends

from sre_agent.application.use_cases.answer_query import AnswerQueryInput
from sre_agent.application.use_cases.parse_chat_intent import ParseIntentInput
from sre_agent.application.use_cases.run_on_demand_investigation import (
    RunInvestigationCommand,
)
from sre_agent.domain.value_objects import ServiceName
from sre_agent.interface.rest.dependencies import get_container
from sre_agent.interface.rest.schemas.chat import ChatQueryIn, ChatQueryOut

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatQueryOut)
async def ask(body: ChatQueryIn, container=Depends(get_container)) -> ChatQueryOut:
    """Active chatbot: classify intent, route to investigation/action OR fall back to Q&A."""
    try:
        intent = await container.parse_intent_uc.execute(ParseIntentInput(text=body.question))
    except Exception:
        intent = None  # fall through to Q&A

    # ROUTE 1: investigation
    if intent and intent.intent == "investigate_app" and intent.app:
        result = await container.investigate_uc.execute(
            RunInvestigationCommand(
                service=ServiceName(intent.app),
                namespace=container.settings.target_namespace,
                requested_by="dashboard-user",
                propose_remediation=True,
            )
        )
        top = result.incident.top_hypothesis
        action = result.incident.proposed_action
        body_md = (
            f"### Investigation: `{intent.app}`\n\n"
            f"**Incident**: `{result.incident.id}` (severity {result.incident.severity})\n\n"
        )
        if top is not None:
            body_md += (
                f"**Top RCA hypothesis** ({top.confidence}):\n> {top.description}\n\n"
                f"_Evidence_: {' · '.join(top.supporting_evidence[:3])}\n\n"
            )
        if action is not None:
            hil = " (requires approval)" if action.requires_hil else ""
            body_md += f"**Suggested action**{hil}: `{action.name}` — {action.rationale}\n"
        cited = list(top.referenced_runbook_ids) if top else []
        return ChatQueryOut(answer=body_md, cited_docs=cited, model="agent-investigation")

    # ROUTE 2: propose-only / execute-action
    if intent and intent.intent in ("propose_action", "execute_action") and intent.app:
        result = await container.investigate_uc.execute(
            RunInvestigationCommand(
                service=ServiceName(intent.app),
                namespace=container.settings.target_namespace,
                requested_by="dashboard-user",
                propose_remediation=True,
            )
        )
        action = result.incident.proposed_action
        if action is None:
            return ChatQueryOut(
                answer=f"No remediation could be proposed for `{intent.app}`.",
                cited_docs=[],
                model="agent-investigation",
            )
        body_md = (
            f"### Proposed for `{intent.app}`: `{action.name}`\n\n"
            f"{action.rationale}\n\n"
            f"**Confidence**: {action.confidence}  ·  **Blast**: {action.blast_radius.level.value}\n"
            f"**Requires approval**: {'yes' if action.requires_hil else 'no (auto-executable)'}\n\n"
            f"Incident: `{result.incident.id}`. "
            f"Open the Incidents page to approve/reject."
        )
        return ChatQueryOut(answer=body_md, cited_docs=[], model="agent-plan")

    # ROUTE 3: fall back to Q&A (RAG)
    result = await container.answer_query_uc.execute(
        AnswerQueryInput(
            question=body.question,
            service_filter=ServiceName(body.service) if body.service else None,
        )
    )
    return ChatQueryOut(
        answer=result.answer, cited_docs=result.cited_docs, model=result.model
    )
