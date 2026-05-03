from __future__ import annotations

import asyncio
from collections.abc import Callable

import structlog

from sre_agent.application.use_cases.log_insights import (
    LogInsightsResult,
    LogInsightsUseCase,
)
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import ServiceName

log = structlog.get_logger(__name__)


class InsightsMonitorScheduler:
    """Background worker that refreshes log insights for every registered app.

    Results are cached on the scheduler instance so the REST handler can return
    them instantly. UI polls `/api/insights` to render.
    """

    def __init__(
        self,
        *,
        uow_factory: Callable[[], UnitOfWork],
        insights_uc: LogInsightsUseCase,
        tick_seconds: int = 90,
        window_minutes: int = 15,
    ) -> None:
        self._uow_factory = uow_factory
        self._uc = insights_uc
        self._tick = tick_seconds
        self._window = window_minutes
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._cache: dict[str, LogInsightsResult] = {}

    @property
    def cache(self) -> dict[str, LogInsightsResult]:
        return self._cache

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="insights-monitor")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task

    async def _run(self) -> None:
        # Quick first tick after startup so UI has data within ~10s
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass
        while not self._stop.is_set():
            try:
                await self._tick_once()
            except Exception:
                log.exception("insights monitor tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._tick)
            except asyncio.TimeoutError:
                pass

    async def _tick_once(self) -> None:
        uow = self._uow_factory()
        async with uow as u:
            apps = await u.apps.list_all()
        seen: set[str] = set()
        for a in apps:
            name = str(a.name)
            if name in seen:
                continue
            seen.add(name)
            try:
                result = await self._uc.execute(
                    service=ServiceName(name), minutes=self._window
                )
                self._cache[name] = result
            except Exception:
                log.exception("insight refresh failed", service=name)
        # Always include `agent` so home page has at least one entry early
        if "agent" not in self._cache:
            try:
                self._cache["agent"] = await self._uc.execute(
                    service=ServiceName("agent"), minutes=self._window
                )
            except Exception:
                pass
