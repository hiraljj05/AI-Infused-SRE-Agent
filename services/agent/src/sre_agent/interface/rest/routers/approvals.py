from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from sre_agent.application.use_cases.resolve_approval import ResolveApprovalCommand
from sre_agent.common.config import get_settings
from sre_agent.domain.entities.approval import ApprovalDecision
from sre_agent.domain.exceptions import ApprovalStateError
from sre_agent.domain.value_objects import ApprovalId, IncidentId
from sre_agent.interface.rest.auth import Identity, require_identity
from sre_agent.interface.rest.dependencies import get_container
from sre_agent.interface.rest.schemas.incidents import approval_to_view
from sre_agent.interface.rest.schemas.resolve import ResolveApprovalIn, ResolveApprovalOut


router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/resolve", response_model=ResolveApprovalOut)
async def resolve_approval(
    body: ResolveApprovalIn,
    request: Request,
    container=Depends(get_container),
    identity: Identity = Depends(require_identity),
) -> ResolveApprovalOut:
    if get_settings().auth_required and not identity.has_role("responder"):
        raise HTTPException(
            403,
            f"approval requires 'responder' role; you have {list(identity.roles)}",
        )
    actor = identity.email if identity.email != "anonymous@local" else body.actor
    try:
        approval = await container.resolve_approval_uc.execute(
            ResolveApprovalCommand(
                approval_id=ApprovalId(value=body.approval_id),
                decision=ApprovalDecision(body.decision),
                actor=actor,
                reason=body.reason,
                modifications=body.modifications,
            )
        )
    except ApprovalStateError as exc:
        raise HTTPException(409, str(exc)) from exc

    if approval.decision == ApprovalDecision.APPROVE:
        await _resume_graph(request, incident_id=approval.incident_id, decision="approve", actor=actor)
    elif approval.decision == ApprovalDecision.REJECT:
        await _resume_graph(request, incident_id=approval.incident_id, decision="reject", actor=actor)

    return ResolveApprovalOut(
        approval_id=approval.id.value,
        state=approval.state.value,
        finalized=approval.is_finalized,
    )


@router.get("")
async def list_approvals(
    container=Depends(get_container),
) -> list[dict[str, object]]:
    """Open / pending approvals — used by the HIL Queue page."""
    async with container.uow_factory() as uow:
        approvals = await uow.approvals.list_open()
        out: list[dict[str, object]] = []
        for ap in approvals:
            incident = await uow.incidents.get(ap.incident_id)
            view = approval_to_view(ap).model_dump(mode="json")
            view["incident_id"] = ap.incident_id.value
            view["service"] = str(incident.service) if incident else None
            view["severity"] = (
                incident.severity.value if incident and incident.severity else None
            )
            view["initial_signal"] = incident.initial_signal if incident else None
            view["proposed_action_name"] = (
                incident.proposed_action.name
                if incident and incident.proposed_action
                else None
            )
            view["action_rationale"] = (
                incident.proposed_action.rationale
                if incident and incident.proposed_action
                else None
            )
            view["blast_radius"] = (
                incident.proposed_action.blast_radius.level.value
                if incident and incident.proposed_action
                else None
            )
            top = incident.top_hypothesis if incident else None
            view["top_rca"] = top.description if top else None
            view["top_rca_confidence"] = top.confidence.value if top else None
            out.append(view)
        return out


@router.get("/{approval_id}")
async def get_approval(
    approval_id: str,
    container=Depends(get_container),
) -> dict[str, object]:
    async with container.uow_factory() as uow:
        approval = await uow.approvals.get(ApprovalId(value=approval_id))
    if approval is None:
        raise HTTPException(404, f"approval {approval_id} not found")
    return approval_to_view(approval).model_dump(mode="json")


async def _resume_graph(
    request: Request, *, incident_id: IncidentId, decision: str, actor: str
) -> None:
    graph = request.app.state.compiled_graph
    # The graph was started with thread_id `signal:<service>` (from /signals).
    # Look up the service from the incident so we resume the SAME thread —
    # using a different thread_id would create a new (empty) checkpoint and crash.
    container = request.app.state.container
    async with container.uow_factory() as uow:
        incident = await uow.incidents.get(incident_id)
    if incident is None:
        return
    thread_id = f"signal:{incident.service}"
    await graph.aupdate_state(
        config={"configurable": {"thread_id": thread_id}},
        values={"hil_decision": decision, "hil_actor": actor},
    )

    async def _continue() -> None:
        async for _ in graph.astream(None, config={"configurable": {"thread_id": thread_id}}):
            pass

    import asyncio

    task: asyncio.Task[None] = asyncio.create_task(_continue())
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)
