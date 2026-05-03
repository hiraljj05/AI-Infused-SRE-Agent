from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from botbuilder.core import TurnContext
from botbuilder.schema import Activity

from sre_agent.interface.rest.dependencies import get_container


router = APIRouter(prefix="", tags=["bot"])


@router.post("/api/messages")
async def messages(request: Request, container=Depends(get_container)) -> Response:
    body = await request.json()
    auth_header = request.headers.get("Authorization", "")
    activity = Activity().deserialize(body)

    async def aux(turn_context: TurnContext) -> None:
        await request.app.state.bot.on_turn(turn_context)

    await container.teams_adapter.process_activity(activity, auth_header, aux)
    return Response(status_code=status.HTTP_200_OK)


@router.post("/internal/resume")
async def internal_resume(payload: dict[str, str], request: Request) -> Response:
    from sre_agent.domain.value_objects import IncidentId

    incident_id = IncidentId(value=payload["incident_id"])
    graph = request.app.state.compiled_graph
    container = request.app.state.container
    async with container.uow_factory() as uow:
        incident = await uow.incidents.get(incident_id)
    if incident is None:
        return Response(status_code=404)
    # Match the thread_id format used by /signals (start of agent run)
    thread_id = f"signal:{incident.service}"
    await graph.aupdate_state(
        config={"configurable": {"thread_id": thread_id}},
        values={"hil_decision": payload["decision"], "hil_actor": payload["actor"]},
    )

    import asyncio

    async def _continue() -> None:
        async for _ in graph.astream(None, config={"configurable": {"thread_id": thread_id}}):
            pass

    task: asyncio.Task[None] = asyncio.create_task(_continue())
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)
    return Response(status_code=200)
