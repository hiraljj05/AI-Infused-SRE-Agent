from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sre_agent.domain.events.approval_events import (
    ApprovalEscalated,
    ApprovalGranted,
    ApprovalRejected,
    ApprovalRequested,
    ApprovalTimedOut,
)
from sre_agent.domain.exceptions import ApprovalStateError
from sre_agent.domain.value_objects import ApprovalId, IncidentId

if TYPE_CHECKING:
    from sre_agent.domain.events.base import DomainEvent


class ApprovalSagaState(str, Enum):
    PENDING = "pending"
    NOTIFIED_PRIMARY = "notified_primary"
    NOTIFIED_SECONDARY = "notified_secondary"
    ESCALATED_TO_COMMANDER = "escalated_to_commander"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEAD_LETTER = "dead_letter"


class ApprovalDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"


@dataclass(slots=True, kw_only=True)
class Approval:
    id: ApprovalId
    incident_id: IncidentId
    action_name: str
    state: ApprovalSagaState = ApprovalSagaState.PENDING
    current_approver: str | None = None
    primary_user: str
    secondary_user: str | None = None
    commander_group: str = "incident-commanders"
    decision: ApprovalDecision | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    rejection_reason: str | None = None
    modifications: str | None = None
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    pending_events: list[DomainEvent] = field(default_factory=list)

    @classmethod
    def request(
        cls,
        *,
        incident_id: IncidentId,
        action_name: str,
        primary_user: str,
        secondary_user: str | None,
        commander_group: str,
        channel: str,
        timeout_seconds: int,
    ) -> Approval:
        approval_id = ApprovalId.new()
        approval = cls(
            id=approval_id,
            incident_id=incident_id,
            action_name=action_name,
            state=ApprovalSagaState.NOTIFIED_PRIMARY,
            current_approver=primary_user,
            primary_user=primary_user,
            secondary_user=secondary_user,
            commander_group=commander_group,
        )
        approval.pending_events.append(
            ApprovalRequested(
                approval_id=approval_id,
                incident_id=incident_id,
                action_name=action_name,
                notified_user=primary_user,
                channel=channel,
                timeout_seconds=timeout_seconds,
            )
        )
        return approval

    def escalate_on_timeout(self) -> None:
        if self.state == ApprovalSagaState.NOTIFIED_PRIMARY:
            if self.secondary_user:
                from_user = self.primary_user
                self.state = ApprovalSagaState.NOTIFIED_SECONDARY
                self.current_approver = self.secondary_user
                self.pending_events.append(
                    ApprovalTimedOut(
                        approval_id=self.id,
                        incident_id=self.incident_id,
                        timed_out_user=from_user,
                    )
                )
                self.pending_events.append(
                    ApprovalEscalated(
                        approval_id=self.id,
                        incident_id=self.incident_id,
                        from_user=from_user,
                        to_user=self.secondary_user,
                        reason="primary-timeout",
                    )
                )
            else:
                self._escalate_to_commander(from_user=self.primary_user, reason="primary-timeout-no-secondary")
        elif self.state == ApprovalSagaState.NOTIFIED_SECONDARY:
            from_user = self.secondary_user or self.primary_user
            self._escalate_to_commander(from_user=from_user, reason="secondary-timeout")
        elif self.state == ApprovalSagaState.ESCALATED_TO_COMMANDER:
            from_user = self.current_approver or self.commander_group
            self.state = ApprovalSagaState.DEAD_LETTER
            self.pending_events.append(
                ApprovalTimedOut(
                    approval_id=self.id,
                    incident_id=self.incident_id,
                    timed_out_user=from_user,
                )
            )
        else:
            raise ApprovalStateError(f"Cannot escalate from state {self.state}")

    def _escalate_to_commander(self, *, from_user: str, reason: str) -> None:
        self.state = ApprovalSagaState.ESCALATED_TO_COMMANDER
        self.current_approver = self.commander_group
        self.pending_events.append(
            ApprovalTimedOut(
                approval_id=self.id,
                incident_id=self.incident_id,
                timed_out_user=from_user,
            )
        )
        self.pending_events.append(
            ApprovalEscalated(
                approval_id=self.id,
                incident_id=self.incident_id,
                from_user=from_user,
                to_user=self.commander_group,
                reason=reason,
            )
        )

    def grant(self, *, approver: str, modifications: str | None = None) -> None:
        if self.state in (
            ApprovalSagaState.APPROVED,
            ApprovalSagaState.REJECTED,
            ApprovalSagaState.DEAD_LETTER,
        ):
            raise ApprovalStateError(f"Approval already finalized ({self.state})")
        now = datetime.now(UTC)
        latency = (now - self.requested_at).total_seconds()
        self.state = ApprovalSagaState.APPROVED
        self.decision = ApprovalDecision.APPROVE
        self.decided_by = approver
        self.decided_at = now
        self.modifications = modifications
        self.pending_events.append(
            ApprovalGranted(
                approval_id=self.id,
                incident_id=self.incident_id,
                approved_by=approver,
                modifications=modifications,
                latency_seconds=latency,
            )
        )

    def reject(self, *, approver: str, reason: str) -> None:
        if self.state in (
            ApprovalSagaState.APPROVED,
            ApprovalSagaState.REJECTED,
            ApprovalSagaState.DEAD_LETTER,
        ):
            raise ApprovalStateError(f"Approval already finalized ({self.state})")
        now = datetime.now(UTC)
        latency = (now - self.requested_at).total_seconds()
        self.state = ApprovalSagaState.REJECTED
        self.decision = ApprovalDecision.REJECT
        self.decided_by = approver
        self.decided_at = now
        self.rejection_reason = reason
        self.pending_events.append(
            ApprovalRejected(
                approval_id=self.id,
                incident_id=self.incident_id,
                rejected_by=approver,
                reason=reason,
                latency_seconds=latency,
            )
        )

    def drain_events(self) -> list[DomainEvent]:
        events = list(self.pending_events)
        self.pending_events.clear()
        return events

    @property
    def is_finalized(self) -> bool:
        return self.state in (
            ApprovalSagaState.APPROVED,
            ApprovalSagaState.REJECTED,
            ApprovalSagaState.DEAD_LETTER,
        )
