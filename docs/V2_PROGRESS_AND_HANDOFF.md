# V2 Build — Progress & Session Handoff

**Purpose**: complete state of the V2 build so a fresh Claude session can pick up exactly where we left off.
**Last updated**: 2026-04-23
**Companion docs**: `docs/V2_BUILD_PLAN.md` (the original 19-phase plan), `docs/HLD.md`, `docs/LLD.md`

---

## TL;DR

- **10 of 18 phases are shipped, verified, and running.** P1–P10.
- **8 phases remain.** P11–P18.
- Local stack is fully running. Azure AKS cluster is up and idle.
- No commits yet — code lives in working tree.
- Next session should pick up at **P11** or pivot to **P13 (Manager Dashboard)** for highest visible impact.

---

## 1. Project Reference

| Attribute | Value |
|-----------|-------|
| Repo root | `/Users/SRE-chatbot` |
| Primary user  |
| LLM | OpenRouter (`anthropic/claude-sonnet-4.5`); key in `.env` |
| Azure account in use | `tyagipriyansh07@outlook.com` |
| Azure subscription | `Azure subscription 1` (id `9de1b523-82fb-4efb-bc40-64b34def0c70`) |
| Azure resource group | `sre-agent-demo` (region `centralindia`) |
| AKS cluster | `sre-demo-aks` — Kubernetes 1.34.4, 1× `Standard_B2s_v2` node, idle |
| AKS context | `sre-demo-aks` (already in `~/.kube/config`) |
| Local Docker stack | docker-compose.dev.yml — all 8 services healthy |

---

## 2. Phases Completed (P1–P10)

Each phase ends with a real verification. Hexagonal layering enforced; domain has no infra imports.

### P1 — Project + App Registry (DB-backed) ✅

- New tables: `projects`, `apps` (Alembic migration `0002_registry.py` exists; in dev we apply via `Base.metadata.create_all`)
- New domain entities: `Project`, `ProjectId`, `App`, `AppId`, `AppOwner`
- New ports: `ProjectRepository`, `AppRepository` (added to `UnitOfWork`)
- New SQLAlchemy ORM: `ProjectModel`, `AppModel`
- New REST routers: `/api/projects`, `/api/apps`
- Replaces YAML-based service catalogue

**Verification**: created project `CHK` (proj_fca1483bd7d1) + apps `payments-api`, `orders-api`. Dedup returns 409.

### P2 — App Onboarding Wizard ✅

- New use case: `OnboardAppUseCase`
- New adapter: `GrafanaAdapter` (HTTP API client) + `build_app_dashboard_template` template
- Onboarding side effects: registers app → POSTs Grafana dashboard → upserts runbook stub into Qdrant
- New REST endpoint: `POST /api/apps/onboard`
- New Next.js page: `app/apps/new/page.tsx` (3-section form, optimistic UX)
- New nav link in `app/layout.tsx`

**Verification**: onboarded `orders-api` → Grafana dashboard `app-orders-api` visible at `http://localhost:3001/d/app-orders-api`, runbook `RB-ORDERS-API-STUB` indexed (Qdrant collection grew 15 → 16).

### P3 — Multi-Channel Alerting Fan-Out ✅

- New ports: `TicketingPort`, `EmailPort` + `TicketDraft`, `CreatedTicket`, `EmailMessage`
- New adapters: `JiraCloudAdapter`, `LogOnlyJiraAdapter`, `SmtpEmailAdapter`, `LogOnlyEmailAdapter`
- Adapter selection: real Jira if `JIRA_BASE_URL` set, else log-only; same for SMTP
- New use case: `CreateIncidentTicketUseCase` — parallel fan-out, project-aware routing
- New graph node: `fan_out_ticket_node` between TRIAGE and GATHER
- Auto-acks ticket immediately

**Verification**: signal on `orders-api` → Jira `CHK-1001` created with auto-ack comment, email dispatched to `checkout-oncall@example.com`. Teams failed (expected — no Bot App ID).

### P4 — Extended Kubernetes Toolkit (18 actions) ✅

- New value objects: `ActionClass` enum (LOW/MEDIUM/HIGH/CRITICAL), `ActionDefinition`, full `ACTIONS` registry
- Verb allow-lists: `SAFE_KUBECTL_VERBS`, `SAFE_POD_EXEC_PROGRAMS`
- Extended `KubernetesPort` with: `patch_resource_limit`, `cordon_node`, `taint_node`, `rollback_deployment`, `patch_image`, `restart_statefulset`, `delete_completed_jobs`, `exec_in_pod`
- Implemented all in `KubernetesAdapter`
- Updated `ExecuteFixUseCase._dispatch` for all 18 actions with guardrails (`delete_pvc` blocked from auto-execution; `kubectl_exec` verb-allowlisted)
- Updated `ProposeRemediationUseCase` LLM prompt to know all actions

**Verification**: `from sre_agent.application.use_cases.propose_remediation import ALLOWED_ACTIONS` shows 19 actions: LOW (7), MEDIUM (6), HIGH (5), CRITICAL (1).

### P5 — Chatbot Active Operator ✅

- New use case: `ParseChatIntentUseCase` — LLM intent classifier
- New use case: `RunOnDemandInvestigationUseCase` — reuses detect/triage/gather/diagnose/propose pipeline, idempotent against existing-state incidents
- Rewrote `/chat` router with intent-aware routing:
  - `query` → RAG Q&A (existing flow)
  - `investigate_app` → on-demand investigation
  - `propose_action`, `execute_action` → returns proposal markdown
- Made `LokiLogsAdapter` and `KubernetesAdapter` tolerant of missing services (returns empty in local dev)
- Made OpenRouter adapter strip markdown fences from JSON responses

**Verification**: `who owns payments-api?` → RAG path; `what is wrong with web-frontend` → investigation path with new incident `INC-F41A10E4C4DE`.

### P6 — SLA-Driven Incident Management ✅

- New domain entity: `SLATracker` with state machine PENDING → WARNED → BREACHED → SATISFIED
- SLA matrix per priority (P1: 2/10/30 min; P2: 5/15/60 min; P3: 15/30/240 min; P4: 60/240/1440 min)
- New port: `SLATrackerRepository`; SQLAlchemy `SLATrackerModel` + repo + table
- New use cases: `StartSLATrackersUseCase` (idempotent), `SatisfySLAUseCase`
- New saga: `SLAMonitorScheduler` — 30s tick, posts WARNED at 50% and BREACHED at 100% via `StatusNotificationPort`
- New graph node: `start_slas_node` after triage; auto-satisfies ack
- `diagnose_node` satisfies RCA SLA; `verify_node` satisfies RESOLVE SLA on success
- Started in lifespan alongside existing approval saga

**Verification**: triggered `sla-test-svc` → 3 trackers created (ack/rca/resolve sized for P3 = 15min/30min/4hr), ack & RCA auto-satisfied, resolve still pending (correct, agent stopped at HIL).

### P7 — Structured Lessons Learnt ✅

- New domain entity: `LessonLearnt` with `IssueCategory` enum (12 categories)
- New ports: `LessonsRepository`, `SimilarLessonsPort`
- New SQLAlchemy ORM: `LessonLearntModel` + table `lessons_learnt`
- New Postgres repo: `SqlAlchemyLessonsRepository`
- New Qdrant adapter: `QdrantLessonsAdapter` — separate collection `lessons_learnt`, with payload indexes on `service`/`project_id`/`issue_category`/`human_verified`
- New use case: `ExtractLessonsLearntUseCase` — LLM-extracts structured fields from postmortem text
- Added `lessons` to UoW
- Bootstrapped `lessons_learnt` Qdrant collection in lifespan

**Verification**: `lessons_learnt` Postgres table + Qdrant collection both exist; collection has payload indexes.

### P8 — Human Resolution Capture ✅

- New use case: `CloseIncidentWithHumanResolutionUseCase`
  - Marks RESOLVE SLA satisfied
  - Computes resolution time from `detected_at`
  - Creates LessonLearnt with `confidence=1.0`, `human_verified=True`, resolver=`user:<email>`
  - Indexes into Qdrant
- New REST endpoint: `POST /api/incidents/{incident_id}/close`
- (Audit-log auto-fill via K8s Audit Log Reader is deferred — not yet implemented)

**Verification**: closed `INC-34975653E610` with `priya@example.com` resolution → lesson `lesson_c2e2405cb8ea` created in DB and Qdrant (collection grew 0 → 1).

### P9 — Memory-First Lookup ✅

- New use case: `FindSimilarIncidentsUseCase` — vector search Qdrant for similar lessons, project-filtered
- New graph node: `memory_lookup_node` between `start_slas` and `fan_out`
- Records similarity matches to incident notes; flags HIGH-confidence (≥0.85) matches
- (Short-circuit-to-prior-fix path is **NOT** wired — node currently just informs the LLM context. Adding short-circuit is a small follow-up for next session.)

**Verification**: direct Qdrant search for `memory-test-svc-2 connection pool exhausted again` returned the prior `connection_pool` lesson with similarity 0.41.

### P10 — Webhooks (Grafana, Azure Monitor, ELK) ✅

- New router: `/webhooks/grafana`, `/webhooks/azure-monitor`, `/webhooks/elasticsearch`
- Each translates the source-specific payload to internal `AgentState` and starts a graph run
- Severity mapping for Azure Monitor (Sev0/1 → P1, Sev2 → P2, etc.)
- Grafana adapter (HTTP API client) was built earlier in P2 and is reusable for `list_dashboards`/`list_alert_rules`

**Verification**: posted Grafana payload to `/webhooks/grafana` → `{"accepted":true,"signals_started":1,"total_alerts":1}`. Note: P11 (ELK) and P12 (Azure Monitor) need full **query** adapters (LogsPort/MetricsPort impls) — only the **inbound webhook** is done so far.

---

## 3. Phases Remaining (P11–P18)

### P11 — ELK / Elasticsearch query adapter

**What's done**: `/webhooks/elasticsearch` ingestion endpoint.
**What's left**:
- `ElasticsearchLogsAdapter` implementing `LogsPort` (search via `_search` API)
- Optional `MultiSourceLogsAdapter` that queries Loki + ELK and merges
- Auto-detect: if `ELASTICSEARCH_URL` set, prefer ELK; else use Loki
- Add to `composition_root` and config

**Effort**: ~3 hours. Files to create:
- `services/agent/src/sre_agent/infrastructure/logs/elasticsearch_adapter.py`
- Optional: `services/agent/src/sre_agent/infrastructure/logs/multi_source_adapter.py`
- Add `ELASTICSEARCH_URL` to `common/config.py`

### P12 — Azure Monitor query adapter

**What's done**: `/webhooks/azure-monitor` ingestion endpoint.
**What's left**:
- `AzureMonitorMetricsAdapter` implementing `MetricsPort` using `azure-monitor-query` SDK
- Composite metrics adapter: query Prometheus + Azure Monitor and merge by canonical metric name
- Wire into `composition_root` (only when Azure creds present)

**Effort**: ~4 hours. Files to create:
- `services/agent/src/sre_agent/infrastructure/metrics/azure_monitor_adapter.py`
- `services/agent/src/sre_agent/infrastructure/metrics/composite_adapter.py`
- Add `AZURE_MONITOR_WORKSPACE_ID` to config; need `DefaultAzureCredential` setup

### P13 — Full Manager Dashboard (Next.js)

**Highest user-visible impact.** 8 views to add to the existing `services/dashboard`:

1. **Overview** (already exists, needs upgrades) — service health map, agent-vs-human donut, MTTR gauge, on-call workload
2. **Apps** — per-app: SLO compliance, MTTR, MTTD, error budget burn-down, recent incidents (`GET /api/apps`, `GET /api/incidents?service=...`)
3. **Incidents** — full table with filters; click → timeline view (already partial)
4. **People** — per-engineer aggregates; needs `GET /api/people/aggregates` endpoint (NEW)
5. **Knowledge** — runbook library, lessons-learnt explorer (NEW: `GET /api/lessons`, `GET /api/runbooks`)
6. **Reports** — weekly digest, monthly compliance, exports
7. **Settings** — apps/projects/owners CRUD (already has create-only, needs full CRUD UI)
8. **Cost** — LLM tokens per app/incident, infra cost (read from Prometheus `sre_agent_llm_tokens_used_total`)

**Effort**: ~7 hours. Tech: Next.js 14 + Tailwind + shadcn/ui + Recharts.

Files to create:
- `services/dashboard/app/apps/page.tsx` (list + drill-down)
- `services/dashboard/app/apps/[id]/page.tsx`
- `services/dashboard/app/people/page.tsx`
- `services/dashboard/app/knowledge/page.tsx`
- `services/dashboard/app/reports/page.tsx`
- `services/dashboard/app/settings/page.tsx`
- `services/dashboard/app/cost/page.tsx`
- `services/dashboard/components/charts/*.tsx` (donut, bar, gauge)

Plus backend endpoints:
- `GET /api/lessons` (filtered by app/category)
- `GET /api/people/aggregates`
- `GET /api/cost/llm-tokens` (Prometheus query)

### P14 — Reports + Auto-Digest

**Effort**: ~3 hours.
- Cron job (in-cluster CronJob or `apscheduler` inside agent) that aggregates last 7 days
- Posts summary to Teams `#sre-weekly` channel via `StatusNotificationPort`
- Generates monthly CSV + PDF using `reportlab`

Files to create:
- `services/agent/src/sre_agent/application/use_cases/generate_weekly_digest.py`
- `services/agent/src/sre_agent/application/saga/digest_scheduler.py`

### P15 — Advisory Mode (new project onboarding)

**Effort**: ~5 hours.
- `RunAdvisoryConversationUseCase` — multi-turn LangGraph mini-flow
- Discovery questions: cloud / workload type / scale / compliance / latency target
- New Qdrant collection `recommended_stacks` (seed with 8–10 stack templates)
- Generates SRE-readiness markdown checklist with download
- Dashboard page `/advisor`
- Teams trigger `@SRE-Agent advise me on a new project`

Files to create:
- `services/agent/src/sre_agent/application/use_cases/run_advisory_conversation.py`
- `services/agent/src/sre_agent/application/agent_graph/advisory_graph.py`
- `services/dashboard/app/advisor/page.tsx`
- `knowledge_base/recommended_stacks/*.md` (seed content)

### P16 — Auth + SSO (Azure AD OIDC)

**Effort**: ~3 hours. **Requires user touchpoint** (Azure AD App Registration + tenant config).
- JWT validation middleware on FastAPI
- Identity propagation from Teams Bot Framework (already provides AAD object ID)
- Role-based gates: only on-call/lead can approve high-risk actions
- Audit `caused_by` always populated with real identity

Files to create:
- `services/agent/src/sre_agent/interface/rest/middleware/auth.py`
- `services/agent/src/sre_agent/common/identity.py`
- Add `AZURE_AD_TENANT_ID`, `AZURE_AD_CLIENT_ID` to config

### P17 — Compliance Polish

**Effort**: ~2 hours.
- 36-month retention enforcement (cron job + soft-delete on `incident_events`, `lessons_learnt`)
- PII detection + masking (we have basic regex; tighten to NER for emails/phones/tokens)
- Encryption at rest verification (Azure-managed keys for AKS PVs)
- Audit log integrity (revoke UPDATE/DELETE grants on `incident_events` from app role)

Files to create:
- `services/agent/src/sre_agent/application/use_cases/enforce_retention.py`
- `services/agent/src/sre_agent/common/pii_scrubber.py`

### P18 — Production Deploy to AKS

**Effort**: ~3 hours. **Will create real Azure resources** (existing Bicep already deployed AKS).
- Helm apply: platform → sre-agent → dummy-app → chaos-ui → dashboard
- Sealed Secrets for OpenRouter key, Jira API token, SMTP creds, Bot Service creds
- Argo CD app-of-apps wired
- Smoke tests post-deploy
- Backup CronJob: Postgres + Qdrant snapshots to Azure Blob

Steps:
- `./scripts/deploy-aks.sh` exists; needs sealed-secrets generation step added
- Update Helm chart `values.yaml` with V2 env (Jira, SMTP, lessons_learnt collection, etc.)

---

## 4. Local Stack — Current State

All 8 containers running healthy:

| Container | Port | Purpose |
|-----------|------|---------|
| `sre-chatbot-agent-1` | 8000 | FastAPI agent (live-reload via mounted source) |
| `sre-chatbot-postgres-1` | 5432 | State + audit + checkpoints |
| `sre-chatbot-qdrant-1` | 6333 | RAG + lessons_learnt vectors |
| `sre-chatbot-redis-1` | 6379 | (reserved for cache) |
| `sre-chatbot-prometheus-1` | 9090 | Metrics |
| `sre-chatbot-grafana-1` | 3001 | Dashboards (admin/admin); SRE Agent dashboard preloaded |
| `sre-chatbot-dashboard-1` | 3030 | Next.js dashboard |
| `sre-chatbot-chaos-ui-1` | 8501 | Streamlit chaos console |

**Postgres tables (10)**: `incidents`, `incident_events`, `approvals`, `postmortems`, `projects`, `apps`, `sla_trackers`, `lessons_learnt`, `checkpoint_*` (4 LangGraph tables)

**Qdrant collections (2)**: `sre_knowledge` (16 docs), `lessons_learnt` (1 doc)

**Bring it all back up**:
```bash
cd /Users/SRE-chatbot
docker compose -f docker-compose.dev.yml up -d
# Then optionally re-apply schema if you added new tables:
docker exec sre-chatbot-agent-1 python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sre_agent.infrastructure.persistence.models import Base

async def run():
    engine = create_async_engine('postgresql+asyncpg://sre:sre@postgres:5432/sre_agent')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print('Schema sync done')

asyncio.run(run())
"
```

---

## 5. Azure State

| Resource | Status | Notes |
|----------|--------|-------|
| Resource group `sre-agent-demo` | Created (centralindia) | Free; deleting it cleans everything |
| AKS `sre-demo-aks` | Running, idle | 1× B2s_v2 = ~$60/mo |
| Log Analytics `sre-demo-aks-logs` | Active | ~$3/mo |
| Container Insights | Active | $0 |
| **Workloads on cluster** | **Nothing deployed yet** | P18 will Helm-apply everything |
| Bot Service | NOT created | Needs Azure AD App Registration first |

**Cost burn**: ~$63/month while idle. To stop billing without losing the cluster:
```bash
az aks stop -g sre-agent-demo -n sre-demo-aks
```

---

## 6. Code Inventory

### New domain entities (V2)
- `services/agent/src/sre_agent/domain/entities/project.py`
- `services/agent/src/sre_agent/domain/entities/app.py`
- `services/agent/src/sre_agent/domain/entities/sla_tracker.py`
- `services/agent/src/sre_agent/domain/entities/lesson_learnt.py`

### New domain ports (V2)
- `services/agent/src/sre_agent/domain/ports/registry.py` — `ProjectRepository`, `AppRepository`
- `services/agent/src/sre_agent/domain/ports/sla.py` — `SLATrackerRepository`
- `services/agent/src/sre_agent/domain/ports/lessons.py` — `LessonsRepository`, `SimilarLessonsPort`
- `services/agent/src/sre_agent/domain/ports/ticketing.py` — `TicketingPort`, `EmailPort`

### New value objects (V2)
- `services/agent/src/sre_agent/domain/value_objects/action_class.py` — `ACTIONS` registry, allow-lists

### New use cases (V2)
- `onboard_app.py`
- `create_incident_ticket.py`
- `parse_chat_intent.py`
- `run_on_demand_investigation.py`
- `start_sla_trackers.py`
- `extract_lessons_learnt.py`
- `close_incident_with_human_resolution.py`
- `find_similar_incidents.py`

### New infrastructure adapters (V2)
- `infrastructure/grafana/grafana_adapter.py`
- `infrastructure/ticketing/jira_adapter.py`
- `infrastructure/ticketing/log_only_jira_adapter.py`
- `infrastructure/ticketing/smtp_email_adapter.py`
- `infrastructure/ticketing/log_only_email_adapter.py`
- `infrastructure/knowledge/qdrant_lessons_adapter.py`
- `infrastructure/persistence/postgres/registry_repos.py`
- `infrastructure/persistence/postgres/registry_mappers.py`
- `infrastructure/persistence/postgres/sla_repo.py`
- `infrastructure/persistence/postgres/lessons_repo.py`

### New REST routers (V2)
- `interface/rest/routers/projects.py` — full CRUD
- `interface/rest/routers/apps.py` — full CRUD + `/onboard`
- `interface/rest/routers/close_incident.py` — `POST /api/incidents/{id}/close`
- `interface/rest/routers/webhooks.py` — Grafana / Azure Monitor / ELK
- Updated `chat.py` — intent-aware routing

### New saga (V2)
- `application/saga/sla_monitor.py` — `SLAMonitorScheduler`

### New Pydantic schemas (V2)
- `interface/rest/schemas/registry.py` — `ProjectIn`, `ProjectView`, `AppIn`, `AppView`

### New dashboard pages (V2)
- `services/dashboard/app/apps/new/page.tsx` — onboarding wizard

### Updated files
- `composition_root.py` — wires all new dependencies
- `application/agent_graph/nodes.py` — added `start_slas_node`, `memory_lookup_node`, `fan_out_ticket_node`
- `application/agent_graph/graph.py` — new graph topology with 4 new nodes
- `application/use_cases/__init__.py` — exports
- `domain/entities/__init__.py` + `domain/ports/__init__.py` + `domain/value_objects/__init__.py` — exports
- `infrastructure/persistence/models/orm.py` — `ProjectModel`, `AppModel`, `SLATrackerModel`, `LessonLearntModel`
- `infrastructure/persistence/postgres/uow.py` — added `projects`, `apps`, `slas`, `lessons` to UoW
- `infrastructure/k8s/kubernetes_adapter.py` — 7 new methods + tolerance to missing config
- `infrastructure/llm/openrouter_adapter.py` — strips markdown fences from JSON
- `infrastructure/logs/loki_adapter.py` — tolerant of missing Loki
- `application/use_cases/execute_fix.py` — dispatches all 18 actions
- `application/use_cases/propose_remediation.py` — knows all 18 actions
- `common/config.py` — `GRAFANA_*`, `JIRA_*`, `SMTP_*`, `QDRANT_LESSONS_COLLECTION`
- `interface/rest/app.py` — registers all new routers, starts SLA monitor
- `services/dashboard/app/layout.tsx` — added `+ Add App` nav link
- `pyproject.toml` — added `pydantic[email]`
- `services/dashboard/Dockerfile` — `NEXT_PUBLIC_API_URL` as build ARG
- `docker-compose.dev.yml` — added Grafana, removed `:ro` from agent src mount in some cases

---

## 7. New Graph Topology

```
START
  └─► detect
       └─► triage
            └─► start_slas         (P6 — auto-ack SLA)
                 └─► memory_lookup  (P9 — find similar prior lessons)
                      └─► fan_out   (P3 — Jira + Email + Teams)
                           └─► gather
                                └─► diagnose      (P6 — satisfy RCA SLA)
                                     └─► propose
                                          ├─[requires_hil]─► notify_hil
                                          │                     ├─approve─► execute
                                          │                     └─reject──► escalate
                                          └─[auto]──────────────► execute
                                                                    └─► verify  (P6 — satisfy RESOLVE SLA)
                                                                         ├─baseline─► postmortem ─► END
                                                                         └─retry───► gather (max 2x) ─► escalate
```

**Sagas running in parallel**:
- `ApprovalSagaScheduler` — every 15s, escalates HIL approvals
- `SLAMonitorScheduler` — every 30s, marks WARNED/BREACHED, posts notifications

---

## 8. Verified Demo Flows (run any of these to sanity-check on resume)

### Demo A — Onboard an app and trigger fan-out
```bash
PROJ_ID=$(curl -s http://localhost:8000/api/projects | python3 -c "import json,sys;print(json.load(sys.stdin)[0]['id'])")
curl -s -X POST http://localhost:8000/api/apps/onboard -H 'Content-Type: application/json' \
  -d "{\"project_id\":\"$PROJ_ID\",\"name\":\"demo-app-$RANDOM\",\"namespace\":\"demo-store\",\"tier\":\"tier-1\",\"owners\":[{\"email\":\"x@y.com\",\"role\":\"primary\"}]}"
```

### Demo B — Trigger a signal end-to-end
```bash
curl -s -X POST http://localhost:8000/signals -H 'Content-Type: application/json' \
  -d '{"service":"demo-app-XXX","initial_signal":"errors spiking","signal_sources":["test"],"namespace":"demo-store"}'
sleep 12
docker exec sre-chatbot-postgres-1 psql -U sre -d sre_agent -c "SELECT id, status, severity FROM incidents ORDER BY detected_at DESC LIMIT 3;"
```

### Demo C — Active chat
```bash
# Q&A
curl -s -X POST http://localhost:8000/chat -H 'Content-Type: application/json' -d '{"question":"who owns payments-api?"}'
# Investigation
curl -s -X POST http://localhost:8000/chat -H 'Content-Type: application/json' -d '{"question":"what is wrong with web-frontend?"}'
```

### Demo D — Human close + lesson capture
```bash
INC=$(docker exec sre-chatbot-postgres-1 psql -U sre -d sre_agent -t -c "SELECT id FROM incidents WHERE status<>'resolved' ORDER BY detected_at DESC LIMIT 1" | xargs)
curl -s -X POST "http://localhost:8000/api/incidents/$INC/close" -H 'Content-Type: application/json' -d '{
  "actor_email":"priya@example.com","issue_category":"connection_pool",
  "fix_description":"What I did","fix_rationale":"Why it worked","could_agent_handle":"yes","tags":["test"]
}'
```

### Demo E — Grafana webhook
```bash
curl -s -X POST http://localhost:8000/webhooks/grafana -H 'Content-Type: application/json' -d '{
  "alerts":[{"status":"firing","labels":{"service":"web-frontend","namespace":"demo-store"},"annotations":{"summary":"latency over 1s"}}]
}'
```

---

## 9. Known Issues / Quirks

1. **Old `payments-api` incident `INC-20C163DA2CE3`** is still active in the DB from yesterday — it blocks dedup. Either close it or use a different service for testing.
2. **K8s adapter is tolerant of missing kubeconfig** — local dev returns empty pod lists. Production will use in-cluster ServiceAccount.
3. **Loki not running locally** — adapter returns empty log lines on connection refused. Acceptable for dev.
4. **OpenRouter occasionally returns markdown-wrapped JSON** — the adapter now strips fences, but if the LLM returns prose, the structured-output endpoints will fall back gracefully (e.g., chat falls back to Q&A).
5. **Memory-first lookup does NOT short-circuit yet** — the `memory_lookup_node` currently only logs the matches. Adding short-circuit-to-prior-fix is a small follow-up.
6. **No tests written for V2 use cases yet** — V1 had unit tests for value objects, incident, approval. V2 use cases need their own test coverage.
7. **`import-linter` not enforced in CI yet** — boundary contracts exist (`.importlinter`), but CI hasn't been updated to run them on V2 code.

---

## 10. Files NOT yet committed to git

The whole V2 build is in the working tree, no commits yet. Suggested commit strategy:

```bash
cd /Users/SRE-chatbot
git add docs/V2_PROGRESS_AND_HANDOFF.md docs/V2_BUILD_PLAN.md
git commit -m "v2 plan + progress doc"

# Phase commits:
git add services/agent/src/sre_agent/domain/entities/project.py services/agent/src/sre_agent/domain/entities/app.py \
        services/agent/src/sre_agent/domain/ports/registry.py \
        services/agent/src/sre_agent/infrastructure/persistence/postgres/registry_*.py \
        services/agent/src/sre_agent/interface/rest/routers/projects.py services/agent/src/sre_agent/interface/rest/routers/apps.py \
        services/agent/src/sre_agent/interface/rest/schemas/registry.py
git commit -m "P1: Project + App registry"

# ...etc per phase
```

---

## 11. How to Resume in a New Session

The new session should:

1. **Read this doc first.** It explains everything.
2. **Re-verify the local stack:**
   ```bash
   docker compose -f /Users/SRE-chatbot/docker-compose.dev.yml ps
   curl -s http://localhost:8000/healthz
   ```
3. **Re-verify Azure context** (might have switched accounts):
   ```bash
   az account show --query "{user:user.name, sub:name}" -o json
   kubectl config current-context
   ```
4. **Pick a phase to resume.** Recommended order:
   - **If demoability is the priority** → P13 (Manager Dashboard) — highest visible impact
   - **If completeness is the priority** → P11 → P12 (finish observability inputs)
   - **If production is the priority** → P16 (Auth) → P17 (Compliance) → P18 (AKS deploy)
5. **Commit current state first.** All V2 code is in the working tree, uncommitted.
6. **Update this doc as you go** — `## 2. Phases Completed` and `## 3. Phases Remaining`.

---

## 12. Quick Architecture Reminder

- **Hexagonal layers**: `domain` (pure) ← `application` (use cases) ← `infrastructure` (adapters) + `interface` (FastAPI/Bot)
- **Composition root**: `services/agent/src/sre_agent/composition_root.py` — single place that wires all dependencies
- **Lifespan**: `services/agent/src/sre_agent/interface/rest/app.py` — boots DI container, opens checkpointer, starts sagas
- **State machine**: `services/agent/src/sre_agent/application/agent_graph/graph.py`
- **Sagas**: `services/agent/src/sre_agent/application/saga/{approval_saga,sla_monitor}.py`

---

## 13. Acknowledgements / Decisions Locked Earlier

| Decision | Choice |
|----------|--------|
| App onboarding | Wizard form (Option B) |
| K8s tool execution | Hybrid (Option C) — predefined + `kubectl_exec` always HIL |
| Human resolution capture | Hybrid form + (deferred) audit-log auto-fill |
| Manager dashboard scope | All 8 views |
| Chatbot scope | Active operator (Option X) — same in Teams + Dashboard |
| Project registry storage | Database (not YAML) |
| Multi-channel alerting | Jira + Email + Teams to project-specific recipients |
| Escalation model | Single agent with extended toolkit (no specialised agents in V2) |
| Memory loop | Auto-extract from postmortems + capture every human resolution |
| Avatar on calls | Deferred to V3 |

---

## End of Handoff

Open this file in the next session, run the pre-flight checks in §11, then continue from §3 with the phase you want next.
