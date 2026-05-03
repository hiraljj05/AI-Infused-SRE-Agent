from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionClass(str, Enum):
    """Risk class drives HIL routing and approval level required."""

    LOW = "low"  # auto-execute (e.g., restart_pod, flush_cache)
    MEDIUM = "medium"  # HIL-2 (primary on-call)
    HIGH = "high"  # HIL-2 (primary or commander)
    CRITICAL = "critical"  # HIL-2 + commander only

    @property
    def requires_hil(self) -> bool:
        return self != ActionClass.LOW

    @property
    def commander_only(self) -> bool:
        return self == ActionClass.CRITICAL


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionDefinition:
    name: str
    cls: ActionClass
    description: str
    parameters: tuple[str, ...]


# The single source of truth for what the agent is allowed to attempt.
ACTIONS: dict[str, ActionDefinition] = {
    # LOW (auto-executable)
    "restart_pod": ActionDefinition(
        name="restart_pod",
        cls=ActionClass.LOW,
        description="Delete a pod; ReplicaSet recreates it.",
        parameters=("namespace", "pod_name"),
    ),
    "rollout_restart": ActionDefinition(
        name="rollout_restart",
        cls=ActionClass.LOW,
        description="Roll the deployment by patching its template annotation.",
        parameters=("namespace", "deployment"),
    ),
    "flush_cache": ActionDefinition(
        name="flush_cache",
        cls=ActionClass.LOW,
        description="Hit cache flush endpoint on the service (no K8s mutation).",
        parameters=("namespace", "service"),
    ),
    "clear_redis_eviction": ActionDefinition(
        name="clear_redis_eviction",
        cls=ActionClass.LOW,
        description="Run a redis-cli FLUSHDB on the eviction queue (read-replica safe).",
        parameters=("namespace", "redis_pod"),
    ),
    "drain_connections": ActionDefinition(
        name="drain_connections",
        cls=ActionClass.LOW,
        description="Send SIGTERM to graceful-drain a single replica.",
        parameters=("namespace", "pod_name"),
    ),
    "delete_completed_jobs": ActionDefinition(
        name="delete_completed_jobs",
        cls=ActionClass.LOW,
        description="Garbage-collect Completed Jobs in a namespace.",
        parameters=("namespace",),
    ),
    # MEDIUM (HIL required)
    "scale_deployment": ActionDefinition(
        name="scale_deployment",
        cls=ActionClass.MEDIUM,
        description="Scale a deployment to N replicas.",
        parameters=("namespace", "deployment", "replicas"),
    ),
    "patch_memory_limit": ActionDefinition(
        name="patch_memory_limit",
        cls=ActionClass.MEDIUM,
        description="Patch container memory limit on a deployment.",
        parameters=("namespace", "deployment", "container", "limit"),
    ),
    "patch_cpu_limit": ActionDefinition(
        name="patch_cpu_limit",
        cls=ActionClass.MEDIUM,
        description="Patch container CPU limit on a deployment.",
        parameters=("namespace", "deployment", "container", "limit"),
    ),
    "cordon_node": ActionDefinition(
        name="cordon_node",
        cls=ActionClass.MEDIUM,
        description="Mark a node unschedulable (no eviction).",
        parameters=("node",),
    ),
    "restart_statefulset": ActionDefinition(
        name="restart_statefulset",
        cls=ActionClass.MEDIUM,
        description="Roll restart a StatefulSet (one pod at a time).",
        parameters=("namespace", "statefulset"),
    ),
    "apply_patch": ActionDefinition(
        name="apply_patch",
        cls=ActionClass.MEDIUM,
        description="Bump the container image to a new tag (cure flow validates afterward).",
        parameters=("namespace", "deployment", "container", "image"),
    ),
    # HIGH (HIL required, blast radius matters)
    "rollback_deployment": ActionDefinition(
        name="rollback_deployment",
        cls=ActionClass.HIGH,
        description="Roll back a deployment to a previous revision.",
        parameters=("namespace", "deployment", "revision"),
    ),
    "failover_to_replica": ActionDefinition(
        name="failover_to_replica",
        cls=ActionClass.HIGH,
        description="Promote a read-replica to primary.",
        parameters=("namespace", "primary_service", "replica_service"),
    ),
    "exec_into_pod": ActionDefinition(
        name="exec_into_pod",
        cls=ActionClass.HIGH,
        description="Read-only command inside a pod (allow-listed verbs).",
        parameters=("namespace", "pod_name", "command"),
    ),
    "kubectl_exec": ActionDefinition(
        name="kubectl_exec",
        cls=ActionClass.HIGH,
        description="Generic kubectl command from an allow-list (NOT for delete/rm).",
        parameters=("verb", "args"),
    ),
    "taint_node": ActionDefinition(
        name="taint_node",
        cls=ActionClass.HIGH,
        description="Apply a taint to evict pods from a node.",
        parameters=("node", "key", "value", "effect"),
    ),
    # CRITICAL (incident commander only, irreversible)
    "delete_pvc": ActionDefinition(
        name="delete_pvc",
        cls=ActionClass.CRITICAL,
        description="Delete a PersistentVolumeClaim. Data loss possible.",
        parameters=("namespace", "pvc_name"),
    ),
    # No-op
    "no_op_escalate": ActionDefinition(
        name="no_op_escalate",
        cls=ActionClass.LOW,
        description="No automated action; escalate to a human.",
        parameters=(),
    ),
}


# Whitelist of safe verbs allowed by `kubectl_exec` and `exec_into_pod`.
SAFE_KUBECTL_VERBS = frozenset({"get", "describe", "logs", "top", "version", "explain"})
SAFE_POD_EXEC_PROGRAMS = frozenset(
    {"ls", "cat", "ps", "df", "free", "uptime", "env", "whoami", "id", "echo", "head", "tail"}
)
