from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from sre_agent.domain.ports.llm import LLMMessage, LLMPort
from sre_agent.domain.ports.logs import LogsPort
from sre_agent.domain.value_objects import ServiceName, TimeWindow


INSIGHT_PROMPT = """You are an SRE assistant analyzing recent service logs.

Read the log lines below and produce 1-3 brief, actionable insights. Each insight must:
- Identify a real pattern (errors trending up, repeated stack traces, deployment correlation, etc.)
- Be 1 sentence (under 130 chars)
- Have a severity: info / warn / critical
- Reference the evidence (count, time window, sample)

If logs are healthy, return a single "info" insight saying so.
Output JSON only, no prose:

{
  "insights": [
    {"severity": "info|warn|critical", "headline": "short statement", "evidence": "count + sample"}
  ]
}
"""


Severity = Literal["info", "warn", "critical"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Insight:
    severity: Severity
    headline: str
    evidence: str


@dataclass(slots=True, kw_only=True)
class LogInsightsResult:
    service: str
    window_minutes: int
    line_count: int
    error_count: int
    warn_count: int
    insights: list[Insight] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    model: str = ""


class LogInsightsUseCase:
    """Pulls recent logs for a service, asks LLM for actionable insights.

    Designed to run on a cadence (e.g. every 60-120s per service) to power a
    "continuous monitoring" view in the dashboard. Output is small + cacheable.
    """

    def __init__(self, *, logs: LogsPort, llm: LLMPort) -> None:
        self._logs = logs
        self._llm = llm

    async def execute(
        self, *, service: ServiceName, minutes: int = 15, max_lines: int = 200
    ) -> LogInsightsResult:
        end = datetime.now(UTC)
        window = TimeWindow(start=end - timedelta(minutes=minutes), end=end)
        lines = await self._logs.query_service(
            service=service, window=window, level_at_least="DEBUG", limit=max_lines
        )

        error_count = sum(1 for ln in lines if ln.level.value in ("ERROR", "FATAL"))
        warn_count = sum(1 for ln in lines if ln.level.value == "WARN")

        if not lines:
            return LogInsightsResult(
                service=str(service),
                window_minutes=minutes,
                line_count=0,
                error_count=0,
                warn_count=0,
                insights=[
                    Insight(
                        severity="info",
                        headline=f"No log activity for {service} in last {minutes}m",
                        evidence="0 lines",
                    )
                ],
                model="",
            )

        # Build a compact log digest for the LLM (keep prompt small)
        sample = lines[: min(80, len(lines))]
        digest = "\n".join(
            f"{ln.timestamp.strftime('%H:%M:%S')} {ln.level.value:<5} {ln.message[:200]}"
            for ln in sample
        )
        user_prompt = (
            f"Service: {service}\n"
            f"Window: last {minutes} minutes\n"
            f"Total lines: {len(lines)} (errors={error_count}, warns={warn_count})\n\n"
            f"Logs (sample of {len(sample)}):\n```\n{digest}\n```"
        )

        try:
            response = await self._llm.complete(
                messages=[
                    LLMMessage(role="system", content=INSIGHT_PROMPT),
                    LLMMessage(role="user", content=user_prompt),
                ],
                temperature=0.1,
                max_tokens=400,
            )
            parsed = _parse_insights(response.content)
            model_id = response.model
        except Exception:
            parsed = _heuristic_insights(error_count, warn_count, len(lines), str(service), minutes)
            model_id = "heuristic"

        return LogInsightsResult(
            service=str(service),
            window_minutes=minutes,
            line_count=len(lines),
            error_count=error_count,
            warn_count=warn_count,
            insights=parsed,
            model=model_id,
        )


def _parse_insights(raw: str) -> list[Insight]:
    import json
    import re

    # Strip code fences if the LLM wrapped its JSON
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return [
            Insight(
                severity="info",
                headline="LLM response unparseable",
                evidence=raw[:120],
            )
        ]
    out: list[Insight] = []
    for entry in (data.get("insights") or [])[:5]:
        sev = str(entry.get("severity", "info")).lower()
        if sev not in ("info", "warn", "critical"):
            sev = "info"
        out.append(
            Insight(
                severity=sev,  # type: ignore[arg-type]
                headline=str(entry.get("headline", ""))[:160],
                evidence=str(entry.get("evidence", ""))[:200],
            )
        )
    return out or [Insight(severity="info", headline="No notable patterns", evidence="")]


def _heuristic_insights(
    errors: int, warns: int, total: int, service: str, minutes: int
) -> list[Insight]:
    if errors > 10:
        return [
            Insight(
                severity="critical",
                headline=f"{errors} errors in {service} over {minutes}m — investigate now",
                evidence=f"{errors} ERROR/FATAL lines, {warns} warnings",
            )
        ]
    if errors > 0:
        return [
            Insight(
                severity="warn",
                headline=f"{errors} errors observed in {service}",
                evidence=f"{errors} errors / {total} total lines",
            )
        ]
    if warns > 5:
        return [
            Insight(
                severity="warn",
                headline=f"Elevated warnings ({warns}) on {service}",
                evidence=f"{warns} WARN lines",
            )
        ]
    return [
        Insight(
            severity="info",
            headline=f"{service} healthy — no errors in last {minutes}m",
            evidence=f"{total} log lines, 0 errors",
        )
    ]
