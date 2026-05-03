from __future__ import annotations

from dataclasses import dataclass

from sre_agent.domain.entities.approval import Approval
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.ports.knowledge import EscalationLookupPort
from sre_agent.domain.ports.notification import (
    ApprovalCardPayload,
    ApprovalNotificationPort,
    NotificationChannel,
)
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import IncidentId


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestApprovalInput:
    incident_id: IncidentId
    channel: NotificationChannel = "teams"
    timeout_seconds: int = 300


class RequestApprovalUseCase:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        escalation: EscalationLookupPort,
        notifier: ApprovalNotificationPort,
    ) -> None:
        self._uow = uow
        self._escalation = escalation
        self._notifier = notifier

    async def execute(self, input_: RequestApprovalInput) -> Approval:
        async with self._uow as uow:
            incident = await uow.incidents.get(input_.incident_id)
            if incident is None:
                raise IncidentStateError(f"Incident {input_.incident_id} not found")
            if incident.proposed_action is None:
                raise IncidentStateError("Cannot request approval without a proposed action")

            primary = await self._escalation.primary_for(incident.service)
            secondary = await self._escalation.secondary_for(incident.service)
            commander = await self._escalation.commander_group()

            approval = Approval.request(
                incident_id=incident.id,
                action_name=incident.proposed_action.name,
                primary_user=primary,
                secondary_user=secondary,
                commander_group=commander,
                channel=input_.channel,
                timeout_seconds=input_.timeout_seconds,
            )
            await uow.approvals.add(approval)
            await uow.events.append(approval.drain_events())
            await uow.commit()

        payload = ApprovalCardPayload(
            approval=approval,
            incident=incident,
            rationale=incident.proposed_action.rationale,
            metrics_summary="(see dashboard)",
        )
        await self._notifier.request_approval(to_user=primary, payload=payload)
        return approval
