"""Real Kubernetes chaos endpoints — patches the live AKS cluster so pods actually
crash. Each endpoint also POSTs to /signals so the agent picks up the resulting
incident, gathers real evidence (restart counts, exit codes, OOMKills) and proposes
a real fix that runs `kubectl patch` against the cluster on approval.

These are POST-only and gated to the configured `target_namespace` to prevent
accidental changes outside the demo blast radius.
"""
from __future__ import annotations

import asyncio

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from sre_agent.interface.rest.dependencies import get_container

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/k8s-chaos", tags=["k8s-chaos"])

# Healthy defaults to restore to, per service. Matches our demo deployment YAML.
HEALTHY_DEFAULTS = {
    "memory": "256Mi",
    "cpu": "500m",
    "replicas": 2,
}


async def _push_signal(agent_url: str, service: str, signal: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{agent_url}/signals",
                json={
                    "service": service,
                    "initial_signal": signal,
                    "signal_sources": ["chaos:k8s"],
                },
            )
            if r.status_code in (200, 202):
                return r.json().get("incident_id", "pending")
    except Exception:
        log.exception("k8s chaos: signal push failed")
    return None


def _agent_self_url(container) -> str:
    # Inside the agent container, /signals is at http://localhost:8000.
    # We're calling our own REST API.
    port = container.settings.http_port or 8000
    return f"http://localhost:{port}"


async def _patch_resources_directly(
    container,
    *,
    deployment: str,
    namespace: str,
    container_name: str = "app",
    requests: dict | None = None,
    limits: dict | None = None,
) -> str:
    """Patch a deployment's container resources atomically (both requests + limits)
    so K8s doesn't reject the change for breaking the requests<=limits invariant."""
    from kubernetes_asyncio import client

    api = client.AppsV1Api(await container.k8s._client())
    resources: dict = {}
    if requests:
        resources["requests"] = requests
    if limits:
        resources["limits"] = limits
    body = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [{"name": container_name, "resources": resources}]
                }
            }
        }
    }
    await api.patch_namespaced_deployment(
        name=deployment,
        namespace=namespace,
        body=body,
    )
    return f"patched {namespace}/{deployment} resources={resources}"


@router.post("/oom")
async def chaos_oom(
    service: str = Query(..., description="App name (must match a registered AKS deployment)"),
    memory: str = Query("8Mi", description="Tiny memory limit to cause OOMKill (e.g. 8Mi)"),
    container=Depends(get_container),
):
    """Patch the deployment's container memory request+limit to a value below the
    container's actual working set, then push a signal so the agent picks it up.
    Pods will OOMKill within seconds; restart_count climbs; exit code 137.
    """
    ns = container.settings.target_namespace or "demo"
    try:
        # Set BOTH request and limit to satisfy K8s validation (requests <= limits).
        result = await _patch_resources_directly(
            container,
            deployment=service,
            namespace=ns,
            requests={"memory": memory},
            limits={"memory": memory},
        )
    except Exception as exc:
        raise HTTPException(500, f"failed to patch deployment: {exc}") from exc

    incident_id = await _push_signal(
        _agent_self_url(container),
        service,
        f"OOMKilled crashloop on {service} pods — memory limit reduced to {memory}, "
        f"restart_count climbing. Container exit code 137 expected.",
    )
    return {
        "chaos": "oom",
        "namespace": ns,
        "deployment": service,
        "memory_limit": memory,
        "patched": result,
        "incident_id": incident_id,
    }


@router.post("/cpu-throttle")
async def chaos_cpu(
    service: str = Query(...),
    cpu: str = Query("10m", description="Tiny CPU limit to cause throttling"),
    container=Depends(get_container),
):
    """Patch the deployment's CPU request+limit so the container is heavily
    throttled (high latency, possible 5xx)."""
    ns = container.settings.target_namespace or "demo"
    try:
        result = await _patch_resources_directly(
            container,
            deployment=service,
            namespace=ns,
            requests={"cpu": cpu},
            limits={"cpu": cpu},
        )
    except Exception as exc:
        raise HTTPException(500, f"failed to patch deployment: {exc}") from exc

    incident_id = await _push_signal(
        _agent_self_url(container),
        service,
        f"p99 latency above SLO on {service} — CPU pegged, "
        f"requests stalling. Limit currently {cpu}.",
    )
    return {
        "chaos": "cpu-throttle",
        "namespace": ns,
        "deployment": service,
        "cpu_limit": cpu,
        "patched": result,
        "incident_id": incident_id,
    }


@router.post("/scale-zero")
async def chaos_scale_zero(
    service: str = Query(...),
    container=Depends(get_container),
):
    """Scale deployment to 0 replicas — total outage."""
    ns = container.settings.target_namespace or "demo"
    try:
        result = await container.k8s.scale_deployment(
            namespace=ns, deployment=service, replicas=0,
            reason="chaos-scale-zero: forcing total outage",
        )
    except Exception as exc:
        raise HTTPException(500, f"failed to scale: {exc}") from exc

    incident_id = await _push_signal(
        _agent_self_url(container),
        service,
        f"All replicas of {service} are gone — total outage. Service is down.",
    )
    return {
        "chaos": "scale-zero",
        "namespace": ns,
        "deployment": service,
        "patched": result,
        "incident_id": incident_id,
    }


@router.post("/restore")
async def chaos_restore(
    service: str = Query(...),
    container=Depends(get_container),
):
    """Reset deployment back to healthy defaults (memory, cpu, replicas)."""
    ns = container.settings.target_namespace or "demo"
    results: list[str] = []
    try:
        # Restore both memory + cpu requests/limits in one atomic patch.
        results.append(
            await _patch_resources_directly(
                container,
                deployment=service,
                namespace=ns,
                requests={
                    "memory": "64Mi",
                    "cpu": "50m",
                },
                limits={
                    "memory": HEALTHY_DEFAULTS["memory"],
                    "cpu": HEALTHY_DEFAULTS["cpu"],
                },
            )
        )
        results.append(
            await container.k8s.scale_deployment(
                namespace=ns, deployment=service,
                replicas=HEALTHY_DEFAULTS["replicas"],
                reason="chaos-restore",
            )
        )
    except Exception as exc:
        raise HTTPException(500, f"restore failed mid-way: {exc}") from exc

    return {
        "chaos": "restore",
        "namespace": ns,
        "deployment": service,
        "applied": results,
    }


@router.get("/status")
async def chaos_status(
    service: str = Query(...),
    container=Depends(get_container),
):
    """Snapshot of the live deployment + its pods."""
    ns = container.settings.target_namespace or "demo"
    pods = await container.k8s.list_pods(namespace=ns, label_selector=f"app={service}")
    deps = await container.k8s.recent_deployments_for(service=service, since_seconds=86400)
    return {
        "namespace": ns,
        "deployment": service,
        "pods": [
            {
                "name": p.identifier.name,
                "phase": p.phase.value if hasattr(p.phase, "value") else str(p.phase),
                "ready": p.ready,
                "restart_count": p.restart_count,
                "image": p.image,
            }
            for p in pods
        ],
        "deployments": [
            {
                "name": d.name,
                "replicas_desired": d.replicas_desired,
                "replicas_ready": d.replicas_ready,
                "revision": d.revision,
                "last_updated": d.last_updated.isoformat(),
            }
            for d in deps
        ],
    }
