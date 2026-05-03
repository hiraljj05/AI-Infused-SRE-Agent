from __future__ import annotations

from typing import Protocol

from sre_agent.domain.value_objects import LogLine, ServiceName, TimeWindow


class LogsPort(Protocol):
    async def query_service(
        self,
        *,
        service: ServiceName,
        window: TimeWindow,
        level_at_least: str = "WARN",
        limit: int = 200,
    ) -> list[LogLine]:
        ...

    async def query_logql(
        self,
        *,
        logql: str,
        window: TimeWindow,
        limit: int = 200,
    ) -> list[LogLine]:
        ...
