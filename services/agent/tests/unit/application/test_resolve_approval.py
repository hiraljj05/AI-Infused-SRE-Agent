from __future__ import annotations

import pytest

from sre_agent.application.use_cases.resolve_approval import (
    ResolveApprovalCommand,
    ResolveApprovalUseCase,
)
from sre_agent.domain.entities.approval import Approval, ApprovalDecision, ApprovalSagaState
from sre_agent.domain.value_objects import IncidentId
from tests.fixtures.fake_uow import FakeUoW


def _seed_approval(uow: FakeUoW) -> Approval:
    approval = Approval.request(
        incident_id=IncidentId.new(),
        action_name="restart_pod",
        primary_user="raj@company.com",
        secondary_user="priya@company.com",
        commander_group="incident-commanders",
        channel="teams",
        timeout_seconds=300,
    )
    approval.drain_events()
    uow.approvals._data[approval.id.value] = approval  # type: ignore[attr-defined]
    return approval


@pytest.mark.asyncio
async def test_approve_grants_and_finalizes() -> None:
    uow = FakeUoW()
    a = _seed_approval(uow)
    uc = ResolveApprovalUseCase(uow)
    result = await uc.execute(
        ResolveApprovalCommand(
            approval_id=a.id,
            decision=ApprovalDecision.APPROVE,
            actor="raj@company.com",
        )
    )
    assert result.state == ApprovalSagaState.APPROVED
    assert result.is_finalized


@pytest.mark.asyncio
async def test_idempotent_repeat_returns_existing_state() -> None:
    uow = FakeUoW()
    a = _seed_approval(uow)
    uc = ResolveApprovalUseCase(uow)
    first = await uc.execute(
        ResolveApprovalCommand(
            approval_id=a.id, decision=ApprovalDecision.APPROVE, actor="raj@company.com"
        )
    )
    second = await uc.execute(
        ResolveApprovalCommand(
            approval_id=a.id, decision=ApprovalDecision.REJECT, actor="someone-else", reason="oops"
        )
    )
    assert first.state == second.state == ApprovalSagaState.APPROVED


@pytest.mark.asyncio
async def test_reject_captures_reason() -> None:
    uow = FakeUoW()
    a = _seed_approval(uow)
    uc = ResolveApprovalUseCase(uow)
    result = await uc.execute(
        ResolveApprovalCommand(
            approval_id=a.id,
            decision=ApprovalDecision.REJECT,
            actor="raj@company.com",
            reason="not during business hours",
        )
    )
    assert result.state == ApprovalSagaState.REJECTED
    assert result.rejection_reason == "not during business hours"
