from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

import structlog

from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.ports.ticketing import TicketingPort

log = structlog.get_logger(__name__)


class JiraStatusPoller:
    """Background worker that periodically refreshes the Jira workflow status of
    every incident with an attached ticket whose ticket isn't already in a
    terminal state. The agent's `IncidentStatus` is left untouched — only
    `incident.jira_ticket_status` / `jira_ticket_status_updated_at` change."""

    def __init__(
        self,
        *,
        uow_factory: Callable[[], UnitOfWork],
        ticketing: TicketingPort,
        tick_seconds: int = 30,
    ) -> None:
        self._uow_factory = uow_factory
        self._ticketing = ticketing
        self._tick = tick_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="jira-status-poller")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick_once()
            except Exception:
                log.exception("jira-status-poller tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._tick)
            except asyncio.TimeoutError:
                pass

    async def _tick_once(self) -> None:
        uow = self._uow_factory()
        async with uow as u:
            incidents = await u.incidents.list_with_pollable_jira_tickets()

        if not incidents:
            return

        now = datetime.now(UTC)
        for inc in incidents:
            if not inc.jira_ticket_key:
                continue
            try:
                fresh_status = await self._ticketing.get_ticket_status(inc.jira_ticket_key)
            except Exception:
                log.exception("get_ticket_status raised", key=inc.jira_ticket_key)
                continue
            if not fresh_status:
                continue
            if fresh_status == inc.jira_ticket_status:
                # no change — skip the write to keep the timestamp stable
                continue

            try:
                uow = self._uow_factory()
                async with uow as u:
                    persisted = await u.incidents.get(inc.id)
                    if persisted is None:
                        continue
                    prev = persisted.jira_ticket_status
                    persisted.update_ticket_status(status=fresh_status, fetched_at=now)
                    await u.incidents.save(persisted)
                    await u.commit()
                log.info(
                    "jira ticket status updated",
                    incident=inc.id.value,
                    key=inc.jira_ticket_key,
                    previous=prev,
                    current=fresh_status,
                )
            except Exception:
                log.exception(
                    "persist jira_ticket_status failed",
                    incident=inc.id.value,
                    key=inc.jira_ticket_key,
                )
