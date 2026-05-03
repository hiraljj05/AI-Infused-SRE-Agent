from __future__ import annotations

from typing import Annotated, Any, TypedDict

from sre_agent.domain.value_objects import ApprovalId, IncidentId


def _replace_scalar(_old: Any, new: Any) -> Any:
    return new


def _extend_list(old: list[Any] | None, new: list[Any] | None) -> list[Any]:
    return (old or []) + (new or [])


class AgentState(TypedDict, total=False):
    """LangGraph state. Annotations supply reducers for concurrent updates."""

    trigger: Annotated[str, _replace_scalar]
    service: Annotated[str, _replace_scalar]
    initial_signal: Annotated[str, _replace_scalar]
    signal_sources: Annotated[list[str], _extend_list]
    namespace: Annotated[str, _replace_scalar]
    incident_id: Annotated[str, _replace_scalar]
    approval_id: Annotated[str, _replace_scalar]
    evidence_summary: Annotated[str, _replace_scalar]
    top_rca: Annotated[str, _replace_scalar]
    top_rca_confidence: Annotated[float, _replace_scalar]
    proposed_action_name: Annotated[str, _replace_scalar]
    requires_hil: Annotated[bool, _replace_scalar]
    hil_decision: Annotated[str, _replace_scalar]  # approve|reject|timeout
    hil_actor: Annotated[str, _replace_scalar]
    execution_success: Annotated[bool, _replace_scalar]
    verification_to_baseline: Annotated[bool, _replace_scalar]
    postmortem_id: Annotated[str, _replace_scalar]
    errors: Annotated[list[str], _extend_list]
    notes: Annotated[list[str], _extend_list]


def incident_id_from(state: AgentState) -> IncidentId:
    return IncidentId(value=state["incident_id"])


def approval_id_from(state: AgentState) -> ApprovalId:
    return ApprovalId(value=state["approval_id"])
