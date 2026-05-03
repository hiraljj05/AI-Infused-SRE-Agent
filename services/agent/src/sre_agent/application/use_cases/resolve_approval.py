from __future__ import annotations

from dataclasses import dataclass

from sre_agent.domain.entities.approval import Approval, ApprovalDecision
from sre_agent.domain.exceptions import ApprovalStateError
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import ApprovalId


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolveApprovalCommand:
    approval_id: ApprovalId
    decision: ApprovalDecision
    actor: str
    reason: str | None = None
    modifications: str | None = None


class ResolveApprovalUseCase:
    """Idempotent: repeated calls with the same approval_id after finalization return the saga as-is."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: ResolveApprovalCommand) -> Approval:
        async with self._uow as uow:
            approval = await uow.approvals.get(command.approval_id)
            if approval is None:
                raise ApprovalStateError(f"Approval {command.approval_id} not found")
            if approval.is_finalized:
                return approval

            if command.decision == ApprovalDecision.APPROVE:
                approval.grant(approver=command.actor, modifications=command.modifications)
            elif command.decision == ApprovalDecision.REJECT:
                approval.reject(approver=command.actor, reason=command.reason or "no-reason-given")
            else:
                approval.grant(approver=command.actor, modifications=command.modifications or "modified")

            await uow.approvals.save(approval)
            await uow.events.append(approval.drain_events())
            await uow.commit()
            return approval
