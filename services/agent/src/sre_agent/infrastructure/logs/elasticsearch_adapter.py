from __future__ import annotations

import re
from datetime import datetime
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


class ElasticsearchLogsAdapter(LogsPort):
    """LogsPort implementation backed by Elasticsearch _search API.

    Configuration:
    - `url` (str): Elasticsearch base URL (e.g. `https://es.example.com:9200`)
    - `index_pattern` (str): index/alias to query — defaults to `logs-*`
    - `auth`: optional `(username, password)` tuple, or pass `api_key`
    - `service_field`: which field carries the service name; defaults to `service.name`
      (Elastic Common Schema). Override to `kubernetes.labels.app` or similar.
    - `message_field`: defaults to `message`.
    """

    def __init__(
        self,
        *,
        url: str,
        index_pattern: str = "logs-*",
        username: str | None = None,
        password: str | None = None,
        api_key: str | None = None,
        service_field: str = "service.name",
        message_field: str = "message",
        timeout_seconds: float = 10.0,
        verify_tls: bool = True,
    ) -> None:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"ApiKey {api_key}"
        auth = (username, password) if username and password and not api_key else None
        self._url = url.rstrip("/")
        self._index_pattern = index_pattern
        self._service_field = service_field
        self._message_field = message_field
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            headers=headers,
            auth=auth,
            verify=verify_tls,
        )

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
        body = {
            "size": limit,
            "sort": [{"@timestamp": "desc"}],
            "query": {
                "bool": {
                    "filter": [
                        {"term": {self._service_field: str(service)}},
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": window.start.isoformat(),
                                    "lte": window.end.isoformat(),
                                }
                            }
                        },
                    ]
                }
            },
        }
        lines = await self._search(body)
        min_rank = _level_rank(LogLevel(level_at_least.upper()))
        return [ln for ln in lines if _level_rank(ln.level) >= min_rank]

    async def query_logql(
        self,
        *,
        logql: str,
        window: TimeWindow,
        limit: int = 200,
    ) -> list[LogLine]:
        """Treat `logql` as a Lucene query string (best-effort cross-tool compat)."""
        body = {
            "size": limit,
            "sort": [{"@timestamp": "desc"}],
            "query": {
                "bool": {
                    "must": [{"query_string": {"query": logql or "*"}}],
                    "filter": [
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": window.start.isoformat(),
                                    "lte": window.end.isoformat(),
                                }
                            }
                        }
                    ],
                }
            },
        }
        return await self._search(body)

    async def _search(self, body: dict[str, Any]) -> list[LogLine]:
        try:
            response = await self._client.post(
                f"{self._url}/{self._index_pattern}/_search", json=body
            )
            response.raise_for_status()
        except (httpx.ConnectError, httpx.HTTPStatusError, httpx.ReadTimeout):
            return []
        return self._to_log_lines(response.json())

    def _to_log_lines(self, body: dict[str, Any]) -> list[LogLine]:
        out: list[LogLine] = []
        hits = body.get("hits", {}).get("hits", [])
        for h in hits:
            src = h.get("_source", {}) or {}
            ts = src.get("@timestamp")
            try:
                when = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None
            except (TypeError, ValueError, AttributeError):
                when = None
            if when is None:
                continue
            message = self._dotted_get(src, self._message_field) or ""
            level_str = self._dotted_get(src, "log.level") or self._dotted_get(src, "level")
            if level_str:
                try:
                    level = LogLevel(str(level_str).upper())
                except ValueError:
                    level = _parse_level(message)
            else:
                level = _parse_level(message)
            source = self._dotted_get(src, self._service_field) or "unknown"
            out.append(
                LogLine(
                    timestamp=when,
                    level=level,
                    message=str(message),
                    source=str(source),
                )
            )
        return out

    @staticmethod
    def _dotted_get(d: dict[str, Any], path: str) -> Any:
        cur: Any = d
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur
