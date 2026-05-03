from __future__ import annotations

import json
import os
from dataclasses import dataclass

from sre_agent.domain.entities.incident import Incident, ProposedAction
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.ports.knowledge import KnowledgePort
from sre_agent.domain.ports.llm import LLMMessage, LLMPort
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import (
    BlastRadius,
    BlastRadiusLevel,
    ConfidenceScore,
    IncidentId,
)


from sre_agent.domain.value_objects import ACTIONS

ALLOWED_ACTIONS: set[str] = set(ACTIONS.keys())


PLAN_SYSTEM_PROMPT = """You are an SRE remediation planner. Given the top RCA hypothesis and retrieved runbooks,
propose ONE remediation action from the allowed list. Be conservative: prefer 'no_op_escalate' if the
RCA confidence is below 0.7 or if the fix is destructive unless runbooks explicitly recommend it.

Allowed actions (each will be HIL-gated by risk class — propose the right one regardless):

LOW (auto-executable; preferred for transient issues):
  - restart_pod         {"namespace","pod_name"}
  - rollout_restart     {"namespace","deployment"}
  - flush_cache         {"namespace","service"}
  - clear_redis_eviction {"namespace","redis_pod"}
  - drain_connections   {"namespace","pod_name"}
  - delete_completed_jobs {"namespace"}

MEDIUM (HIL approval needed):
  - scale_deployment    {"namespace","deployment","replicas"}
  - patch_memory_limit  {"namespace","deployment","container","limit"}
  - patch_cpu_limit     {"namespace","deployment","container","limit"}
  - cordon_node         {"node"}
  - restart_statefulset {"namespace","statefulset"}
  - apply_patch         {"namespace","deployment","container","image"}

HIGH (HIL approval needed; consider blast radius):
  - rollback_deployment {"namespace","deployment","revision"}
  - failover_to_replica {"namespace","primary_service","replica_service"}
  - exec_into_pod       {"namespace","pod_name","command"}  // read-only verbs only (ls, cat, ps, df, head, tail)
  - kubectl_exec        {"verb","args"}                     // verb in (get, describe, logs, top, version)
  - taint_node          {"node","key","value","effect"}

CRITICAL (commander only; data loss possible):
  - delete_pvc          {"namespace","pvc_name"}

ESCALATION:
  - no_op_escalate {}

PATTERN-SPECIFIC GUIDANCE (apply BEFORE picking from the menu above):
  - OOM / memory chaos:
    If the signal/RCA mentions "OOMKilled", "memory limit reduced", "exit code 137",
    or container memory at/below 32Mi: ALWAYS propose `patch_memory_limit` with
    parameters {"namespace","deployment","container":"app","limit":"256Mi"}.
    Reason: restart_pod cannot fix an OOM caused by an undersized memory limit —
    only restoring the limit will. Use the deployment's name (e.g. "food-orders")
    not a pod name. blast_radius_level should be "medium".

  - CPU throttle chaos:
    If the signal/RCA mentions "CPU throttle", "cpu limit reduced", "p99 latency
    spike from cpu", or container CPU limit at/below 10m: ALWAYS propose
    `patch_cpu_limit` with parameters
    {"namespace","deployment","container":"app","limit":"500m"}.
    Reason: rollout_restart will NOT clear the underlying low CPU limit;
    only patching the limit back to baseline restores throughput.
    blast_radius_level should be "medium".

  - Scale-to-zero / outage chaos:
    If the signal/RCA mentions "scaled to 0", "all pods gone", "deployment has 0
    replicas", "full outage", or current replicas == 0: ALWAYS propose
    `scale_deployment` with parameters
    {"namespace","deployment","replicas":"2"}.
    Reason: there is nothing to restart when replicas=0; only scaling back up
    restores the service. blast_radius_level should be "medium".

Return JSON matching the schema. blast_radius_level should reflect the action's true blast radius.
"""


PLAN_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["action_name", "parameters", "rationale", "confidence", "blast_radius_level"],
    "properties": {
        "action_name": {"type": "string", "enum": sorted(ALLOWED_ACTIONS)},
        "parameters": {"type": "object"},
        "rationale": {"type": "string", "minLength": 10},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "blast_radius_level": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
    },
}


@dataclass(frozen=True, slots=True, kw_only=True)
class ProposeRemediationInput:
    incident_id: IncidentId
    evidence_summary: str
    namespace: str


class ProposeRemediationUseCase:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        llm: LLMPort,
        knowledge: KnowledgePort,
    ) -> None:
        self._uow = uow
        self._llm = llm
        self._knowledge = knowledge

    async def execute(self, input_: ProposeRemediationInput) -> Incident:
        async with self._uow as uow:
            incident = await uow.incidents.get(input_.incident_id)
            if incident is None:
                raise IncidentStateError(f"Incident {input_.incident_id} not found")

            top = incident.top_hypothesis
            if top is None:
                raise IncidentStateError("Incident has no RCA yet; cannot propose remediation")

            runbooks = await self._knowledge.search(
                query=top.description,
                kinds=("runbook",),
                service=incident.service,
                limit=3,
            )
            runbook_block = "\n\n".join(
                f"[{r.id}] {r.title}\n{r.content[:600]}" for r in runbooks
            ) or "(no runbooks matched)"

            user_prompt = (
                f"Service: {incident.service}\n"
                f"Severity: {incident.severity}\n"
                f"Top RCA (confidence {top.confidence}): {top.description}\n"
                f"Supporting evidence: {'; '.join(top.supporting_evidence)}\n"
                f"Namespace: {input_.namespace}\n\n"
                f"# Runbooks\n{runbook_block}\n\n"
                f"# Evidence\n{input_.evidence_summary}\n\n"
                "Propose exactly one remediation action."
            )

            response = await self._llm.complete_structured(
                messages=[
                    LLMMessage(role="system", content=PLAN_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=user_prompt),
                ],
                json_schema=PLAN_JSON_SCHEMA,
                temperature=0.1,
                max_tokens=600,
            )
            data = response.structured or json.loads(response.content)

            action_name = data["action_name"]
            if action_name not in ALLOWED_ACTIONS:
                raise IncidentStateError(f"LLM returned disallowed action: {action_name}")

            parameters = {str(k): str(v) for k, v in data.get("parameters", {}).items()}
            confidence = ConfidenceScore(float(data["confidence"]))

            level = BlastRadiusLevel(data["blast_radius_level"])
            action_blast = BlastRadius(
                level=level,
                affected_services=incident.blast_radius.affected_services if incident.blast_radius else (str(incident.service),),
                estimated_users_affected=incident.blast_radius.estimated_users_affected if incident.blast_radius else 0,
                estimated_downtime_seconds=30 if action_name == "restart_pod" else 60,
                reversible=action_name != "rollback_deployment",
            )

            requires_hil = action_blast.requires_hil or not confidence.is_actionable or action_name in {
                "rollback_deployment",
                "cordon_node",
                "scale_deployment",
            }
            # Demo override — force every action through the HIL approval flow so the
            # primary→secondary→commander escalation chain is observable end-to-end.
            if os.environ.get("DEMO_FORCE_HIL", "").lower() in ("1", "true", "yes"):
                requires_hil = True

            proposed = ProposedAction(
                name=action_name,
                parameters=parameters,
                rationale=data["rationale"],
                blast_radius=action_blast,
                confidence=confidence,
                requires_hil=requires_hil,
            )
            incident.propose_action(proposed)
            await uow.incidents.save(incident)
            await uow.events.append(incident.drain_events())
            await uow.commit()
            return incident
