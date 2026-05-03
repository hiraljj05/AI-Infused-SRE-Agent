from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import cast

import structlog
from kubernetes_asyncio import client, config
from kubernetes_asyncio.client.api_client import ApiClient

from sre_agent.common.metrics import AUTOMATED_REMEDIATION, TOOL_INVOCATIONS
from sre_agent.domain.ports.k8s import (
    DeploymentInfo,
    KubernetesPort,
    PodEvent,
    PodInfo,
    PodPhase,
)
from sre_agent.domain.value_objects import PodIdentifier, ServiceName


log = structlog.get_logger(__name__)


class KubernetesAdapter(KubernetesPort):
    """Kubernetes adapter using the official async client.

    Configuration:
    - `in_cluster=True` uses the pod's ServiceAccount (production / Argo-deployed).
    - Otherwise falls back to kubeconfig (local dev with `kind` or `az aks get-credentials`).
    """

    def __init__(self, *, in_cluster: bool = False, kubeconfig: str | None = None) -> None:
        self._in_cluster = in_cluster
        self._kubeconfig = kubeconfig
        self._api_client: ApiClient | None = None

    async def _client(self) -> ApiClient:
        if self._api_client is None:
            if self._in_cluster:
                config.load_incluster_config()
            else:
                await config.load_kube_config(config_file=self._kubeconfig)
            self._api_client = ApiClient()
        return self._api_client

    async def _client_or_none(self) -> ApiClient | None:
        """Same as _client but returns None on missing/invalid kubeconfig instead of raising.

        Used by read-only operations (list_pods, get_recent_events) so the agent can run
        without K8s in local dev / unit tests.
        """
        try:
            return await self._client()
        except Exception as exc:
            log.warning("kubernetes unavailable, returning empty results", error=str(exc))
            return None

    async def close(self) -> None:
        if self._api_client is not None:
            await self._api_client.close()
            self._api_client = None

    async def list_pods(
        self, *, namespace: str, label_selector: str | None = None
    ) -> list[PodInfo]:
        cli = await self._client_or_none()
        if cli is None:
            return []
        api = client.CoreV1Api(cli)
        try:
            result = await api.list_namespaced_pod(
                namespace=namespace, label_selector=label_selector
            )
            TOOL_INVOCATIONS.labels(tool="list_pods", status="success").inc()
        except Exception:
            TOOL_INVOCATIONS.labels(tool="list_pods", status="error").inc()
            raise
        return [self._to_pod_info(p) for p in result.items]

    async def get_pod(self, pod: PodIdentifier) -> PodInfo | None:
        api = client.CoreV1Api(await self._client())
        try:
            p = await api.read_namespaced_pod(name=pod.name, namespace=pod.namespace)
            TOOL_INVOCATIONS.labels(tool="get_pod", status="success").inc()
            return self._to_pod_info(p)
        except client.ApiException as exc:
            if exc.status == 404:
                return None
            TOOL_INVOCATIONS.labels(tool="get_pod", status="error").inc()
            raise

    async def get_pod_logs(
        self, pod: PodIdentifier, *, tail_lines: int = 200, previous: bool = False
    ) -> str:
        api = client.CoreV1Api(await self._client())
        try:
            logs = await api.read_namespaced_pod_log(
                name=pod.name,
                namespace=pod.namespace,
                tail_lines=tail_lines,
                previous=previous,
            )
            TOOL_INVOCATIONS.labels(tool="get_pod_logs", status="success").inc()
            return cast(str, logs)
        except Exception:
            TOOL_INVOCATIONS.labels(tool="get_pod_logs", status="error").inc()
            raise

    async def get_recent_events(
        self, *, namespace: str, since_seconds: int = 600
    ) -> list[PodEvent]:
        api = client.CoreV1Api(await self._client())
        result = await api.list_namespaced_event(namespace=namespace)
        threshold = datetime.now(UTC).timestamp() - since_seconds
        events: list[PodEvent] = []
        for e in result.items:
            obj = e.involved_object
            if obj is None or obj.kind != "Pod":
                continue
            ts = (e.last_timestamp or e.event_time or e.first_timestamp)
            if ts is None or ts.timestamp() < threshold:
                continue
            events.append(
                PodEvent(
                    pod=PodIdentifier(namespace=obj.namespace or namespace, name=obj.name),
                    reason=e.reason or "",
                    message=e.message or "",
                    type_=e.type or "Normal",
                    at=ts,
                )
            )
        return events

    async def get_deployment(self, *, namespace: str, name: str) -> DeploymentInfo | None:
        api = client.AppsV1Api(await self._client())
        try:
            d = await api.read_namespaced_deployment(name=name, namespace=namespace)
        except client.ApiException as exc:
            if exc.status == 404:
                return None
            raise
        return self._to_deployment_info(d, namespace)

    async def restart_pod(self, pod: PodIdentifier, *, reason: str) -> str:
        api = client.CoreV1Api(await self._client())
        try:
            await api.delete_namespaced_pod(name=pod.name, namespace=pod.namespace)
            AUTOMATED_REMEDIATION.labels(action="restart_pod", outcome="success").inc()
            log.info("pod restarted", pod=pod.qualified, reason=reason)
            return f"pod {pod.qualified} delete requested; ReplicaSet will recreate"
        except Exception:
            AUTOMATED_REMEDIATION.labels(action="restart_pod", outcome="error").inc()
            raise

    async def scale_deployment(
        self, *, namespace: str, deployment: str, replicas: int, reason: str
    ) -> str:
        api = client.AppsV1Api(await self._client())
        body = {"spec": {"replicas": replicas}}
        try:
            await api.patch_namespaced_deployment_scale(
                name=deployment, namespace=namespace, body=body
            )
            AUTOMATED_REMEDIATION.labels(action="scale_deployment", outcome="success").inc()
            log.info(
                "deployment scaled",
                deployment=f"{namespace}/{deployment}",
                replicas=replicas,
                reason=reason,
            )
            return f"deployment {namespace}/{deployment} scaled to {replicas}"
        except Exception:
            AUTOMATED_REMEDIATION.labels(action="scale_deployment", outcome="error").inc()
            raise

    async def rollout_restart(
        self, *, namespace: str, deployment: str, reason: str
    ) -> str:
        api = client.AppsV1Api(await self._client())
        patch = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "sre-agent/restartedAt": datetime.now(UTC).isoformat(),
                            "sre-agent/reason": reason,
                        }
                    }
                }
            }
        }
        try:
            await api.patch_namespaced_deployment(
                name=deployment,
                namespace=namespace,
                body=patch,
                _content_type="application/strategic-merge-patch+json",
            )
            AUTOMATED_REMEDIATION.labels(action="rollout_restart", outcome="success").inc()
            return f"rollout restart of {namespace}/{deployment}"
        except Exception:
            AUTOMATED_REMEDIATION.labels(action="rollout_restart", outcome="error").inc()
            raise

    async def patch_resource_limit(
        self,
        *,
        namespace: str,
        deployment: str,
        container: str,
        resource: str,
        limit: str,
        reason: str,
    ) -> str:
        if resource not in ("memory", "cpu"):
            raise ValueError(f"resource must be memory|cpu, got {resource!r}")
        api = client.AppsV1Api(await self._client())
        patch = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {"name": container, "resources": {"limits": {resource: limit}}}
                        ]
                    }
                }
            }
        }
        try:
            await api.patch_namespaced_deployment(
                name=deployment,
                namespace=namespace,
                body=patch,
                _content_type="application/strategic-merge-patch+json",
            )
            AUTOMATED_REMEDIATION.labels(
                action=f"patch_{resource}_limit", outcome="success"
            ).inc()
            log.info(
                "resource limit patched",
                deployment=f"{namespace}/{deployment}",
                container=container,
                resource=resource,
                limit=limit,
                reason=reason,
            )
            return f"patched {resource} limit on {deployment}/{container} to {limit}"
        except Exception:
            AUTOMATED_REMEDIATION.labels(
                action=f"patch_{resource}_limit", outcome="error"
            ).inc()
            raise

    async def cordon_node(self, *, node: str, reason: str) -> str:
        api = client.CoreV1Api(await self._client())
        body = {"spec": {"unschedulable": True}}
        try:
            await api.patch_node(name=node, body=body)
            AUTOMATED_REMEDIATION.labels(action="cordon_node", outcome="success").inc()
            log.info("node cordoned", node=node, reason=reason)
            return f"node {node} cordoned"
        except Exception:
            AUTOMATED_REMEDIATION.labels(action="cordon_node", outcome="error").inc()
            raise

    async def taint_node(
        self, *, node: str, key: str, value: str, effect: str, reason: str
    ) -> str:
        if effect not in ("NoSchedule", "PreferNoSchedule", "NoExecute"):
            raise ValueError(f"invalid taint effect {effect!r}")
        api = client.CoreV1Api(await self._client())
        body = {"spec": {"taints": [{"key": key, "value": value, "effect": effect}]}}
        try:
            await api.patch_node(name=node, body=body)
            AUTOMATED_REMEDIATION.labels(action="taint_node", outcome="success").inc()
            log.info("node tainted", node=node, key=key, effect=effect, reason=reason)
            return f"node {node} tainted with {key}={value}:{effect}"
        except Exception:
            AUTOMATED_REMEDIATION.labels(action="taint_node", outcome="error").inc()
            raise

    async def rollback_deployment(
        self, *, namespace: str, deployment: str, revision: int | None, reason: str
    ) -> str:
        api = client.AppsV1Api(await self._client())
        try:
            current = await api.read_namespaced_deployment(name=deployment, namespace=namespace)
            patch = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "sre-agent/rollback-from-rev": str(
                                    (current.metadata.annotations or {}).get(
                                        "deployment.kubernetes.io/revision", "?"
                                    )
                                ),
                                "sre-agent/rollback-reason": reason,
                            }
                        }
                    }
                }
            }
            await api.patch_namespaced_deployment(
                name=deployment,
                namespace=namespace,
                body=patch,
                _content_type="application/strategic-merge-patch+json",
            )
            AUTOMATED_REMEDIATION.labels(action="rollback_deployment", outcome="success").inc()
            log.info(
                "deployment rollback annotated",
                deployment=f"{namespace}/{deployment}",
                revision=revision,
                reason=reason,
            )
            return f"rollback marker applied to {namespace}/{deployment}"
        except Exception:
            AUTOMATED_REMEDIATION.labels(action="rollback_deployment", outcome="error").inc()
            raise

    async def patch_image(
        self,
        *,
        namespace: str,
        deployment: str,
        container: str,
        image: str,
        reason: str,
    ) -> str:
        api = client.AppsV1Api(await self._client())
        patch = {
            "spec": {
                "template": {
                    "spec": {"containers": [{"name": container, "image": image}]}
                }
            }
        }
        try:
            await api.patch_namespaced_deployment(
                name=deployment,
                namespace=namespace,
                body=patch,
                _content_type="application/strategic-merge-patch+json",
            )
            AUTOMATED_REMEDIATION.labels(action="apply_patch", outcome="success").inc()
            log.info(
                "image patched",
                deployment=f"{namespace}/{deployment}",
                container=container,
                image=image,
                reason=reason,
            )
            return f"image patched on {deployment}/{container} -> {image}"
        except Exception:
            AUTOMATED_REMEDIATION.labels(action="apply_patch", outcome="error").inc()
            raise

    async def restart_statefulset(
        self, *, namespace: str, statefulset: str, reason: str
    ) -> str:
        api = client.AppsV1Api(await self._client())
        patch = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "sre-agent/restartedAt": datetime.now(UTC).isoformat(),
                            "sre-agent/reason": reason,
                        }
                    }
                }
            }
        }
        try:
            await api.patch_namespaced_stateful_set(
                name=statefulset,
                namespace=namespace,
                body=patch,
                _content_type="application/strategic-merge-patch+json",
            )
            AUTOMATED_REMEDIATION.labels(action="restart_statefulset", outcome="success").inc()
            return f"statefulset rollout {namespace}/{statefulset}"
        except Exception:
            AUTOMATED_REMEDIATION.labels(action="restart_statefulset", outcome="error").inc()
            raise

    async def delete_completed_jobs(self, *, namespace: str) -> str:
        batch_api = client.BatchV1Api(await self._client())
        try:
            jobs = await batch_api.list_namespaced_job(namespace=namespace)
            deleted = 0
            for j in jobs.items:
                conds = j.status.conditions or []
                if any(c.type == "Complete" and c.status == "True" for c in conds):
                    await batch_api.delete_namespaced_job(
                        name=j.metadata.name,
                        namespace=namespace,
                        propagation_policy="Background",
                    )
                    deleted += 1
            AUTOMATED_REMEDIATION.labels(
                action="delete_completed_jobs", outcome="success"
            ).inc()
            return f"deleted {deleted} completed job(s) in {namespace}"
        except Exception:
            AUTOMATED_REMEDIATION.labels(
                action="delete_completed_jobs", outcome="error"
            ).inc()
            raise

    async def exec_in_pod(
        self,
        *,
        pod: PodIdentifier,
        container: str | None,
        command: list[str],
    ) -> str:
        from kubernetes_asyncio.stream import WsApiClient  # noqa: PLC0415

        api = client.CoreV1Api(WsApiClient())
        try:
            output = await api.connect_get_namespaced_pod_exec(
                name=pod.name,
                namespace=pod.namespace,
                container=container,
                command=command,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
            )
            TOOL_INVOCATIONS.labels(tool="exec_in_pod", status="success").inc()
            return cast(str, output)
        except Exception:
            TOOL_INVOCATIONS.labels(tool="exec_in_pod", status="error").inc()
            raise

    async def recent_deployments_for(
        self, *, service: ServiceName, since_seconds: int = 3600
    ) -> list[DeploymentInfo]:
        cli = await self._client_or_none()
        if cli is None:
            return []
        api = client.AppsV1Api(cli)
        selector = f"app={service}"
        ns_api = client.CoreV1Api(cli)
        namespaces = await ns_api.list_namespace()
        threshold = datetime.now(UTC).timestamp() - since_seconds
        out: list[DeploymentInfo] = []
        for ns in namespaces.items:
            deploys = await api.list_namespaced_deployment(
                namespace=ns.metadata.name, label_selector=selector
            )
            for d in deploys.items:
                info = self._to_deployment_info(d, ns.metadata.name)
                if info.last_updated.timestamp() >= threshold:
                    out.append(info)
        return out

    @staticmethod
    def _to_pod_info(p: object) -> PodInfo:
        # p is V1Pod
        meta = getattr(p, "metadata", None)
        spec = getattr(p, "spec", None)
        status = getattr(p, "status", None)
        phase: PodPhase = cast(PodPhase, getattr(status, "phase", "Unknown") or "Unknown")
        container_statuses = getattr(status, "container_statuses", None) or []
        restart_count = sum(int(getattr(cs, "restart_count", 0) or 0) for cs in container_statuses)
        ready = all(bool(getattr(cs, "ready", False)) for cs in container_statuses) if container_statuses else False
        waiting_reasons = [
            getattr(getattr(cs, "state", None), "waiting", None) for cs in container_statuses
        ]
        if any(w and getattr(w, "reason", "") == "CrashLoopBackOff" for w in waiting_reasons):
            phase = "CrashLoopBackOff"
        containers = getattr(spec, "containers", None) or []
        image = getattr(containers[0], "image", "") if containers else ""
        node = getattr(spec, "node_name", "") if spec else ""
        started_at = getattr(status, "start_time", None)
        return PodInfo(
            identifier=PodIdentifier(
                namespace=getattr(meta, "namespace", "default"),
                name=getattr(meta, "name", "unknown"),
            ),
            phase=phase,
            ready=ready,
            restart_count=restart_count,
            image=image,
            node=node,
            started_at=started_at,
        )

    @staticmethod
    def _to_deployment_info(d: object, namespace: str) -> DeploymentInfo:
        meta = getattr(d, "metadata", None)
        spec = getattr(d, "spec", None)
        status = getattr(d, "status", None)
        annotations = getattr(meta, "annotations", {}) or {}
        revision_raw = annotations.get("deployment.kubernetes.io/revision", "1")
        try:
            revision = int(revision_raw)
        except (TypeError, ValueError):
            revision = 1
        # k8s python SDK returns V1DeploymentCondition objects (not dicts).
        # Use attribute access; fall back to created/now if absent.
        last_updated = None
        conditions = getattr(status, "conditions", None) or []
        if conditions:
            last_updated = getattr(conditions[-1], "last_update_time", None) or getattr(
                conditions[-1], "last_transition_time", None
            )
        if last_updated is None:
            last_updated = getattr(meta, "creation_timestamp", None)
        if not isinstance(last_updated, datetime):
            last_updated = datetime.now(UTC)
        return DeploymentInfo(
            namespace=namespace,
            name=getattr(meta, "name", "unknown"),
            replicas_desired=int(getattr(spec, "replicas", 0) or 0),
            replicas_ready=int(getattr(status, "ready_replicas", 0) or 0),
            revision=revision,
            last_updated=last_updated,
        )
