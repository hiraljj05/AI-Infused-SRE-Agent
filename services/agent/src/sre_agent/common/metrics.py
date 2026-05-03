from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

MTTD = Histogram(
    "sre_agent_mttd_seconds",
    "Mean time to detect from signal onset",
    labelnames=("severity",),
    buckets=(30, 60, 120, 180, 300, 600, 1800, 3600),
)

MTTR = Histogram(
    "sre_agent_mttr_seconds",
    "Mean time to resolve from detection",
    labelnames=("severity",),
    buckets=(60, 300, 900, 1800, 3600, 7200, 14400, 28800),
)

RCA_CONFIDENCE = Histogram(
    "sre_agent_rca_confidence",
    "Top RCA hypothesis confidence distribution",
    labelnames=("service",),
    buckets=(0.1, 0.3, 0.5, 0.7, 0.85, 0.95),
)

TOOL_INVOCATIONS = Counter(
    "sre_agent_tool_invocations_total",
    "Tool invocations by the agent",
    labelnames=("tool", "status"),
)

LLM_TOKENS = Counter(
    "sre_agent_llm_tokens_used_total",
    "LLM tokens consumed",
    labelnames=("provider", "model", "kind"),
)

HIL_LATENCY = Histogram(
    "sre_agent_hil_approval_latency_seconds",
    "Time from approval request to human decision",
    labelnames=("outcome",),
    buckets=(5, 15, 30, 60, 120, 300, 600, 1800, 3600),
)

ACTIVE_INCIDENTS = Gauge(
    "sre_agent_active_incidents",
    "Currently active incidents by severity",
    labelnames=("severity",),
)

AUTOMATED_REMEDIATION = Counter(
    "sre_agent_automated_remediation_total",
    "Count of automated remediation attempts and outcomes",
    labelnames=("action", "outcome"),
)
