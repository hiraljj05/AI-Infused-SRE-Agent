from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True, kw_only=True)
class TicketDraft:
    project_key: str
    summary: str
    description: str
    priority: str  # P0/P1/P2/P3 -> Highest/High/Medium/Low
    labels: tuple[str, ...] = ()
    assignee_email: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CreatedTicket:
    key: str  # e.g., CHK-4521
    url: str


class TicketingPort(Protocol):
    async def create_ticket(self, draft: TicketDraft) -> CreatedTicket: ...
    async def add_comment(self, ticket_key: str, comment: str) -> None: ...
    async def transition_to_resolved(self, ticket_key: str, resolution: str) -> None: ...

    async def get_ticket_status(self, ticket_key: str) -> str | None:
        """Return the current workflow status name (e.g. 'To Do', 'In Progress',
        'Done'), or None if it cannot be determined.
        """
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class EmailMessage:
    to: list[str]
    subject: str
    body_text: str
    body_html: str | None = None
    cc: list[str] | None = None


class EmailPort(Protocol):
    async def send(self, message: EmailMessage) -> None: ...
