from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, Depends, Request

from sre_agent.application.agent_graph.state import AgentState
from sre_agent.interface.rest.dependencies import get_container
from sre_agent.interface.rest.schemas.detect import DetectSignalIn, DetectSignalOut


log = structlog.get_logger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("", response_model=DetectSignalOut, status_code=202)
async def receive_signal(
    body: DetectSignalIn,
    request: Request,
    container=Depends(get_container),
) -> DetectSignalOut:
    namespace = body.namespace or container.settings.target_namespace
    state: AgentState = {
        "trigger": "signal",
        "service": body.service,
        "initial_signal": body.initial_signal,
        "signal_sources": body.signal_sources,
        "namespace": namespace,
    }

    graph = request.app.state.compiled_graph
    thread_config = {"configurable": {"thread_id": f"signal:{body.service}"}}

    async def _run() -> None:
        try:
            async for _ in graph.astream(state, config=thread_config):
                pass
        except Exception:
            log.exception("agent graph run failed", service=body.service)

    task: asyncio.Task[None] = asyncio.create_task(_run())
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)

    return DetectSignalOut(
        incident_id="pending",
        status="accepted",
        started_agent_run=True,
    )
