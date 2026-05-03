from __future__ import annotations

import os
import time

import httpx
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel


PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://payments-api:8080")
SERVICE_NAME = "orders-api"

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


class OrderIn(BaseModel):
    order_id: str
    user_id: str
    product_id: str
    quantity: int


app = FastAPI(title=SERVICE_NAME)
app.mount("/metrics", make_asgi_app())


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.post("/orders")
async def create_order(payload: OrderIn) -> dict[str, object]:
    route = "/orders"
    code = "500"
    start = time.perf_counter()
    try:
        amount = payload.quantity * 1000
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(
                f"{PAYMENTS_URL}/charge",
                json={"order_id": payload.order_id, "user_id": payload.user_id, "amount_cents": amount},
            )
        if r.status_code >= 500:
            code = str(r.status_code)
            raise HTTPException(status_code=502, detail="payments service failed")
        code = "200"
        return {"order_id": payload.order_id, "status": "accepted", "payment": r.json()}
    finally:
        REQ_COUNT.labels(service=SERVICE_NAME, code=code, route=route).inc()
        REQ_LATENCY.labels(service=SERVICE_NAME, route=route).observe(time.perf_counter() - start)
