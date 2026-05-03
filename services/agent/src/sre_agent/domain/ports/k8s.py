from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from sre_agent.domain.value_objects import PodIdentifier, ServiceName


PodPhase = Literal["Pending", "Running", "Succeeded", "Failed", "Unknown", "CrashLoopBackOff"]


@dataclass(frozen=True, slots=True, kw_only=True)
class PodInfo:
    identifier: PodIdentifier
    phase: PodPhase
    ready: bool
    restart_count: int
    image: str
    node: str
    started_at: datetime | None


@dataclass(frozen=True, slots=True, kw_only=True)
class PodEvent:
    pod: PodIdentifier
    reason: str
    message: str
    type_: str
    at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class DeploymentInfo:
    namespace: str
    name: str
    replicas_desired: int
    replicas_ready: int
    revision: int
    last_updated: datetime


class KubernetesPort(Protocol):
    async def list_pods(self, *, namespace: str, label_selector: str | None = None) -> list[PodInfo]:
        ...

    async def get_pod(self, pod: PodIdentifier) -> PodInfo | None:
        ...

    async def get_pod_logs(
        self, pod: PodIdentifier, *, tail_lines: int = 200, previous: bool = False
    ) -> str:
        ...

    async def get_recent_events(
        self, *, namespace: str, since_seconds: int = 600
    ) -> list[PodEvent]:
        ...

    async def get_deployment(self, *, namespace: str, name: str) -> DeploymentInfo | None:
        ...

    async def restart_pod(self, pod: PodIdentifier, *, reason: str) -> str:
        ...

    async def scale_deployment(
        self, *, namespace: str, deployment: str, replicas: int, reason: str
    ) -> str:
        ...

    async def rollout_restart(
        self, *, namespace: str, deployment: str, reason: str
    ) -> str:
        ...

    async def recent_deployments_for(
        self, *, service: ServiceName, since_seconds: int = 3600
    ) -> list[DeploymentInfo]:
        ...

    # P4 extended toolkit
    async def patch_resource_limit(
        self,
        *,
        namespace: str,
        deployment: str,
        container: str,
        resource: str,  # "memory" | "cpu"
        limit: str,
        reason: str,
    ) -> str:
        ...

    async def cordon_node(self, *, node: str, reason: str) -> str:
        ...

    async def taint_node(
        self, *, node: str, key: str, value: str, effect: str, reason: str
    ) -> str:
        ...

    async def rollback_deployment(
        self, *, namespace: str, deployment: str, revision: int | None, reason: str
    ) -> str:
        ...

    async def patch_image(
        self,
        *,
        namespace: str,
        deployment: str,
        container: str,
        image: str,
        reason: str,
    ) -> str:
        ...

    async def restart_statefulset(
        self, *, namespace: str, statefulset: str, reason: str
    ) -> str:
        ...

    async def delete_completed_jobs(self, *, namespace: str) -> str:
        ...

    async def exec_in_pod(
        self,
        *,
        pod: PodIdentifier,
        container: str | None,
        command: list[str],
    ) -> str:
        ...
