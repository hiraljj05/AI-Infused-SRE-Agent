from __future__ import annotations

from typing import Any, Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from sre_agent.application.agent_graph.nodes import AgentNodes
from sre_agent.application.agent_graph.state import AgentState


def _route_after_propose(state: AgentState) -> Literal["notify_hil", "execute"]:
    return "notify_hil" if state.get("requires_hil", True) else "execute"


def _route_after_hil(state: AgentState) -> Literal["execute", "escalate"]:
    decision = state.get("hil_decision", "")
    if decision == "approve":
        return "execute"
    return "escalate"


def _route_after_verify(state: AgentState) -> Literal["postmortem", "gather", "escalate"]:
    if state.get("verification_to_baseline"):
        return "postmortem"
    notes = state.get("notes") or []
    retry_count = sum(1 for n in notes if n.startswith("verify to_baseline=False"))
    if retry_count >= 2:
        return "escalate"
    return "gather"


def _route_after_execute(state: AgentState) -> Literal["verify", "escalate"]:
    return "verify" if state.get("execution_success") else "escalate"


class AgentGraphFactory:
    """Builds the compiled LangGraph with an injected checkpointer. Holds no per-request state."""

    def __init__(self, nodes: AgentNodes) -> None:
        self._nodes = nodes

    def build(self, checkpointer: BaseCheckpointSaver) -> Any:
        g: StateGraph = StateGraph(AgentState)

        g.add_node("detect", self._nodes.detect_node)
        g.add_node("triage", self._nodes.triage_node)
        g.add_node("start_slas", self._nodes.start_slas_node)
        g.add_node("memory_lookup", self._nodes.memory_lookup_node)
        g.add_node("fan_out", self._nodes.fan_out_ticket_node)
        g.add_node("gather", self._nodes.gather_node)
        g.add_node("diagnose", self._nodes.diagnose_node)
        g.add_node("propose", self._nodes.propose_node)
        g.add_node("notify_hil", self._nodes.notify_hil_node)
        g.add_node("execute", self._nodes.execute_node)
        g.add_node("verify", self._nodes.verify_node)
        g.add_node("postmortem", self._nodes.postmortem_node)
        g.add_node("escalate", self._nodes.escalate_node)

        g.add_edge(START, "detect")
        g.add_edge("detect", "triage")
        g.add_edge("triage", "start_slas")
        g.add_edge("start_slas", "memory_lookup")
        g.add_edge("memory_lookup", "fan_out")
        g.add_edge("fan_out", "gather")
        g.add_edge("gather", "diagnose")
        g.add_edge("diagnose", "propose")
        g.add_conditional_edges("propose", _route_after_propose)
        g.add_conditional_edges("notify_hil", _route_after_hil)
        g.add_conditional_edges("execute", _route_after_execute)
        g.add_conditional_edges("verify", _route_after_verify)
        g.add_edge("postmortem", END)
        g.add_edge("escalate", END)

        return g.compile(
            checkpointer=checkpointer,
            # Pause AFTER notify_hil so the conditional that reads `hil_decision`
            # is only evaluated once a human has approved/rejected via the
            # /approvals/resolve (or bot card) → /internal/resume callback.
            # Without this, notify_hil runs synchronously and the conditional
            # sees an empty hil_decision, falling through to escalate → END.
            # interrupt_before=["execute"] is kept as defense-in-depth so a
            # non-HIL action also has a chance to be inspected if needed.
            interrupt_after=["notify_hil"],
            interrupt_before=["execute"],
        )
