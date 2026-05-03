from __future__ import annotations

from dataclasses import dataclass

from sre_agent.domain.entities.incident import Incident
from sre_agent.domain.exceptions import GuardrailViolation, IncidentStateError
from sre_agent.domain.ports.k8s import KubernetesPort
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import IncidentId, PodIdentifier


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecuteFixInput:
    incident_id: IncidentId
    executed_by: str


class ExecuteFixUseCase:
    """Translates a ProposedAction into a concrete K8s operation.

    Only runs for pre-approved playbook actions. High-risk / irreversible actions have
    already been gated by HIL.
    """

    def __init__(self, *, uow: UnitOfWork, k8s: KubernetesPort) -> None:
        self._uow = uow
        self._k8s = k8s

    async def execute(self, input_: ExecuteFixInput) -> Incident:
        async with self._uow as uow:
            incident = await uow.incidents.get(input_.incident_id)
            if incident is None:
                raise IncidentStateError(f"Incident {input_.incident_id} not found")
            action = incident.proposed_action
            if action is None:
                raise IncidentStateError("Incident has no proposed action to execute")

            incident.start_execution()
            await uow.incidents.save(incident)
            await uow.commit()

        try:
            output = await self._dispatch(action.name, action.parameters)
            success = True
        except GuardrailViolation:
            raise
        except Exception as exc:
            output = f"execution error: {exc}"
            success = False

        async with self._uow as uow:
            incident = await uow.incidents.get(input_.incident_id)
            if incident is None:
                raise IncidentStateError("Incident disappeared between lock and write")
            incident.record_execution_result(
                success=success, output=output, executed_by=input_.executed_by
            )
            await uow.incidents.save(incident)
            await uow.events.append(incident.drain_events())
            await uow.commit()
            return incident

    async def _dispatch(self, name: str, params: dict[str, str]) -> str:
        from sre_agent.domain.value_objects import ACTIONS, SAFE_KUBECTL_VERBS

        if name not in ACTIONS:
            raise GuardrailViolation(f"Unknown action {name!r}")
        reason = "sre-agent remediation"

        if name == "restart_pod":
            pod = PodIdentifier(namespace=params["namespace"], name=params["pod_name"])
            return await self._k8s.restart_pod(pod, reason=reason)
        if name == "rollout_restart":
            return await self._k8s.rollout_restart(
                namespace=params["namespace"],
                deployment=params["deployment"],
                reason=reason,
            )
        if name == "scale_deployment":
            return await self._k8s.scale_deployment(
                namespace=params["namespace"],
                deployment=params["deployment"],
                replicas=int(params["replicas"]),
                reason=reason,
            )
        if name == "patch_memory_limit":
            return await self._k8s.patch_resource_limit(
                namespace=params["namespace"],
                deployment=params["deployment"],
                container=params["container"],
                resource="memory",
                limit=params["limit"],
                reason=reason,
            )
        if name == "patch_cpu_limit":
            return await self._k8s.patch_resource_limit(
                namespace=params["namespace"],
                deployment=params["deployment"],
                container=params["container"],
                resource="cpu",
                limit=params["limit"],
                reason=reason,
            )
        if name == "cordon_node":
            return await self._k8s.cordon_node(node=params["node"], reason=reason)
        if name == "taint_node":
            return await self._k8s.taint_node(
                node=params["node"],
                key=params["key"],
                value=params.get("value", ""),
                effect=params.get("effect", "NoSchedule"),
                reason=reason,
            )
        if name == "rollback_deployment":
            rev_str = params.get("revision", "")
            revision = int(rev_str) if rev_str.isdigit() else None
            return await self._k8s.rollback_deployment(
                namespace=params["namespace"],
                deployment=params["deployment"],
                revision=revision,
                reason=reason,
            )
        if name == "apply_patch":
            return await self._k8s.patch_image(
                namespace=params["namespace"],
                deployment=params["deployment"],
                container=params["container"],
                image=params["image"],
                reason=reason,
            )
        if name == "restart_statefulset":
            return await self._k8s.restart_statefulset(
                namespace=params["namespace"],
                statefulset=params["statefulset"],
                reason=reason,
            )
        if name == "delete_completed_jobs":
            return await self._k8s.delete_completed_jobs(namespace=params["namespace"])
        if name in ("exec_into_pod", "kubectl_exec"):
            cmd_str = params.get("command", "") or params.get("args", "")
            tokens = cmd_str.split()
            if not tokens:
                raise GuardrailViolation(f"{name}: empty command")
            verb = tokens[0]
            if name == "kubectl_exec" and verb not in SAFE_KUBECTL_VERBS:
                raise GuardrailViolation(
                    f"kubectl verb {verb!r} not in safe allow-list {sorted(SAFE_KUBECTL_VERBS)}"
                )
            if name == "exec_into_pod":
                pod = PodIdentifier(namespace=params["namespace"], name=params["pod_name"])
                return await self._k8s.exec_in_pod(
                    pod=pod, container=params.get("container"), command=tokens
                )
            # kubectl_exec: log only for safety, do not actually invoke arbitrary kubectl
            return f"(read-only) would run: kubectl {cmd_str}"
        if name in ("flush_cache", "clear_redis_eviction", "drain_connections"):
            # Non-K8s side effects; in V2 this would call service admin endpoints
            return f"(stub) executed {name} with params {params}"
        if name == "delete_pvc":
            raise GuardrailViolation(
                "delete_pvc requires incident commander (CRITICAL); not auto-executable"
            )
        if name == "no_op_escalate":
            return "escalated - no automated action taken"
        raise GuardrailViolation(
            f"Action {name} not yet wired in dispatcher"
        )
