from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx

from sre_agent.domain.ports.logs import LogsPort
from sre_agent.domain.value_objects import LogLevel, LogLine, ServiceName, TimeWindow


_LEVEL_PATTERN = re.compile(r"\b(DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\b", re.IGNORECASE)


def _parse_level(line: str) -> LogLevel:
    match = _LEVEL_PATTERN.search(line)
    if not match:
        return LogLevel.INFO
    token = match.group(1).upper()
    if token == "WARNING":
        return LogLevel.WARN
    return LogLevel(token)


def _level_rank(level: LogLevel) -> int:
    return {
        LogLevel.DEBUG: 0,
        LogLevel.INFO: 1,
        LogLevel.WARN: 2,
        LogLevel.ERROR: 3,
        LogLevel.FATAL: 4,
    }[level]


class LokiLogsAdapter(LogsPort):
    def __init__(self, *, url: str, timeout_seconds: float = 10.0) -> None:
        self._url = url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def close(self) -> None:
        await self._client.aclose()

    async def query_service(
        self,
        *,
        service: ServiceName,
        window: TimeWindow,
        level_at_least: str = "WARN",
        limit: int = 200,
    ) -> list[LogLine]:
        logql = f'{{app="{service}"}}'
        lines = await self.query_logql(logql=logql, window=window, limit=limit)
        min_rank = _level_rank(LogLevel(level_at_least.upper()))
        return [ln for ln in lines if _level_rank(ln.level) >= min_rank]

    async def query_logql(
        self,
        *,
        logql: str,
        window: TimeWindow,
        limit: int = 200,
    ) -> list[LogLine]:
        params = {
            "query": logql,
            "start": int(window.start.timestamp() * 1_000_000_000),
            "end": int(window.end.timestamp() * 1_000_000_000),
            "limit": str(limit),
            "direction": "backward",
        }
        try:
            response = await self._client.get(
                f"{self._url}/loki/api/v1/query_range", params=params
            )
            response.raise_for_status()
        except (httpx.ConnectError, httpx.HTTPStatusError):
            # Loki not deployed (local dev); return no lines so caller still gets evidence
            return []
        body = response.json()
        return self._to_log_lines(body)

    @staticmethod
    def _to_log_lines(body: dict[str, Any]) -> list[LogLine]:
        out: list[LogLine] = []
        result = body.get("data", {}).get("result", [])
        for stream in result:
            labels = stream.get("stream", {})
            source = labels.get("app") or labels.get("service_name") or "unknown"
            for ts, message in stream.get("values", []):
                try:
                    ts_seconds = int(ts) / 1_000_000_000
                    when = datetime.fromtimestamp(ts_seconds, tz=UTC)
                except (TypeError, ValueError):
                    continue
                out.append(
                    LogLine(
                        timestamp=when,
                        level=_parse_level(message),
                        message=message,
                        source=source,
                    )
                )
        return out
