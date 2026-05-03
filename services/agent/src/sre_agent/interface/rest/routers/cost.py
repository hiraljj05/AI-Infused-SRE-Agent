from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sre_agent.interface.rest.dependencies import get_container

router = APIRouter(prefix="/api/cost", tags=["cost"])


# Rough USD-per-1M-tokens for common OpenRouter models (prompt+completion blended).
# These estimates only — for an exact figure use OpenRouter's billing dashboard.
_MODEL_USD_PER_M_TOKENS: dict[str, float] = {
    "anthropic/claude-sonnet-4.5": 3.0,
    "anthropic/claude-sonnet-4": 3.0,
    "anthropic/claude-3.5-sonnet": 3.0,
    "anthropic/claude-3-opus": 15.0,
    "anthropic/claude-3-haiku": 0.25,
    "openai/gpt-4o": 5.0,
    "openai/gpt-4o-mini": 0.15,
    "default": 3.0,
}


class ModelBreakdown(BaseModel):
    model: str
    tokens: int
    usd: float


class DayBreakdown(BaseModel):
    day: str
    tokens: int


class CostBreakdown(BaseModel):
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    estimated_usd: float
    by_model: list[ModelBreakdown]
    by_day: list[DayBreakdown]
    source: str  # "prometheus" or "estimate"
    notes: str


def _estimate_usd(model: str, tokens: int) -> float:
    rate = _MODEL_USD_PER_M_TOKENS.get(model, _MODEL_USD_PER_M_TOKENS["default"])
    return round(tokens / 1_000_000 * rate, 4)


@router.get("/llm-tokens", response_model=CostBreakdown)
async def llm_token_cost(container=Depends(get_container)) -> CostBreakdown:
    """Aggregates LLM token usage from Prometheus counters."""
    settings = container.settings
    prom_url = settings.prometheus_url.rstrip("/")
    notes = ""

    by_model: dict[str, dict[str, int]] = {}
    by_day: dict[str, int] = {}
    prompt_total = 0
    completion_total = 0
    source = "prometheus"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{prom_url}/api/v1/query",
                params={"query": "sum by (model, kind) (sre_agent_llm_tokens_used_total)"},
            )
            r.raise_for_status()
            body = r.json()
            for sample in body.get("data", {}).get("result", []):
                metric = sample.get("metric", {})
                model = metric.get("model", "unknown")
                kind = metric.get("kind", "unknown")
                value = int(float(sample.get("value", [0, "0"])[1]))
                by_model.setdefault(model, {"prompt": 0, "completion": 0, "total": 0})
                if kind == "prompt":
                    by_model[model]["prompt"] += value
                    prompt_total += value
                elif kind == "completion":
                    by_model[model]["completion"] += value
                    completion_total += value
                by_model[model]["total"] += value

            now = datetime.now(UTC)
            start = now - timedelta(days=7)
            r2 = await client.get(
                f"{prom_url}/api/v1/query_range",
                params={
                    "query": "sum(increase(sre_agent_llm_tokens_used_total[1d]))",
                    "start": start.timestamp(),
                    "end": now.timestamp(),
                    "step": "86400",
                },
            )
            r2.raise_for_status()
            body2 = r2.json()
            for series in body2.get("data", {}).get("result", []):
                for ts, val in series.get("values", []):
                    day = datetime.fromtimestamp(float(ts), tz=UTC).strftime("%Y-%m-%d")
                    by_day[day] = by_day.get(day, 0) + int(float(val))
    except Exception as exc:
        source = "estimate"
        notes = f"Prometheus unreachable ({type(exc).__name__}); showing zeros."

    by_model_out = [
        ModelBreakdown(
            model=m,
            tokens=v["total"],
            usd=_estimate_usd(m, v["total"]),
        )
        for m, v in by_model.items()
    ]
    by_model_out.sort(key=lambda x: x.tokens, reverse=True)

    by_day_out = [DayBreakdown(day=d, tokens=t) for d, t in sorted(by_day.items())]

    total_tokens = prompt_total + completion_total
    estimated_usd = round(sum(m.usd for m in by_model_out), 4)

    return CostBreakdown(
        total_tokens=total_tokens,
        prompt_tokens=prompt_total,
        completion_tokens=completion_total,
        estimated_usd=estimated_usd,
        by_model=by_model_out,
        by_day=by_day_out,
        source=source,
        notes=notes,
    )
