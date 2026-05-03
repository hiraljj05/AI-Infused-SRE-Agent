from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

import structlog

from sre_agent.domain.entities.sla_tracker import SLAStatus, SLATracker
from sre_agent.domain.ports.notification import StatusNotificationPort
from sre_agent.domain.ports.repositories import UnitOfWork

log = structlog.get_logger(__name__)


class SLAMonitorScheduler:
    """Background worker that scans open SLA trackers and:
    1. Marks them WARNED at 50% elapsed.
    2. Marks them BREACHED when due_at passes.
    3. Posts a notification on transition (best-effort).
    """

    def __init__(
        self,
        *,
        uow_factory: Callable[[], UnitOfWork],
        status_notifier: StatusNotificationPort,
        tick_seconds: int = 30,
    ) -> None:
        self._uow_factory = uow_factory
        self._status = status_notifier
        self._tick = tick_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._notified: set[str] = set()  # avoid double-notifying same tracker

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="sla-monitor")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick_once()
            except Exception:
                log.exception("sla-monitor tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._tick)
            except asyncio.TimeoutError:
                pass

    async def _tick_once(self) -> None:
        uow = self._uow_factory()
        async with uow as u:
            open_trackers: list[SLATracker] = await u.slas.list_open()
            now = datetime.now(UTC)
            transitions: list[tuple[SLATracker, SLAStatus, SLAStatus]] = []
            for t in open_trackers:
                prev = t.status
                t.evaluate(now=now)
                if t.status != prev:
                    transitions.append((t, prev, t.status))
                    await u.slas.save(t)
            await u.commit()

            for t, prev, new_state in transitions:
                key = f"{t.id}:{new_state.value}"
                if key in self._notified:
                    continue
                self._notified.add(key)
                await self._notify_safe(t, prev, new_state)

    async def _notify_safe(
        self, t: SLATracker, prev: SLAStatus, new_state: SLAStatus
    ) -> None:
        # Best effort, never raise from saga
        try:
            uow = self._uow_factory()
            async with uow as u:
                incident = await u.incidents.get(t.incident_id)
            if incident is None:
                return
            if new_state == SLAStatus.WARNED:
                summary = (
                    f"⚠ SLA WARNING for {incident.id}: {t.sla_type.value.upper()} "
                    f"is 50% elapsed (severity {t.severity.value}). "
                    f"Due at {t.due_at.isoformat()}."
                )
            elif new_state == SLAStatus.BREACHED:
                summary = (
                    f"🚨 SLA BREACH for {incident.id}: {t.sla_type.value.upper()} "
                    f"deadline missed (severity {t.severity.value})."
                )
            else:
                return
            await self._status.post_incident_update(incident=incident, summary=summary)
            log.info(
                "sla notification sent",
                tracker=str(t.id),
                incident=t.incident_id.value,
                state=new_state.value,
            )
        except Exception:
            log.exception("sla notify failed", tracker=str(t.id))
