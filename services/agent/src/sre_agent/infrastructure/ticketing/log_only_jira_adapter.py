from __future__ import annotations

import uuid

import structlog

from sre_agent.domain.ports.ticketing import CreatedTicket, TicketDraft, TicketingPort

log = structlog.get_logger(__name__)


class LogOnlyJiraAdapter(TicketingPort):
    """Dev / fallback adapter that logs ticket actions instead of calling Jira.

    Used automatically when JIRA_BASE_URL is not configured. Returns synthetic ticket
    keys so the rest of the flow continues to work for demos.
    """

    def __init__(self) -> None:
        self._counter = 0

    async def create_ticket(self, draft: TicketDraft) -> CreatedTicket:
        self._counter += 1
        key = f"{draft.project_key}-{1000 + self._counter}"
        url = f"http://localhost/jira/browse/{key}"
        log.info(
            "jira (log-only) create_ticket",
            key=key,
            project=draft.project_key,
            priority=draft.priority,
            summary=draft.summary,
        )
        return CreatedTicket(key=key, url=url)

    async def add_comment(self, ticket_key: str, comment: str) -> None:
        log.info("jira (log-only) add_comment", key=ticket_key, comment=comment[:200])

    async def transition_to_resolved(self, ticket_key: str, resolution: str) -> None:
        log.info("jira (log-only) transition_to_resolved", key=ticket_key, resolution=resolution)

    async def get_ticket_status(self, ticket_key: str) -> str | None:
        log.debug("jira (log-only) get_ticket_status", key=ticket_key)
        return None
