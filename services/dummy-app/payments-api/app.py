from __future__ import annotations

import asyncio
import os
import random
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel


SERVICE_NAME = "payments-api"
FAILURE_FLAG_PATH = Path(os.getenv("FAILURE_FLAG_PATH", "/tmp/payments-fail"))
LATENCY_FLAG_PATH = Path(os.getenv("LATENCY_FLAG_PATH", "/tmp/payments-slow"))

REQ_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=("service", "code", "route"),
)
REQ_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    labelnames=("service", "route"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


class ChargeIn(BaseModel):
    order_id: str
    user_id: str
    amount_cents: int


app = FastAPI(title=SERVICE_NAME)
app.mount("/metrics", make_asgi_app())


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.post("/charge")
async def charge(payload: ChargeIn) -> dict[str, object]:
    route = "/charge"
    code = "500"
    start = time.perf_counter()
    try:
        if LATENCY_FLAG_PATH.exists():
            await asyncio.sleep(random.uniform(1.0, 2.5))
        if FAILURE_FLAG_PATH.exists():
            code = "503"
            raise HTTPException(status_code=503, detail="payment processor unavailable (simulated)")
        # success path: ~5% natural flakiness for realism
        if random.random() < 0.02:
            code = "500"
            raise HTTPException(status_code=500, detail="random transient error")
        code = "200"
        return {
            "order_id": payload.order_id,
            "user_id": payload.user_id,
            "amount_cents": payload.amount_cents,
            "status": "charged",
        }
    finally:
        REQ_COUNT.labels(service=SERVICE_NAME, code=code, route=route).inc()
        REQ_LATENCY.labels(service=SERVICE_NAME, route=route).observe(time.perf_counter() - start)


# Runtime fault control (for local dev / Chaos UI without K8s)
@app.post("/_admin/fail")
async def enable_failure() -> dict[str, str]:
    FAILURE_FLAG_PATH.touch()
    return {"status": "failure_mode_enabled"}


@app.post("/_admin/heal")
async def disable_failure() -> dict[str, str]:
    FAILURE_FLAG_PATH.unlink(missing_ok=True)
    LATENCY_FLAG_PATH.unlink(missing_ok=True)
    return {"status": "healthy"}


@app.post("/_admin/slow")
async def enable_slow() -> dict[str, str]:
    LATENCY_FLAG_PATH.touch()
    return {"status": "latency_mode_enabled"}
