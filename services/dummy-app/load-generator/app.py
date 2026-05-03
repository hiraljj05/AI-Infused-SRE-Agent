from __future__ import annotations

import asyncio
import os
import random

import httpx
import structlog


TARGET = os.getenv("TARGET_URL", "http://web-frontend:8080/checkout")
RATE_RPS = float(os.getenv("RATE_RPS", "5"))
USERS = int(os.getenv("USERS", "50"))


log = structlog.get_logger("load-gen")


async def worker(client: httpx.AsyncClient, interval: float) -> None:
    while True:
        payload = {
            "user_id": f"u-{random.randint(1, USERS)}",
            "product_id": f"p-{random.randint(1, 20)}",
            "quantity": random.randint(1, 3),
        }
        try:
            r = await client.post(TARGET, json=payload, timeout=4.0)
            log.debug("request", status=r.status_code)
        except Exception as exc:
            log.warning("request-failed", error=str(exc))
        jitter = random.uniform(0.8, 1.2)
        await asyncio.sleep(interval * jitter)


async def main() -> None:
    concurrency = max(1, int(RATE_RPS))
    interval = concurrency / RATE_RPS
    async with httpx.AsyncClient() as client:
        await asyncio.gather(*[worker(client, interval) for _ in range(concurrency)])


if __name__ == "__main__":
    asyncio.run(main())
