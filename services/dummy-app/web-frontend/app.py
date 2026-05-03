from __future__ import annotations

import os
import time
import uuid

import httpx
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel


ORDERS_URL = os.getenv("ORDERS_URL", "http://orders-api:8080")
SERVICE_NAME = "web-frontend"


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


class CheckoutIn(BaseModel):
    user_id: str
    product_id: str
    quantity: int = 1


app = FastAPI(title=SERVICE_NAME)
app.mount("/metrics", make_asgi_app())


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": SERVICE_NAME, "version": os.getenv("VERSION", "0.1.0")}


@app.post("/checkout")
async def checkout(payload: CheckoutIn) -> dict[str, object]:
    start = time.perf_counter()
    route = "/checkout"
    code = "500"
    try:
        order_id = str(uuid.uuid4())
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                f"{ORDERS_URL}/orders",
                json={
                    "order_id": order_id,
                    "user_id": payload.user_id,
                    "product_id": payload.product_id,
                    "quantity": payload.quantity,
                },
            )
        if resp.status_code >= 500:
            code = str(resp.status_code)
            raise HTTPException(status_code=502, detail="orders service failed")
        code = "200"
        return {"order_id": order_id, "orders_response": resp.json()}
    finally:
        REQ_COUNT.labels(service=SERVICE_NAME, code=code, route=route).inc()
        REQ_LATENCY.labels(service=SERVICE_NAME, route=route).observe(time.perf_counter() - start)
