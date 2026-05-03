from __future__ import annotations

from typing import Any

import httpx
import structlog
from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ChannelAccount

from sre_agent.application.use_cases.answer_query import (
    AnswerOperationalQueryUseCase,
    AnswerQueryInput,
)
from sre_agent.application.use_cases.resolve_approval import ResolveApprovalCommand, ResolveApprovalUseCase
from sre_agent.domain.entities.approval import ApprovalDecision
from sre_agent.domain.exceptions import ApprovalStateError
from sre_agent.domain.value_objects import ApprovalId
from sre_agent.infrastructure.messaging.teams_adapter import ConversationReferenceStore


log = structlog.get_logger(__name__)

WELCOME = (
    "Hi - I am the SRE Agent. I can tell you about active incidents, runbooks, "
    "and on-call owners. Try: 'what is broken?', 'show me incidents on payments-api', "
    "'who is on call for auth?'."
)


class SREAgentBot(ActivityHandler):
    """Teams bot entry point. Handles chat messages and adaptive card submits."""

    def __init__(
        self,
        *,
        refs: ConversationReferenceStore,
        answer_query: AnswerOperationalQueryUseCase,
        resolve_approval: ResolveApprovalUseCase,
        api_base_url: str,
    ) -> None:
        super().__init__()
        self._refs = refs
        self._answer = answer_query
        self._resolve = resolve_approval
        self._api_base = api_base_url.rstrip("/")

    async def on_turn(self, turn_context: TurnContext) -> None:
        self._refs.save_from_activity(turn_context.activity)
        await super().on_turn(turn_context)

    async def on_members_added_activity(
        self,
        members_added: list[ChannelAccount],
        turn_context: TurnContext,
    ) -> None:
        for member in members_added:
            if turn_context.activity.recipient and member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(WELCOME)

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        value: dict[str, Any] | None = turn_context.activity.value
        if value and "approval_id" in value and "decision" in value:
            await self._handle_card_submit(turn_context, value)
            return

        text = (turn_context.activity.text or "").strip()
        if not text:
            await turn_context.send_activity("Please ask a question, or use an approval card.")
            return
        try:
            result = await self._answer.execute(AnswerQueryInput(question=text))
        except Exception as exc:
            log.exception("bot answer failed")
            await turn_context.send_activity(f"Sorry - I hit an error: {exc}")
            return
        cited = f"\n\n_Sources: {', '.join(result.cited_docs)}_" if result.cited_docs else ""
        await turn_context.send_activity(result.answer + cited)

    async def _handle_card_submit(self, turn_context: TurnContext, value: dict[str, Any]) -> None:
        actor = "unknown"
        if turn_context.activity.from_property:
            actor = (
                turn_context.activity.from_property.name
                or turn_context.activity.from_property.id
                or "unknown"
            )
        decision_raw = str(value.get("decision", "")).lower()
        try:
            decision = ApprovalDecision(decision_raw)
        except ValueError:
            await turn_context.send_activity(f"Unknown decision: {decision_raw}")
            return
        try:
            approval = await self._resolve.execute(
                ResolveApprovalCommand(
                    approval_id=ApprovalId(value=str(value["approval_id"])),
                    decision=decision,
                    actor=actor,
                    reason=value.get("reason"),
                    modifications=value.get("modifications"),
                )
            )
        except ApprovalStateError as exc:
            await turn_context.send_activity(f"Could not resolve approval: {exc}")
            return

        if approval.decision:
            await self._notify_api_resume(
                incident_id=approval.incident_id.value,
                decision=approval.decision.value,
                actor=actor,
            )
            await turn_context.send_activity(
                f"Approval {approval.id} recorded as {approval.decision.value} by {actor}."
            )
        else:
            await turn_context.send_activity(f"Approval state updated to {approval.state.value}.")

    async def _notify_api_resume(self, *, incident_id: str, decision: str, actor: str) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                await client.post(
                    f"{self._api_base}/internal/resume",
                    json={"incident_id": incident_id, "decision": decision, "actor": actor},
                )
            except Exception:
                log.exception("failed to notify api resume")
