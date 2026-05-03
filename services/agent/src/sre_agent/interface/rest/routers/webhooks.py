from __future__ import annotations

import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request

from sre_agent.application.agent_graph.state import AgentState
from sre_agent.interface.rest.dependencies import get_container

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _kick_off_agent(request: Request, state: AgentState) -> None:
    """Background-task helper to start a graph run for a new signal."""
    graph = request.app.state.compiled_graph
    thread_config = {"configurable": {"thread_id": f"webhook:{state['service']}"}}

    async def _run() -> None:
        try:
            async for _ in graph.astream(state, config=thread_config):
                pass
        except Exception:
            log.exception("agent graph run failed", service=state["service"])

    task: asyncio.Task[None] = asyncio.create_task(_run())
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)


@router.post("/grafana")
async def grafana_alert(
    payload: dict[str, Any],
    request: Request,
    container=Depends(get_container),
) -> dict[str, Any]:
    """Receives Grafana Unified Alerting webhook payloads.

    Grafana >= 9 sends a payload with `alerts: [...]`. Each alert has labels and an
    annotations.summary. We extract the service, severity, and message, and trigger
    the agent flow per alert.
    """
    alerts = payload.get("alerts", [])
    started = 0
    for alert in alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        service = (
            labels.get("service")
            or labels.get("app")
            or labels.get("kubernetes_service_name")
            or "unknown"
        )
        signal = (
            annotations.get("summary")
            or annotations.get("description")
            or alert.get("name")
            or "Grafana alert fired"
        )
        namespace = labels.get("namespace") or container.settings.target_namespace
        if alert.get("status") == "resolved":
            log.info("grafana alert resolved (ignored)", service=service)
            continue
        state: AgentState = {
            "trigger": "grafana",
            "service": service,
            "initial_signal": str(signal)[:500],
            "signal_sources": ["grafana"],
            "namespace": namespace,
        }
        _kick_off_agent(request, state)
        started += 1
        log.info("grafana alert ingested", service=service, signal=signal[:100])
    return {"accepted": True, "signals_started": started, "total_alerts": len(alerts)}


@router.post("/azure-monitor")
async def azure_monitor_alert(
    payload: dict[str, Any],
    request: Request,
    container=Depends(get_container),
) -> dict[str, Any]:
    """Receives Azure Monitor common alert schema (or Event Grid) payloads.

    Schema reference: https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/alerts-common-schema
    """
    data = payload.get("data", payload)
    alert_ctx = data.get("essentials", data.get("data", {}))
    service = (
        alert_ctx.get("targetResourceType")
        or alert_ctx.get("alertTargetIDs", [""])[0].split("/")[-1]
        or "azure-resource"
    )
    signal = (
        alert_ctx.get("alertRule")
        or alert_ctx.get("description")
        or "Azure Monitor alert fired"
    )
    severity_map = {
        "Sev0": "P1",
        "Sev1": "P1",
        "Sev2": "P2",
        "Sev3": "P3",
        "Sev4": "P4",
    }
    namespace = container.settings.target_namespace
    state: AgentState = {
        "trigger": "azure-monitor",
        "service": str(service)[:64],
        "initial_signal": f"{signal} ({alert_ctx.get('severity', 'Sev2')})",
        "signal_sources": ["azure-monitor"],
        "namespace": namespace,
    }
    _kick_off_agent(request, state)
    log.info(
        "azure monitor alert ingested",
        service=state["service"],
        severity=alert_ctx.get("severity"),
    )
    return {"accepted": True}


@router.post("/elasticsearch")
async def elastic_alert(
    payload: dict[str, Any],
    request: Request,
    container=Depends(get_container),
) -> dict[str, Any]:
    """Generic webhook for Elasticsearch / Kibana watcher alerts.

    Accepts {service, signal, namespace?} or full Watcher payload with alert.attachments.
    """
    service = payload.get("service") or payload.get("watch_id", "elasticsearch-alert")
    signal = payload.get("signal") or payload.get("description") or "Elasticsearch alert fired"
    namespace = payload.get("namespace") or container.settings.target_namespace
    state: AgentState = {
        "trigger": "elasticsearch",
        "service": str(service)[:64],
        "initial_signal": str(signal)[:500],
        "signal_sources": ["elasticsearch"],
        "namespace": namespace,
    }
    _kick_off_agent(request, state)
    return {"accepted": True}
