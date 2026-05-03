from __future__ import annotations

from dataclasses import dataclass

from sre_agent.application.use_cases.detect_incident import (
    DetectIncidentCommand,
    DetectIncidentUseCase,
)
from sre_agent.application.use_cases.diagnose_incident import (
    DiagnoseIncidentUseCase,
    DiagnoseInput,
)
from sre_agent.application.use_cases.gather_evidence import GatherEvidenceUseCase
from sre_agent.application.use_cases.propose_remediation import (
    ProposeRemediationInput,
    ProposeRemediationUseCase,
)
from sre_agent.application.use_cases.triage_incident import (
    TriageIncidentUseCase,
    TriageInput,
)
from sre_agent.domain.entities.incident import Incident, IncidentStatus
from sre_agent.domain.value_objects import IncidentId, ServiceName


@dataclass(frozen=True, slots=True, kw_only=True)
class RunInvestigationCommand:
    service: ServiceName
    namespace: str
    requested_by: str  # user identity
    propose_remediation: bool = True


@dataclass(slots=True, kw_only=True)
class InvestigationResult:
    incident: Incident
    evidence_summary: str
    proposed_action_name: str | None
    proposed_action_requires_hil: bool


class RunOnDemandInvestigationUseCase:
    """Triggered from the chatbot when a user asks "what's wrong with X?".

    Reuses the same pipeline as the autonomous flow — just doesn't auto-execute.
    """

    def __init__(
        self,
        *,
        detect: DetectIncidentUseCase,
        triage: TriageIncidentUseCase,
        gather: GatherEvidenceUseCase,
        diagnose: DiagnoseIncidentUseCase,
        propose: ProposeRemediationUseCase,
    ) -> None:
        self._detect = detect
        self._triage = triage
        self._gather = gather
        self._diagnose = diagnose
        self._propose = propose

    async def execute(self, command: RunInvestigationCommand) -> InvestigationResult:
        incident = await self._detect.execute(
            DetectIncidentCommand(
                service=command.service,
                initial_signal=f"on-demand investigation requested by {command.requested_by}",
                signal_sources=("chat", command.requested_by),
            )
        )

        # Idempotent: only triage if still in DETECTED state
        if incident.status == IncidentStatus.DETECTED:
            incident = await self._triage.execute(
                TriageInput(
                    incident_id=incident.id,
                    observed_error_rate=0.1,
                    observed_latency_p99_ms=500,
                    estimated_users_affected=100,
                )
            )

        # Idempotent: only gather if not already past diagnosis
        if incident.status in (IncidentStatus.TRIAGED, IncidentStatus.DIAGNOSING):
            evidence = await self._gather.execute(
                incident_id=incident.id, namespace=command.namespace
            )
        else:
            # Already diagnosed; build minimal evidence package
            from sre_agent.application.use_cases.gather_evidence import GatheredEvidence

            evidence = GatheredEvidence(incident=incident)
        evidence_summary = GatherEvidenceUseCase.summarize_for_llm(evidence)

        if incident.status == IncidentStatus.DIAGNOSING:
            incident = await self._diagnose.execute(
                DiagnoseInput(incident_id=incident.id, evidence=evidence)
            )

        action_name: str | None = None
        requires_hil: bool = False
        if command.propose_remediation and incident.status == IncidentStatus.DIAGNOSING:
            incident = await self._propose.execute(
                ProposeRemediationInput(
                    incident_id=incident.id,
                    evidence_summary=evidence_summary,
                    namespace=command.namespace,
                )
            )
        if incident.proposed_action is not None:
            action_name = incident.proposed_action.name
            requires_hil = incident.proposed_action.requires_hil

        return InvestigationResult(
            incident=incident,
            evidence_summary=evidence_summary,
            proposed_action_name=action_name,
            proposed_action_requires_hil=requires_hil,
        )
