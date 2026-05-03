from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from sre_agent.domain.entities.approval import Approval
from sre_agent.domain.entities.incident import Incident

NotificationChannel = Literal["teams", "slack", "email", "webhook"]


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovalCardPayload:
    approval: Approval
    incident: Incident
    rationale: str
    metrics_summary: str = ""


class ApprovalNotificationPort(Protocol):
    async def request_approval(
        self,
        *,
        to_user: str,
        payload: ApprovalCardPayload,
    ) -> str:
        """Send approval request, return message/thread ID for later updates."""
        ...

    async def update_approval_message(
        self,
        *,
        to_user: str,
        thread_id: str,
        final_status: Literal["approved", "rejected", "timed_out", "escalated"],
        decided_by: str | None = None,
    ) -> None:
        ...


class StatusNotificationPort(Protocol):
    async def post_incident_update(
        self,
        *,
        incident: Incident,
        summary: str,
        channel_id: str | None = None,
    ) -> None:
        ...

    async def post_resolution(
        self,
        *,
        incident: Incident,
        summary: str,
    ) -> None:
        ...
