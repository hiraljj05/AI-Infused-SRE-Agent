"""Chaos console wired exclusively to /api/k8s-chaos/*.

No /signals shortcut, no Chaos Mesh CRDs. Every button here causes a real
`kubectl patch` in AKS via the agent's k8s-chaos endpoints, which also push
a single signal back to the agent so the LangGraph wakes up.
"""
from __future__ import annotations

import os

import httpx
import streamlit as st

AGENT_API_URL = os.getenv("AGENT_API_URL", "http://agent.sre-agent.svc.cluster.local:8000")
TARGET_NAMESPACE = os.getenv("TARGET_NAMESPACE", "demo")

st.set_page_config(page_title="SRE Agent — Chaos Console", layout="wide")
st.title("SRE Agent — Chaos Console")
st.caption(
    "Every action below performs a real `kubectl patch` against the AKS cluster "
    f"(namespace `{TARGET_NAMESPACE}`). No simulation. No fake signals."
)

SERVICES = ["food-orders", "portfolio-web"]

SCENARIOS: dict[str, dict[str, str]] = {
    "OOMKill (memory chaos)": {
        "endpoint": "/api/k8s-chaos/oom",
        "description": "Patches the deployment's memory limit to 1Mi → real OOMKilled events on real pods.",
        "expected_signal": "OOMKilled events, restartCount > 0, error rate spike",
    },
    "CPU throttle": {
        "endpoint": "/api/k8s-chaos/cpu-throttle",
        "description": "Patches the deployment's CPU limit to 1m → 99%+ throttling on real pods.",
        "expected_signal": "p99 latency spike, CPU throttle metric > 0",
    },
    "Scale to zero (full outage)": {
        "endpoint": "/api/k8s-chaos/scale-zero",
        "description": "Scales the deployment replicas to 0 → real outage on real service.",
        "expected_signal": "all pods gone, requests failing connect",
    },
}


with st.sidebar:
    st.header("Target")
    st.write(f"Namespace: `{TARGET_NAMESPACE}`")
    st.write(f"Agent API: `{AGENT_API_URL}`")
    target_service = st.selectbox("Service to attack", SERVICES, index=0)
    st.divider()
    st.caption(
        "Heal: revert the patch and reset replicas. Use after each scenario "
        "to bring the service back to baseline."
    )
    if st.button("🩹 Restore service", use_container_width=True):
        try:
            with httpx.Client(timeout=15.0) as c:
                r = c.post(
                    f"{AGENT_API_URL}/api/k8s-chaos/restore",
                    params={"service": target_service},
                )
            (st.success if r.is_success else st.error)(f"{r.status_code}: {r.text[:300]}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"restore failed: {exc}")


st.subheader(f"Scenarios on `{target_service}`")
cols = st.columns(2)
for i, (label, scenario) in enumerate(SCENARIOS.items()):
    with cols[i % 2]:
        with st.container(border=True):
            st.write(f"**{label}**")
            st.write(scenario["description"])
            st.caption(f"Expected signal: {scenario['expected_signal']}")
            if st.button(f"Inject — {label}", key=label, use_container_width=True):
                try:
                    with httpx.Client(timeout=20.0) as c:
                        r = c.post(
                            f"{AGENT_API_URL}{scenario['endpoint']}",
                            params={"service": target_service},
                        )
                    if r.is_success:
                        st.success(f"{r.status_code}: {r.text[:300]}")
                        try:
                            data = r.json()
                            inc = data.get("incident_id")
                            if inc:
                                st.info(f"Incident opened: **{inc}** — watch the dashboard timeline.")
                        except Exception:  # noqa: BLE001
                            pass
                    else:
                        st.error(f"{r.status_code}: {r.text[:500]}")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"chaos call failed: {exc}")


st.divider()
st.subheader("Live state")
if st.button("Refresh /api/k8s-chaos/status", use_container_width=False):
    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.get(f"{AGENT_API_URL}/api/k8s-chaos/status")
        st.json(r.json() if r.is_success else {"status_code": r.status_code, "body": r.text})
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
