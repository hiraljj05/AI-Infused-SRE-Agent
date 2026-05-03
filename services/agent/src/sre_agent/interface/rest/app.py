from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import PlainTextResponse

from sre_agent.common.config import get_settings
from sre_agent.common.logging import configure_logging
from sre_agent.common.tracing import configure_tracing
from sre_agent.composition_root import build_container, open_checkpointer
from sre_agent.interface.bot.bot_handler import SREAgentBot
from sre_agent.interface.rest.routers import (
    advisor,
    apps,
    approvals,
    chat,
    close_incident,
    cost,
    events,
    health,
    incidents,
    insights,
    k8s_chaos,
    lessons,
    logs,
    people,
    postmortems,
    projects,
    reports,
    signals,
    sla,
    webhooks,
)
from sre_agent.interface.rest.routers import bot as bot_router
from sre_agent.interface.rest.auth import router as auth_router


KNOWLEDGE_BASE_DEFAULT = Path(__file__).resolve().parents[5] / "knowledge_base"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing(
        endpoint=settings.otel_exporter_otlp_endpoint or None,
        service_name=settings.otel_service_name,
        attrs=settings.otel_resource_attributes,
    )

    kb_root = Path(__import__("os").environ.get("KNOWLEDGE_BASE_ROOT", str(KNOWLEDGE_BASE_DEFAULT)))
    container = build_container(settings=settings, knowledge_base_root=kb_root)
    app.state.container = container
    app.state.background_tasks = set()

    await container.knowledge.ensure_collection()
    await container.lessons_vec.ensure_collection()

    checkpointer = await open_checkpointer(settings)
    app.state.checkpointer = checkpointer
    app.state.compiled_graph = container.agent_graph_factory.build(checkpointer)

    api_base = f"http://localhost:{settings.http_port}"
    app.state.bot = SREAgentBot(
        refs=container.conversation_refs,
        answer_query=container.answer_query_uc,
        resolve_approval=container.resolve_approval_uc,
        api_base_url=api_base,
    )

    async def _on_approval_dead_letter(approval) -> None:  # type: ignore[no-untyped-def]
        """When the saga gives up paging humans, unblock the LangGraph thread.

        Without this, the graph stays paused at `interrupt_after=["notify_hil"]`
        and the incident sits in `awaiting_approval` forever. Routing to
        `escalate` (via `_route_after_hil`) flips the incident to ESCALATED.
        """
        async with container.uow_factory() as uow:
            incident = await uow.incidents.get(approval.incident_id)
        if incident is None:
            return
        thread_id = f"signal:{incident.service}"
        graph = app.state.compiled_graph
        try:
            await graph.aupdate_state(
                config={"configurable": {"thread_id": thread_id}},
                values={"hil_decision": "timeout", "hil_actor": "system"},
            )

            async def _continue() -> None:
                async for _ in graph.astream(
                    None, config={"configurable": {"thread_id": thread_id}}
                ):
                    pass

            task: asyncio.Task[None] = asyncio.create_task(_continue())
            app.state.background_tasks.add(task)
            task.add_done_callback(app.state.background_tasks.discard)
        except Exception:
            import structlog

            structlog.get_logger(__name__).exception(
                "failed to resume graph on dead-letter",
                approval_id=str(approval.id),
                incident_id=str(approval.incident_id),
            )

    container.saga.set_dead_letter_callback(_on_approval_dead_letter)

    container.saga.start()
    container.sla_monitor.start()
    container.digest_scheduler.start()
    container.insights_monitor.start()
    container.jira_status_poller.start()

    try:
        yield
    finally:
        await container.saga.stop()
        await container.sla_monitor.stop()
        await container.digest_scheduler.stop()
        await container.insights_monitor.stop()
        await container.jira_status_poller.stop()
        for task in list(app.state.background_tasks):
            task.cancel()
        if app.state.background_tasks:
            await asyncio.gather(*app.state.background_tasks, return_exceptions=True)
        await container.metrics.close()
        await container.logs.close()
        await container.k8s.close()
        await container.grafana.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="SRE Agent API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3030",
            "http://localhost:3000",
            "http://127.0.0.1:3030",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(signals.router)
    app.include_router(incidents.router)
    app.include_router(approvals.router)
    app.include_router(chat.router)
    app.include_router(projects.router)
    app.include_router(apps.router)
    app.include_router(close_incident.router)
    app.include_router(webhooks.router)
    app.include_router(lessons.router)
    app.include_router(people.router)
    app.include_router(cost.router)
    app.include_router(reports.router)
    app.include_router(postmortems.router)
    app.include_router(advisor.router)
    app.include_router(logs.router)
    app.include_router(sla.router)
    app.include_router(events.router)
    app.include_router(insights.router)
    app.include_router(k8s_chaos.router)
    app.include_router(auth_router)
    app.include_router(bot_router.router)

    @app.get("/metrics", response_class=PlainTextResponse)
    async def prometheus_metrics() -> str:
        return generate_latest().decode()

    return app


app = create_app()
