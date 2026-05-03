from __future__ import annotations

import asyncio
from collections.abc import Callable

import structlog

from sre_agent.application.use_cases.generate_weekly_digest import (
    GenerateWeeklyDigestUseCase,
)
from sre_agent.domain.ports.repositories import UnitOfWork

log = structlog.get_logger(__name__)


class WeeklyDigestScheduler:
    """In-process scheduler that runs the weekly digest generation periodically.

    Default cadence is 7 days. Set `interval_seconds` to a smaller value for demos.
    The digest is logged structurally; if a `dispatch` callback is provided, it is
    invoked with the rendered markdown so the caller can post it to Teams/email/etc.
    """

    def __init__(
        self,
        *,
        uow_factory: Callable[[], UnitOfWork],
        interval_seconds: int = 7 * 24 * 60 * 60,
        dispatch: Callable[[str], asyncio.Future] | None = None,
        startup_delay_seconds: int = 60,
    ) -> None:
        self._uow_factory = uow_factory
        self._interval = interval_seconds
        self._dispatch = dispatch
        self._startup_delay = startup_delay_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="weekly-digest-scheduler")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task

    async def _run(self) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=self._startup_delay)
        except asyncio.TimeoutError:
            pass
        while not self._stop.is_set():
            try:
                await self._tick_once()
            except Exception:
                log.exception("weekly digest tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                pass

    async def _tick_once(self) -> None:
        uc = GenerateWeeklyDigestUseCase(uow=self._uow_factory())
        digest = await uc.execute(days=7)
        log.info(
            "weekly digest generated",
            new_incidents=digest.new_incidents,
            resolved=digest.resolved_incidents,
            agent_share_pct=digest.agent_share_pct,
            avg_mttr_minutes=digest.avg_mttr_minutes,
            breached_slas=digest.open_breached_slas,
        )
        if self._dispatch is not None:
            try:
                await self._dispatch(digest.summary_markdown)
            except Exception:
                log.exception("digest dispatch failed")
