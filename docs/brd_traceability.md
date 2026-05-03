# BRD-020 Traceability Matrix

Every requirement from BRD-020 maps to concrete code modules and tests.

## Business Rules

| BRD ID | Requirement | Implementation |
|------|-----|----|
| BR-020-001 | Multi-platform observability ingestion | `infrastructure/metrics/prometheus_adapter.py`, `infrastructure/logs/loki_adapter.py`. Canonical metric-name mapping in `METRIC_TEMPLATES`. Adapters are interchangeable via `MetricsPort` / `LogsPort`. |
| BR-020-002 | Concurrent incident detection + RCA + remediation | Each incident is an isolated LangGraph run (thread per incident_id). `DetectIncidentUseCase` deduplicates via `find_active_for_service`. |
| BR-020-003 | SLO governance + ITSM integration | `application/use_cases/` produces incident records via Postgres (acts as ITSM store for demo). Extendable to ServiceNow/Jira by adding an adapter. |
| BR-020-004 | HIL for production remediation | `application/saga/approval_saga.py`, `domain/entities/approval.py`. LangGraph `interrupt_before=["execute"]` pauses until approval. |
| BR-020-005 | AI disclosure on onboarding | Dashboard surfaces disclosure text on service detail page (Phase 7 polish). |
| BR-020-006 | Knowledge base + deduplication + retention | `infrastructure/knowledge/qdrant_adapter.py` (RAG), `DetectIncidentUseCase` (dedup), event_sourcing for immutable audit (36mo via retention policy on postgres). |

## Operational Metrics (Arjuna Requirements)

| Metric | Target | Where emitted |
|------|-----|------|
| MTTD | P1 <= 3 min | `common/metrics.py::MTTD`, observed from `IncidentDetected` to `IncidentTriaged` |
| MTTR | P1 <= 1 hour | `common/metrics.py::MTTR`, observed at `IncidentResolved` |
| Automated remediation success rate | >= 70% | `common/metrics.py::AUTOMATED_REMEDIATION` |
| RCA hypothesis accuracy | >= 80% | Tracked offline via postmortem sign-off vs LLM RCA; `RCA_CONFIDENCE` histogram |
| Alert noise rate | <= 20% | `DetectIncidentUseCase.find_active_for_service` dedup + alert correlation |
| On-call ack time (P1) | <= 5 min | `HIL_LATENCY` histogram |
| Postmortem completion rate | >= 95% (within 24h) | `GeneratePostmortemUseCase` auto-drafts after `IncidentResolved` |

## HIL Checkpoints

| BRD ID | Checkpoint | Implementation |
|------|-----|------|
| HIL-1 | Monitoring config review | Performed out-of-band via git review of `knowledge_base/services/*.yaml` (GitOps) |
| HIL-2 | Production remediation approval | `notify_hil_node` + `ResolveApprovalUseCase` + Teams Adaptive Card. Saga escalates on timeout. |
| HIL-3 | Postmortem sign-off | `Postmortem.sign_off()` - dashboard exposes a "publish" button (Phase 7 polish). |

## Guardrails (see `domain/ports/k8s.py` and use cases)

- No irreversible actions without HIL-2: `ProposedAction.requires_hil` derived from blast radius + confidence threshold.
- Agent cannot modify alert rules / SLO / playbook content at runtime: GitOps-only.
- RCA below threshold -> `no_op_escalate` action (see `ProposeRemediationUseCase`).
- Post-action verification required: `VerifyResolutionUseCase` before resolution.
- Audit trail append-only: `incident_events` table with no UPDATE/DELETE grants.
