"""Tiny Flask app that pretends to be a real product (portfolio site or food-ordering site).

Run two copies via docker-compose with different ENV:
  SERVICE_NAME    e.g. "portfolio-web", "food-orders"
  APP_KIND        "portfolio" | "food"
  SRE_AGENT_URL   e.g. "http://agent:8000"   (chaos endpoints push signals here)
"""
from __future__ import annotations

import logging
import os
import random
import sys
import threading
import time
from datetime import datetime
from typing import Any

import httpx
from flask import Flask, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

SERVICE_NAME = os.environ.get("SERVICE_NAME", "demo-svc")
APP_KIND = os.environ.get("APP_KIND", "portfolio")
SRE_AGENT_URL = os.environ.get("SRE_AGENT_URL", "http://agent:8000")
PORT = int(os.environ.get("PORT", "8080"))

# ── logging — single line per event, structured ish ───────────────────────
logging.basicConfig(
    level=logging.INFO,
    format=f"%(asctime)s %(levelname)s [{SERVICE_NAME}] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
    force=True,
)
log = logging.getLogger(SERVICE_NAME)

# ── prometheus metrics ────────────────────────────────────────────────────
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests",
    ["service", "route", "code"],
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["service", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
ERRORS = Counter("app_errors_total", "Application errors", ["service", "kind"])

# ── app state ─────────────────────────────────────────────────────────────
app = Flask(SERVICE_NAME)
_chaos_state: dict[str, Any] = {
    "extra_latency_ms": 0,
    "error_rate": 0.0,
    "memory_blob": None,  # holds large bytes when memory chaos is on
}


@app.before_request
def _start_timer() -> None:
    request.environ["X-START"] = time.time()


@app.after_request
def _record(resp):  # type: ignore[no-untyped-def]
    start = float(request.environ.get("X-START", time.time()))
    elapsed = time.time() - start
    route = (request.url_rule.rule if request.url_rule else request.path) or "unknown"
    HTTP_REQUESTS.labels(service=SERVICE_NAME, route=route, code=str(resp.status_code)).inc()
    HTTP_LATENCY.labels(service=SERVICE_NAME, route=route).observe(elapsed)
    log.info('%s %s %d %.3fs', request.method, request.path, resp.status_code, elapsed)
    return resp


def _maybe_chaos() -> None:
    """Apply current chaos config to a request — slow it down or fail it."""
    extra = _chaos_state.get("extra_latency_ms") or 0
    if extra:
        time.sleep(extra / 1000.0)
    rate = _chaos_state.get("error_rate") or 0.0
    if rate > 0 and random.random() < rate:
        ERRORS.labels(service=SERVICE_NAME, kind="chaos_500").inc()
        log.error("chaos: simulating 500 (error_rate=%.2f)", rate)
        from werkzeug.exceptions import InternalServerError

        raise InternalServerError("chaos: simulated upstream failure")


# ─────────────── PORTFOLIO ROUTES ─────────────────────────────────────────

PORTFOLIO_PROJECTS = [
    {"slug": "agentic-rag", "title": "Agentic RAG for legal docs", "stars": 412},
    {"slug": "kube-cost", "title": "kube-cost — k8s cost dashboard", "stars": 1284},
    {"slug": "incident-bot", "title": "Slack incident bot", "stars": 207},
]
BLOG_POSTS = [
    {"slug": "scaling-llm-eval", "title": "Scaling LLM evals to 10k cases", "claps": 482},
    {"slug": "k8s-finops", "title": "K8s FinOps without breaking devs", "claps": 211},
    {"slug": "rag-chunking", "title": "Chunking strategies for technical docs", "claps": 96},
]


@app.route("/")
def root_portfolio():
    if APP_KIND != "portfolio":
        return root_food()
    _maybe_chaos()
    log.info("homepage view referer=%s", request.headers.get("Referer", "-"))
    return jsonify(
        {
            "name": "Priyansh Tyagi",
            "headline": "Platform / SRE engineer",
            "projects": len(PORTFOLIO_PROJECTS),
            "posts": len(BLOG_POSTS),
        }
    )


@app.route("/about")
def about():
    _maybe_chaos()
    return jsonify({"bio": "AI/SRE engineer. Loves observability and small fast UIs."})


@app.route("/projects")
def projects():
    _maybe_chaos()
    log.info("projects.list count=%d", len(PORTFOLIO_PROJECTS))
    return jsonify({"projects": PORTFOLIO_PROJECTS})


@app.route("/blog/<slug>")
def blog_post(slug: str):
    _maybe_chaos()
    post = next((p for p in BLOG_POSTS if p["slug"] == slug), None)
    if not post:
        ERRORS.labels(service=SERVICE_NAME, kind="not_found").inc()
        log.warning("blog.not_found slug=%s", slug)
        return jsonify({"error": "not found"}), 404
    log.info("blog.view slug=%s claps=%d", slug, post["claps"])
    return jsonify(post)


@app.route("/contact", methods=["POST"])
def contact():
    _maybe_chaos()
    body = request.get_json(silent=True) or {}
    email = body.get("email", "?")
    log.info("contact.received from=%s", email)
    return jsonify({"ok": True}), 202


# ─────────────── FOOD-ORDERING ROUTES ─────────────────────────────────────

MENU = [
    {"id": "p1", "name": "Margherita pizza", "price": 9.5},
    {"id": "p2", "name": "Veggie burger", "price": 7.0},
    {"id": "p3", "name": "Caesar salad", "price": 6.5},
    {"id": "p4", "name": "Pad thai", "price": 11.0},
    {"id": "p5", "name": "Tiramisu", "price": 5.5},
]
_orders: list[dict[str, Any]] = []


def root_food():
    if APP_KIND != "food":
        return jsonify({"service": SERVICE_NAME, "kind": APP_KIND})
    _maybe_chaos()
    return jsonify(
        {"app": "FoodGo", "menu_size": len(MENU), "orders_today": len(_orders)}
    )


@app.route("/menu")
def menu():
    _maybe_chaos()
    log.info("menu.view items=%d", len(MENU))
    return jsonify({"items": MENU})


@app.route("/cart", methods=["GET", "POST"])
def cart():
    _maybe_chaos()
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        log.info("cart.add user=%s items=%s", body.get("user", "anon"), body.get("items", []))
        return jsonify({"ok": True, "cart_total": round(random.uniform(8, 45), 2)})
    return jsonify({"items": [], "total": 0})


@app.route("/checkout", methods=["POST"])
def checkout():
    _maybe_chaos()
    body = request.get_json(silent=True) or {}
    user = body.get("user", "anon")
    items = body.get("items", random.sample([m["id"] for m in MENU], k=2))
    total = round(sum(next(m["price"] for m in MENU if m["id"] == i) for i in items), 2)
    order_id = f"ord_{int(time.time()*1000)%1_000_000:06d}"
    _orders.append({"id": order_id, "user": user, "items": items, "total": total})
    log.info("order.placed id=%s user=%s items=%s total=$%.2f", order_id, user, items, total)
    if random.random() < 0.04:
        ERRORS.labels(service=SERVICE_NAME, kind="payment_decline").inc()
        log.warning("payment.declined order=%s reason=insufficient_funds", order_id)
    return jsonify({"order_id": order_id, "total": total, "status": "confirmed"}), 201


@app.route("/order/<order_id>")
def order(order_id: str):
    _maybe_chaos()
    o = next((o for o in _orders if o["id"] == order_id), None)
    if not o:
        ERRORS.labels(service=SERVICE_NAME, kind="not_found").inc()
        log.warning("order.not_found id=%s", order_id)
        return jsonify({"error": "not found"}), 404
    return jsonify(o)


# ─────────────── CHAOS ENDPOINTS ──────────────────────────────────────────


def _push_signal_to_agent(initial_signal: str) -> str | None:
    """Tell the SRE agent something is wrong with us. Returns incident id or None."""
    try:
        r = httpx.post(
            f"{SRE_AGENT_URL}/signals",
            json={
                "service": SERVICE_NAME,
                "initial_signal": initial_signal,
                "signal_sources": [f"chaos:{APP_KIND}"],
            },
            timeout=5.0,
        )
        if r.status_code in (200, 202):
            return r.json().get("incident_id", "pending")
        log.error("agent push failed status=%d body=%s", r.status_code, r.text[:200])
    except Exception as exc:
        log.error("agent push errored: %s", exc)
    return None


@app.route("/chaos/cpu", methods=["POST"])
def chaos_cpu():
    seconds = int(request.args.get("seconds", "5"))
    log.warning("CHAOS cpu burn seconds=%d — pegging worker", seconds)

    def _burn():
        end = time.time() + seconds
        while time.time() < end:
            pow(987654, 87654)  # busy work

    threading.Thread(target=_burn, daemon=True).start()
    incident_id = _push_signal_to_agent(f"CPU pegged at 100% on {SERVICE_NAME} ({seconds}s)")
    return jsonify(
        {"chaos": "cpu", "seconds": seconds, "incident_id": incident_id}
    )


@app.route("/chaos/memory", methods=["POST"])
def chaos_memory():
    mb = int(request.args.get("mb", "150"))
    log.error("CHAOS memory inflate mb=%d — heading toward OOM", mb)
    try:
        _chaos_state["memory_blob"] = bytearray(mb * 1024 * 1024)
    except MemoryError:
        log.error("OOMKill: memory blob refused")
    incident_id = _push_signal_to_agent(
        f"Memory usage spiking (+{mb}MB) on {SERVICE_NAME} — OOMKill risk"
    )
    return jsonify({"chaos": "memory", "mb": mb, "incident_id": incident_id})


@app.route("/chaos/latency", methods=["POST"])
def chaos_latency():
    ms = int(request.args.get("ms", "1500"))
    _chaos_state["extra_latency_ms"] = ms
    log.warning("CHAOS latency inflate ms=%d — every request now slower", ms)
    incident_id = _push_signal_to_agent(
        f"p99 latency above SLO on {SERVICE_NAME} — adding {ms}ms to every request"
    )
    return jsonify({"chaos": "latency", "added_ms": ms, "incident_id": incident_id})


@app.route("/chaos/errors", methods=["POST"])
def chaos_errors():
    rate = float(request.args.get("rate", "0.5"))
    _chaos_state["error_rate"] = max(0.0, min(rate, 1.0))
    log.error("CHAOS errors enabled rate=%.2f — random 500s incoming", rate)
    incident_id = _push_signal_to_agent(
        f"5xx error rate spiking on {SERVICE_NAME} (~{int(rate*100)}%)"
    )
    return jsonify({"chaos": "errors", "rate": rate, "incident_id": incident_id})


@app.route("/chaos/recover", methods=["POST"])
def chaos_recover():
    _chaos_state["extra_latency_ms"] = 0
    _chaos_state["error_rate"] = 0.0
    _chaos_state["memory_blob"] = None
    log.info("chaos: cleared all faults — back to normal")
    return jsonify({"recovered": True})


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "service": SERVICE_NAME, "kind": APP_KIND})


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


# ── background traffic generator (so logs/metrics flow continuously) ──────
def _traffic_loop() -> None:
    """Hit our own routes a few times per second so demo dashboards always have data."""
    time.sleep(3)
    if APP_KIND == "portfolio":
        endpoints = ["/", "/about", "/projects"] + [f"/blog/{p['slug']}" for p in BLOG_POSTS]
    else:
        endpoints = ["/", "/menu"] + [f"/order/ord_000000"]  # 404 occasionally
    counter = 0
    while True:
        try:
            counter += 1
            ep = random.choice(endpoints)
            httpx.get(f"http://localhost:{PORT}{ep}", timeout=3.0)
            if APP_KIND == "food" and counter % 7 == 0:
                httpx.post(
                    f"http://localhost:{PORT}/checkout",
                    json={"user": f"user{random.randint(1,500)}"},
                    timeout=3.0,
                )
            if APP_KIND == "portfolio" and counter % 11 == 0:
                httpx.post(
                    f"http://localhost:{PORT}/contact",
                    json={"email": f"visitor{random.randint(1,9999)}@example.com"},
                    timeout=3.0,
                )
        except Exception:
            pass
        time.sleep(random.uniform(0.5, 2.0))


def _start_background() -> None:
    if os.environ.get("DISABLE_TRAFFIC") != "1":
        t = threading.Thread(target=_traffic_loop, name="traffic", daemon=True)
        t.start()


_start_background()


if __name__ == "__main__":
    log.info(
        "%s booting kind=%s port=%d agent=%s",
        SERVICE_NAME,
        APP_KIND,
        PORT,
        SRE_AGENT_URL,
    )
    app.run(host="0.0.0.0", port=PORT, threaded=True)
