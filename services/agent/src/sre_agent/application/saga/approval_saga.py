from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog

from sre_agent.domain.entities.approval import Approval, ApprovalSagaState
from sre_agent.domain.ports.notification import (
    ApprovalCardPayload,
    ApprovalNotificationPort,
)
from sre_agent.domain.ports.repositories import UnitOfWork

DeadLetterCallback = Callable[[Approval], Awaitable[None]]


log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class SagaTimeouts:
    primary_seconds: int = 300
    secondary_seconds: int = 180
    commander_seconds: int = 120


class ApprovalSagaScheduler:
    """Background worker that escalates pending approvals on timeout.

    Runs every `tick_seconds` and scans open approvals. Each approval carries a
    `requested_at` timestamp; if the current state's TTL has passed, escalate by calling
    `Approval.escalate_on_timeout()` and re-notify the next approver.
    """

    def __init__(
        self,
        *,
        uow_factory: object,
        notifier: ApprovalNotificationPort,
        timeouts: SagaTimeouts | None = None,
        tick_seconds: int = 15,
        on_dead_letter: DeadLetterCallback | None = None,
    ) -> None:
        self._uow_factory = uow_factory  # callable returning UnitOfWork
        self._notifier = notifier
        self._timeouts = timeouts or SagaTimeouts()
        self._tick = tick_seconds
        self._on_dead_letter = on_dead_letter
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def set_dead_letter_callback(self, callback: DeadLetterCallback) -> None:
        """Allow late binding (e.g. once the FastAPI lifespan has compiled the graph)."""
        self._on_dead_letter = callback

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="approval-saga")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick_once()
            except Exception:
                log.exception("approval-saga tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._tick)
            except asyncio.TimeoutError:
                pass

    async def _tick_once(self) -> None:
        uow_factory = self._uow_factory
        uow: UnitOfWork = uow_factory()  # type: ignore[operator]
        async with uow as u:
            # Load open approvals. We use a dedicated repo method via list_by_state
            # if available, otherwise rely on a specialized scan.
            scan = getattr(u.approvals, "list_open", None)
            if scan is None:
                return
            open_approvals: list[Approval] = await scan()

            now = datetime.now(UTC)
            for approval in open_approvals:
                ttl = self._ttl_for(approval.state)
                if ttl is None:
                    continue
                if now - approval.requested_at < timedelta(seconds=ttl):
                    continue
                prev_state = approval.state
                try:
                    approval.escalate_on_timeout()
                except Exception:
                    log.exception("escalation failed", approval_id=str(approval.id))
                    continue
                approval.requested_at = now  # reset TTL for the next approver
                await u.approvals.save(approval)
                await u.events.append(approval.drain_events())
                log.info(
                    "approval escalated",
                    approval_id=str(approval.id),
                    from_state=prev_state.value,
                    to_state=approval.state.value,
                    current_approver=approval.current_approver,
                )
                if approval.current_approver and approval.state != ApprovalSagaState.DEAD_LETTER:
                    await self._renotify(approval)
                if approval.state == ApprovalSagaState.DEAD_LETTER and self._on_dead_letter is not None:
                    try:
                        await self._on_dead_letter(approval)
                    except Exception:
                        log.exception(
                            "dead-letter callback failed",
                            approval_id=str(approval.id),
                        )
            await u.commit()

    def _ttl_for(self, state: ApprovalSagaState) -> int | None:
        if state == ApprovalSagaState.NOTIFIED_PRIMARY:
            return self._timeouts.primary_seconds
        if state == ApprovalSagaState.NOTIFIED_SECONDARY:
            return self._timeouts.secondary_seconds
        if state == ApprovalSagaState.ESCALATED_TO_COMMANDER:
            return self._timeouts.commander_seconds
        return None

    async def _renotify(self, approval: Approval) -> None:
        uow_factory = self._uow_factory
        uow: UnitOfWork = uow_factory()  # type: ignore[operator]
        async with uow as u:
            incident = await u.incidents.get(approval.incident_id)
        if incident is None or incident.proposed_action is None:
            return
        if not approval.current_approver:
            return
        payload = ApprovalCardPayload(
            approval=approval,
            incident=incident,
            rationale=incident.proposed_action.rationale,
            metrics_summary="(escalated - see dashboard)",
        )
        await self._notifier.request_approval(
            to_user=approval.current_approver, payload=payload
        )
