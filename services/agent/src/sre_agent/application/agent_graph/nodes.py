from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sre_agent.application.agent_graph.state import AgentState, approval_id_from, incident_id_from
from sre_agent.application.use_cases.create_incident_ticket import (
    CreateIncidentTicketCommand,
    CreateIncidentTicketUseCase,
)
from sre_agent.application.use_cases.detect_incident import DetectIncidentCommand, DetectIncidentUseCase
from sre_agent.application.use_cases.diagnose_incident import DiagnoseIncidentUseCase, DiagnoseInput
from sre_agent.application.use_cases.execute_fix import ExecuteFixInput, ExecuteFixUseCase
from sre_agent.application.use_cases.gather_evidence import GatheredEvidence, GatherEvidenceUseCase
from sre_agent.application.use_cases.generate_postmortem import (
    GeneratePostmortemInput,
    GeneratePostmortemUseCase,
)
from sre_agent.application.use_cases.propose_remediation import (
    ProposeRemediationInput,
    ProposeRemediationUseCase,
)
from sre_agent.application.use_cases.request_approval import (
    RequestApprovalInput,
    RequestApprovalUseCase,
)
from sre_agent.application.use_cases.find_similar_incidents import (
    FindSimilarCommand,
    FindSimilarIncidentsUseCase,
)
from sre_agent.application.use_cases.start_sla_trackers import (
    SatisfySLAUseCase,
    StartSLATrackersCommand,
    StartSLATrackersUseCase,
)
from sre_agent.application.use_cases.triage_incident import TriageIncidentUseCase, TriageInput
from sre_agent.domain.entities.sla_tracker import SLAType
from sre_agent.application.use_cases.verify_resolution import (
    VerifyResolutionInput,
    VerifyResolutionUseCase,
)
from sre_agent.domain.entities.incident import IncidentStatus
from sre_agent.domain.value_objects import ServiceName


@dataclass(kw_only=True)
class AgentNodes:
    """Groups all LangGraph node callables.

    LangGraph checkpoints state to Postgres, so the state must be JSON-serializable.
    Large non-serializable objects (raw evidence) are cached in memory keyed by
    incident_id; their summary (a string) is persisted in state.
    """

    uow_factory: Any
    detect: DetectIncidentUseCase
    triage: TriageIncidentUseCase
    gather: GatherEvidenceUseCase
    diagnose: DiagnoseIncidentUseCase
    propose: ProposeRemediationUseCase
    request_approval: RequestApprovalUseCase
    execute: ExecuteFixUseCase
    verify: VerifyResolutionUseCase
    postmortem: GeneratePostmortemUseCase
    create_ticket: CreateIncidentTicketUseCase
    start_slas: StartSLATrackersUseCase
    satisfy_sla: SatisfySLAUseCase
    find_similar: FindSimilarIncidentsUseCase
    ticketing: Any = None  # TicketingPort — used to transition Jira on auto-resolve
    evidence_cache: dict[str, GatheredEvidence] | None = None
    ticket_index: dict[str, str] | None = None  # incident_id -> ticket_key

    def __post_init__(self) -> None:
        if self.evidence_cache is None:
            self.evidence_cache = {}
        if self.ticket_index is None:
            self.ticket_index = {}

    async def detect_node(self, state: AgentState) -> AgentState:
        incident = await self.detect.execute(
            DetectIncidentCommand(
                service=ServiceName(state["service"]),
                initial_signal=state["initial_signal"],
                signal_sources=tuple(state.get("signal_sources", [])),
            )
        )
        return {"incident_id": str(incident.id), "notes": [f"detected {incident.id}"]}

    async def triage_node(self, state: AgentState) -> AgentState:
        incident = await self.triage.execute(
            TriageInput(
                incident_id=incident_id_from(state),
                observed_error_rate=0.3,
                observed_latency_p99_ms=1200,
                estimated_users_affected=500,
            )
        )
        return {"notes": [f"triaged severity={incident.severity}"]}

    async def start_slas_node(self, state: AgentState) -> AgentState:
        trackers = await self.start_slas.execute(
            StartSLATrackersCommand(incident_id=incident_id_from(state))
        )
        # Auto-ack: agent created and dispatched the ticket → ack SLA satisfied
        await self.satisfy_sla.execute(
            incident_id=incident_id_from(state), sla_type=SLAType.ACK
        )
        return {"notes": [f"sla trackers started ({len(trackers)})", "sla:ack auto-satisfied"]}

    async def memory_lookup_node(self, state: AgentState) -> AgentState:
        result = await self.find_similar.execute(
            FindSimilarCommand(incident_id=incident_id_from(state), limit=3)
        )
        notes: list[str] = []
        if not result.matches:
            return {"notes": ["memory: no similar past incidents"]}
        for m in result.matches:
            notes.append(
                f"memory: similar lesson {m.lesson.id} "
                f"({m.similarity:.2f}) - {m.lesson.issue_category.value}"
            )
        if result.confident_match and result.top_match is not None:
            notes.append(
                f"memory: HIGH-confidence prior fix: {result.top_match.lesson.fix_applied[:80]}"
            )
        return {"notes": notes}

    async def fan_out_ticket_node(self, state: AgentState) -> AgentState:
        result = await self.create_ticket.execute(
            CreateIncidentTicketCommand(incident_id=incident_id_from(state))
        )
        notes: list[str] = []
        if result.ticket is not None:
            assert self.ticket_index is not None
            self.ticket_index[state["incident_id"]] = result.ticket.key
            notes.append(f"ticket {result.ticket.key} created")
        if result.email_sent:
            notes.append("email dispatched")
        if result.teams_posted:
            notes.append("teams posted")
        for w in result.warnings:
            notes.append(f"warn: {w}")
        return {"notes": notes or ["fan-out: no channels delivered"]}

    async def gather_node(self, state: AgentState) -> AgentState:
        evidence = await self.gather.execute(
            incident_id=incident_id_from(state), namespace=state["namespace"]
        )
        summary = GatherEvidenceUseCase.summarize_for_llm(evidence)
        assert self.evidence_cache is not None
        self.evidence_cache[state["incident_id"]] = evidence
        return {"evidence_summary": summary}

    async def diagnose_node(self, state: AgentState) -> AgentState:
        assert self.evidence_cache is not None
        evidence = self.evidence_cache.get(state["incident_id"])
        if evidence is None:
            return {"errors": ["evidence missing in cache - re-run gather"]}
        incident = await self.diagnose.execute(
            DiagnoseInput(incident_id=incident_id_from(state), evidence=evidence)
        )
        top = incident.top_hypothesis
        # RCA SLA satisfied
        await self.satisfy_sla.execute(
            incident_id=incident_id_from(state), sla_type=SLAType.RCA
        )
        return {
            "top_rca": top.description if top else "",
            "top_rca_confidence": top.confidence.value if top else 0.0,
            "notes": [f"RCA: {top.description if top else 'none'}", "sla:rca satisfied"],
        }

    async def propose_node(self, state: AgentState) -> AgentState:
        incident = await self.propose.execute(
            ProposeRemediationInput(
                incident_id=incident_id_from(state),
                evidence_summary=state.get("evidence_summary", ""),
                namespace=state["namespace"],
            )
        )
        action = incident.proposed_action
        assert action is not None
        return {
            "proposed_action_name": action.name,
            "requires_hil": action.requires_hil,
            "notes": [f"proposed {action.name} requires_hil={action.requires_hil}"],
        }

    async def notify_hil_node(self, state: AgentState) -> AgentState:
        approval = await self.request_approval.execute(
            RequestApprovalInput(incident_id=incident_id_from(state))
        )
        return {"approval_id": str(approval.id), "notes": [f"HIL requested {approval.id}"]}

    async def execute_node(self, state: AgentState) -> AgentState:
        incident = await self.execute.execute(
            ExecuteFixInput(
                incident_id=incident_id_from(state),
                executed_by=state.get("hil_actor") or "agent",
            )
        )
        success = incident.status != IncidentStatus.FAILED
        return {"execution_success": success, "notes": [f"execute success={success}"]}

    async def verify_node(self, state: AgentState) -> AgentState:
        incident = await self.verify.execute(
            VerifyResolutionInput(incident_id=incident_id_from(state), wait_seconds=30)
        )
        to_baseline = incident.status == IncidentStatus.RESOLVED
        if to_baseline:
            await self.satisfy_sla.execute(
                incident_id=incident_id_from(state), sla_type=SLAType.RESOLVE
            )
        return {
            "verification_to_baseline": to_baseline,
            "notes": [
                f"verify to_baseline={to_baseline}",
                "sla:resolve satisfied" if to_baseline else "sla:resolve still open",
            ],
        }

    async def postmortem_node(self, state: AgentState) -> AgentState:
        pm = await self.postmortem.execute(
            GeneratePostmortemInput(incident_id=incident_id_from(state))
        )
        # clear evidence cache once incident closed
        assert self.evidence_cache is not None
        self.evidence_cache.pop(state["incident_id"], None)

        # Transition the linked Jira ticket to Done, best-effort.
        notes = [f"postmortem {pm.id} drafted"]
        ticket_key: str | None = None
        if self.ticket_index is not None:
            ticket_key = self.ticket_index.get(state["incident_id"])
        if ticket_key and self.ticketing is not None:
            try:
                await self.ticketing.transition_to_resolved(
                    ticket_key,
                    resolution="Resolved by SRE agent (auto-verified after remediation)",
                )
                notes.append(f"jira:{ticket_key} transitioned to Done")
            except Exception as exc:  # noqa: BLE001
                notes.append(f"jira:{ticket_key} transition failed: {exc!s}"[:120])
        return {"postmortem_id": pm.id, "notes": notes}

    async def escalate_node(self, state: AgentState) -> AgentState:
        _ = approval_id_from(state) if state.get("approval_id") else None
        decision = state.get("hil_decision") or "no-decision"
        actor = state.get("hil_actor") or "system"
        if decision == "reject":
            reason = f"rejected by {actor}"
        elif decision == "timeout":
            reason = f"approval timed out (last actor: {actor})"
        else:
            reason = (
                "verification failed after retries"
                if state.get("execution_success") is False or state.get("verification_to_baseline") is False
                else f"escalated ({decision})"
            )

        incident_id = incident_id_from(state)
        async with self.uow_factory() as uow:
            incident = await uow.incidents.get(incident_id)
            if incident is not None and incident.status != IncidentStatus.ESCALATED:
                incident.escalate(reason=reason)
                await uow.incidents.save(incident)
                await uow.events.append(incident.drain_events())
                await uow.commit()

        return {"notes": [f"escalated to incident commander ({reason})"]}
