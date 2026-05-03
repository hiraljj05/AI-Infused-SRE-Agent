from __future__ import annotations

import pytest

from sre_agent.domain.entities.approval import Approval, ApprovalSagaState
from sre_agent.domain.events.approval_events import (
    ApprovalEscalated,
    ApprovalGranted,
    ApprovalRejected,
    ApprovalRequested,
    ApprovalTimedOut,
)
from sre_agent.domain.exceptions import ApprovalStateError
from sre_agent.domain.value_objects import IncidentId


def _make_approval(*, secondary: str | None = "priya@company.com") -> Approval:
    return Approval.request(
        incident_id=IncidentId.new(),
        action_name="restart_pod",
        primary_user="raj@company.com",
        secondary_user=secondary,
        commander_group="incident-commanders",
        channel="teams",
        timeout_seconds=300,
    )


class TestApprovalSaga:
    def test_initial_state_notified_primary(self) -> None:
        a = _make_approval()
        assert a.state == ApprovalSagaState.NOTIFIED_PRIMARY
        assert a.current_approver == "raj@company.com"
        events = a.drain_events()
        assert any(isinstance(e, ApprovalRequested) for e in events)

    def test_grant_finalises(self) -> None:
        a = _make_approval()
        a.drain_events()
        a.grant(approver="raj@company.com")
        assert a.is_finalized
        assert a.state == ApprovalSagaState.APPROVED
        events = a.drain_events()
        assert any(isinstance(e, ApprovalGranted) for e in events)

    def test_reject_finalises(self) -> None:
        a = _make_approval()
        a.reject(approver="raj@company.com", reason="not-now")
        assert a.is_finalized
        assert a.state == ApprovalSagaState.REJECTED
        events = a.drain_events()
        assert any(isinstance(e, ApprovalRejected) for e in events)

    def test_timeout_escalates_primary_to_secondary(self) -> None:
        a = _make_approval()
        a.drain_events()
        a.escalate_on_timeout()
        assert a.state == ApprovalSagaState.NOTIFIED_SECONDARY
        assert a.current_approver == "priya@company.com"
        events = a.drain_events()
        assert any(isinstance(e, ApprovalTimedOut) for e in events)
        assert any(isinstance(e, ApprovalEscalated) for e in events)

    def test_timeout_escalates_to_commander(self) -> None:
        a = _make_approval()
        a.drain_events()
        a.escalate_on_timeout()  # primary -> secondary
        a.drain_events()
        a.escalate_on_timeout()  # secondary -> commander
        assert a.state == ApprovalSagaState.ESCALATED_TO_COMMANDER
        assert a.current_approver == "incident-commanders"

    def test_no_secondary_goes_straight_to_commander(self) -> None:
        a = _make_approval(secondary=None)
        a.drain_events()
        a.escalate_on_timeout()
        assert a.state == ApprovalSagaState.ESCALATED_TO_COMMANDER

    def test_commander_timeout_becomes_dead_letter(self) -> None:
        a = _make_approval(secondary=None)
        a.drain_events()
        a.escalate_on_timeout()  # -> commander
        a.drain_events()
        a.escalate_on_timeout()  # -> dead_letter
        assert a.state == ApprovalSagaState.DEAD_LETTER
        assert a.is_finalized

    def test_cannot_grant_after_rejection(self) -> None:
        a = _make_approval()
        a.reject(approver="raj@company.com", reason="x")
        with pytest.raises(ApprovalStateError):
            a.grant(approver="raj@company.com")
