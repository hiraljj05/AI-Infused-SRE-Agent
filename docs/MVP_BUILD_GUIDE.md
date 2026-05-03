# SRE Agent — MVP Build Guide

**Document type**: From-scratch build guide for a single engineer to ship an MVP
**Audience**: Anyone starting this project from zero who wants the minimum lovable product running
**Estimated effort**: 4–6 weeks for one full-time engineer
**Companion documents**: `docs/V2_BUILD_PLAN.md` (the bigger picture once MVP is shipped)

---

## What "MVP" means here

The smallest thing that proves the core idea:

> *Production system breaks → AI agent detects → diagnoses with confidence score → asks a human for permission → fixes it → verifies the fix.*

If a stranger watches you click one button to break a service, then watches the agent take it from "🚨 alert" to "✅ resolved" in three minutes with a humane approval prompt in the middle — **that's MVP**.

Everything else (Jira, Email, multi-cloud, manager dashboards, advisory mode, on-call avatar) is post-MVP.

### What's IN the MVP

| Feature | Scope |
|---------|-------|
| Monitoring source | **Prometheus only** (one source, locally) |
| Alert trigger | Manual button (Streamlit chaos UI) → POST to agent |
| LLM | One model via OpenRouter (Claude or GPT) |
| RAG knowledge base | Qdrant + sentence-transformers (CPU embeddings, free) |
| Incident lifecycle | Detect → triage → gather → diagnose → propose → HIL → execute → verify → postmortem |
| Action library | 3 actions: `restart_pod`, `rollout_restart`, `scale_deployment` |
| HIL approval | **Web dashboard button** (Teams later) |
| Notifications | Browser-visible only (Teams/Email later) |
| Persistence | Postgres in Docker |
| UI | Two pages: Incident list + Chat Q&A |
| Demo workload | 3 small services (frontend, backend, db) running in Docker |
| Deployment target | **Local Docker Compose** (cloud later) |

### What's OUT of the MVP

| Feature | Why deferred |
|---------|-------------|
| Microsoft Teams bot | Auth setup is hours; Adaptive Cards are complex. Add post-MVP. |
| Jira / Email integration | Web dashboard is enough to demo HIL. |
| AKS / Kubernetes deployment | Docker Compose proves the loop without cluster overhead. |
| Manager dashboard / reports | One page showing incidents is enough. |
| Multi-source observability (Grafana, ELK, Azure Monitor) | One source proves the concept. |
| Lessons-learnt extraction | Single Qdrant index of past incidents is enough. |
| SLA tracking with priority-aware ack/RCA timers | Single hard timeout for HIL is enough. |
| Auth/SSO | Localhost dev — no auth needed. |
| Avatar on calls | Stretch goal years out. |

---

## Prerequisites

### Tooling on your laptop

| Tool | Why | Install |
|------|-----|---------|
| Python 3.12 | Agent backend | `brew install python@3.12` (mac) or use `uv python install 3.12` |
| Node 20 | Dashboard | `brew install node@20` |
| Docker Desktop | Run Postgres, Qdrant, Prometheus | https://docker.com/desktop |
| `uv` | Fast Python package manager | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `make` | Run dev shortcuts | preinstalled on mac/linux |
| Git | Version control | preinstalled |
| A code editor | (VS Code, Cursor, etc.) | your choice |

### Accounts

| Account | Why | Cost |
|---------|-----|------|
| **OpenRouter** (https://openrouter.ai) | LLM access (Claude/GPT/Gemini etc.) | Pay-per-token; ~$1–3 for the entire MVP build |
| GitHub | Repo + container registry | Free for public repos |

That's it. **No cloud account required for the MVP.**

---

## The 12-Phase Plan

Each phase builds on the previous. Each is independently demoable.

### Phase 0 — Repo Scaffolding · Half day

**Goal**: A clean repo with the file layout you'll grow into.

**Steps**:

1. Create the repo:
   ```
   mkdir sre-agent && cd sre-agent && git init
   ```
2. Create directory structure:
   ```
   services/agent/src/sre_agent/{domain,application,infrastructure,interface}
   services/dashboard
   services/dummy-app/{frontend,backend,db-init}
   services/chaos-ui
   knowledge_base/{runbooks,services}
   docs
   scripts
   ```
3. Add `.gitignore`, `.editorconfig`, an empty `README.md`, and a `Makefile` skeleton with `dev-up`, `test`, `lint` targets.
4. Add a `docker-compose.dev.yml` skeleton with empty service blocks (you'll fill them in later phases).

**Deliverable**: An empty but well-organized repo committed to git.

**Pitfalls**:
- Don't skip the directory boundaries — even when empty, they enforce the architecture later.
- Use **hexagonal layering** from day one (`domain/` is pure, `infrastructure/` has all the integrations). Refactoring this later is painful.

---

### Phase 1 — Dummy Workload · 1 day

**Goal**: Three small services to monitor and break.

**Steps**:

1. **Frontend** (Python FastAPI): exposes `/checkout` that calls backend.
2. **Backend** (Python FastAPI): exposes `/charge` with intentional `/admin/fail` and `/admin/heal` endpoints.
3. **DB init** (Postgres + a seed script).
4. Each service has Prometheus instrumentation:
   ```python
   from prometheus_client import Counter, Histogram, make_asgi_app
   REQ = Counter("http_requests_total", ...,
                 labelnames=("service","code","route"))
   LAT = Histogram("http_request_duration_seconds", ...,
                   labelnames=("service","route"))
   app.mount("/metrics", make_asgi_app())
   ```
5. Dockerfiles for each service.
6. Add a small load-generator container that hits the frontend ~3 RPS continuously.
7. Wire all four into `docker-compose.dev.yml`.

**Deliverable**: `docker compose up frontend backend db load-gen` produces continuous traffic. Hitting `POST http://localhost:8001/admin/fail` causes the backend to return 503s.

**Pitfalls**:
- Don't make the dummy app fancy. Three services max.
- Make the failure mode reliable — the chaos demo has to fail predictably.

---

### Phase 2 — Observability Plumbing · Half day

**Goal**: Prometheus running and scraping the dummy app.

**Steps**:

1. Add Prometheus to compose:
   ```yaml
   prometheus:
     image: prom/prometheus:v2.55.0
     ports: ["9090:9090"]
     volumes: ["./infra/prometheus.yml:/etc/prometheus/prometheus.yml:ro"]
   ```
2. Write `infra/prometheus.yml`:
   ```yaml
   global:
     scrape_interval: 15s
   scrape_configs:
     - job_name: dummy
       static_configs:
         - targets: [frontend:8000, backend:8001]
   ```
3. (Optional) Add Grafana with a pre-provisioned Prometheus datasource for human visibility.

**Deliverable**: Open http://localhost:9090, query `http_requests_total{service="backend"}` → see real numbers.

**Pitfalls**:
- Don't pin `latest` for Prometheus — pin a version.
- Prometheus container name must match what services use as target hostname (`backend:8001`, not `localhost:8001`).

---

### Phase 3 — Agent Domain Core · 2 days

**Goal**: Pure-Python business model with zero infrastructure dependencies.

**Steps**:

1. `pyproject.toml` with `fastapi`, `pydantic`, `pytest` (no infra deps yet).
2. **Value objects** (`domain/value_objects/`):
   - `Severity` (P1–P4 enum with target SLAs)
   - `ConfidenceScore` (0–1 with `is_actionable` ≥ 0.7)
   - `IncidentId` (`INC-<uuid>`)
   - `ServiceName` (DNS-label validation)
3. **Entities** (`domain/entities/incident.py`):
   - `Incident` aggregate with state machine: `DETECTED → TRIAGED → DIAGNOSING → AWAITING_APPROVAL → EXECUTING → VERIFYING → RESOLVED`
   - Methods: `detect()`, `triage()`, `record_evidence()`, `record_rca()`, `propose_action()`, `record_execution_result()`, `record_verification()`, `resolve()`
4. **Domain events** (`domain/events/`): one event per state transition.
5. **Ports** (`domain/ports/`):
   - `LLMPort`, `MetricsPort`, `KnowledgePort`, `KubernetesPort`, `ApprovalNotificationPort`
   - `IncidentRepository`, `UnitOfWork`
6. **Unit tests** for everything in domain. Should pass without Docker.

**Deliverable**: `pytest tests/unit/` passes. No infrastructure imports anywhere in `domain/`.

**Pitfalls**:
- Don't import `sqlalchemy`, `httpx`, `kubernetes`, or anything else in `domain/`. If you're tempted, you're doing it wrong.
- Use `dataclass(slots=True, frozen=True)` for value objects to lock them down.

---

### Phase 4 — Application Layer (Use Cases) · 2 days

**Goal**: Orchestrate domain objects through ports — still no concrete infrastructure.

**Steps**:

1. Use cases as classes with one async `execute(input)` method:
   - `DetectIncidentUseCase` (dedup against active incidents for the service)
   - `TriageIncidentUseCase` (compute severity)
   - `GatherEvidenceUseCase` (parallel calls to MetricsPort, KubernetesPort)
   - `DiagnoseIncidentUseCase` (calls LLMPort + KnowledgePort, structured output)
   - `ProposeRemediationUseCase` (LLM picks from allowed actions)
   - `RequestApprovalUseCase`, `ResolveApprovalUseCase`
   - `ExecuteFixUseCase`, `VerifyResolutionUseCase`
   - `GeneratePostmortemUseCase`
   - `AnswerOperationalQueryUseCase` (for chat)
2. Constructor-injected dependencies (no global state).
3. Unit tests with **fake** UnitOfWork + fake ports (in-memory dicts).

**Deliverable**: Tests demonstrate the full happy-path lifecycle without any real infrastructure.

**Pitfalls**:
- Resist the urge to start adding LangGraph here — keep use cases plain.
- Resist the urge to inline LLM prompts in domain code; keep them in the use case.

---

### Phase 5 — Infrastructure Adapters · 3 days

**Goal**: Real implementations of ports.

**Steps**:

1. **OpenRouter LLM adapter** (`infrastructure/llm/openrouter_adapter.py`):
   - Use `openai` SDK with `base_url=https://openrouter.ai/api/v1`
   - `complete()` and `complete_structured(json_schema)` methods
   - Tenacity retries
2. **Sentence-Transformers embeddings adapter**:
   - Model `sentence-transformers/all-MiniLM-L6-v2` (384 dims, CPU, free)
   - Lazy load in a thread (`asyncio.to_thread`)
3. **Qdrant adapter**:
   - `ensure_collection()` (idempotent create)
   - `search(query, kinds?, service?, limit=5)`
   - `upsert(docs)` with deterministic point IDs
4. **Prometheus adapter**:
   - Canonical metric name → PromQL template
   - `query_range()` over a TimeWindow
5. **Kubernetes adapter** (`kubernetes-asyncio`):
   - `list_pods()`, `restart_pod()`, `rollout_restart()`, `scale_deployment()`
   - Auto-detect in-cluster vs. kubeconfig
6. **Postgres repository** (SQLAlchemy async):
   - 3 tables: `incidents`, `approvals`, `incident_events`
   - Alembic migration
   - `SqlAlchemyUnitOfWork` async context manager

**Deliverable**: Each adapter has at least one integration test using `testcontainers` for the real backend.

**Pitfalls**:
- Pin `openai`, `qdrant-client`, `kubernetes-asyncio` versions.
- For the Postgres event store, **flush after adding the parent incident before adding events** — otherwise FK violations.
- Don't try to use LangGraph's Postgres checkpointer with SQLAlchemy. Use psycopg connection pool separately.

---

### Phase 6 — Knowledge Base Seed · Half day

**Goal**: 5–10 markdown runbooks indexed in Qdrant so RAG returns useful context.

**Steps**:

1. Create `knowledge_base/runbooks/`:
   - `RB-503.md` — service returning 503s
   - `RB-CRASHLOOP.md` — pod CrashLoopBackOff
   - `RB-OOM.md` — OOMKilled
   - `RB-LATENCY.md` — high p99 latency
   - `RB-DB-CONN.md` — connection pool exhaustion
2. Each runbook has YAML frontmatter (`id`, `kind: runbook`, `service`, `title`) + markdown body with symptoms / diagnosis / remediation.
3. Write `scripts/seed_knowledge_base.py`:
   - Walks the directory
   - Parses frontmatter
   - Embeds each doc
   - Upserts into Qdrant with metadata
4. Run it once locally.

**Deliverable**: `curl http://localhost:6333/collections/sre_knowledge` shows 5+ documents indexed.

**Pitfalls**:
- Keep runbooks under ~600 chars in the body — embeddings work better on focused chunks.
- Always include a `service` metadata field so RAG can filter.

---

### Phase 7 — LangGraph State Machine · 2 days

**Goal**: Wire the use cases into a durable state machine with HIL pause.

**Steps**:

1. Add `langgraph` to `pyproject.toml`.
2. Define `AgentState` as `TypedDict` (must be JSON-serializable). Reducers: `_replace_scalar`, `_extend_list`.
3. `AgentNodes` class — one method per graph node (`detect_node`, `triage_node`, ...).
   - Each node: take state, call use case, return partial state.
   - In-memory cache for non-serializable objects (e.g., evidence packs) keyed by `incident_id`.
4. `AgentGraphFactory.build(checkpointer)`:
   - Add nodes
   - Add edges (sequential up to `propose`, then conditional)
   - `interrupt_before=["execute"]` to pause for HIL
5. Use `MemorySaver` for now (or Postgres later).

**Deliverable**: A test calls `graph.astream(state)` and watches it pause at the `execute` step.

**Pitfalls**:
- Don't put complex objects in `AgentState` — checkpointer serializes everything to JSON.
- `interrupt_before` only triggers if a checkpointer is set.
- LangGraph's API changes between minor versions — pin it.

---

### Phase 8 — FastAPI Interface Layer · 2 days

**Goal**: HTTP endpoints to drive the system.

**Steps**:

1. `interface/rest/app.py` with FastAPI factory + lifespan:
   - In `lifespan`: build container (DI), open checkpointer, build graph, start saga
2. Routers:
   - `POST /signals` (kick off agent run in background task)
   - `GET  /incidents` (list active incidents)
   - `GET  /incidents/{id}` (detail with RCA + proposed action)
   - `POST /approvals/resolve` (approve/reject HIL — resumes graph)
   - `POST /chat` (calls `AnswerOperationalQueryUseCase`)
   - `GET  /healthz`, `/readyz`, `/metrics`
3. Pydantic schemas for all I/O.
4. CORS middleware (`allow_origins=["*"]` for local dev).

**Deliverable**: Hit `/signals` with curl → see incident appear in DB.

**Pitfalls**:
- Don't run the agent graph **inside** the request handler — kick it off as a background asyncio task and return 202 immediately. Otherwise requests time out.
- Add the agent run task to `request.app.state.background_tasks` so it doesn't get garbage-collected.

---

### Phase 9 — Approval Saga · 1 day

**Goal**: Background worker that escalates pending approvals on timeout.

**Steps**:

1. `application/saga/approval_saga.py`:
   - `ApprovalSagaScheduler` — wakes every 15s
   - Scans open approvals, escalates if TTL exceeded
   - For MVP: just one escalation step (primary → fallback)
2. Started from FastAPI lifespan, stopped on shutdown.
3. Triggered re-notifications go to the dashboard (browser polling) or Teams.

**Deliverable**: Submit an incident requiring HIL → don't approve → after 5 min it's marked escalated.

**Pitfalls**:
- Use `asyncio.create_task` and store the task reference, otherwise it gets GC'd.
- `await asyncio.sleep` between ticks, not `time.sleep`.

---

### Phase 10 — Dashboard (Next.js) · 3 days

**Goal**: Two pages — incidents list/detail, and chat.

**Steps**:

1. `npx create-next-app@latest dashboard --typescript --tailwind --app`
2. Install `swr`, `react-markdown`, `remark-gfm`.
3. `lib/api.ts` — typed client for the agent's REST API.
4. Pages:
   - `/` — list of active incidents with severity badges, click → detail
   - `/incidents/[id]` — RCA hypotheses, proposed action, **Approve/Reject buttons** that POST to `/approvals/resolve`
   - `/chat` — chat UI with markdown rendering, suggestion chips, citation pills
5. Dockerfile (multi-stage, Next.js standalone output).
6. **CRITICAL**: Pass `NEXT_PUBLIC_API_URL` as a **build-time** ARG in Dockerfile (Next.js bakes `NEXT_PUBLIC_*` vars into client JS at build).

**Deliverable**: Open http://localhost:3000 → see incidents → click → approve in browser → fix runs.

**Pitfalls**:
- Tailwind v3 + Next.js 14 is the stable combo.
- For ESLint blocking the build over unescaped quotes: add `"react/no-unescaped-entities": "off"` to `.eslintrc.json`.
- If port 3000 is taken, map to `3030:3000` in docker-compose.

---

### Phase 11 — Chaos Injection UI · Half day

**Goal**: A button that breaks the dummy app and notifies the agent.

**Steps**:

1. Streamlit app `chaos-ui/app.py` with 3 buttons:
   - "Inject 503s on backend" → `POST http://backend:8001/admin/fail` then `POST http://agent:8000/signals`
   - "Heal backend" → `POST http://backend:8001/admin/heal`
   - "Restart backend pod" (only relevant in K8s mode)
2. Each button shows the response status.
3. Wire into compose.

**Deliverable**: Click "Inject 503s" → backend starts returning 503 → agent's `/signals` is hit → incident appears in dashboard within seconds.

**Pitfalls**:
- Streamlit's container hostname inside docker-compose must match the service name (`backend`, not `localhost`).

---

### Phase 12 — End-to-End Demo + Polish · 2 days

**Goal**: A 3-minute demo you can hand to a stranger.

**Steps**:

1. Write `demo.md`:
   ```
   1. Open dashboard (http://localhost:3000)         — all green
   2. Open chaos UI (http://localhost:8501)          — second tab
   3. Click "Inject 503s on backend"                 — break it
   4. Watch dashboard                                — incident appears
   5. Click incident                                 — RCA + proposed restart
   6. Click "Approve"                                — agent fixes
   7. Watch dashboard                                — incident resolved
   8. Open /chat                                     — ask "what just happened?"
   9. Agent answers with timeline + RCA citing runbook
   ```
2. Polish:
   - Loading spinners
   - Error states
   - Empty states with helpful copy
3. Record a screen capture of the demo for posterity.
4. Write `README.md` with quickstart:
   ```
   git clone ... && cd sre-agent
   cp .env.example .env  # add your OpenRouter key
   make dev-up           # docker compose up
   open http://localhost:3000
   ```

**Deliverable**: A friend can clone the repo, add their OpenRouter key, and run the full demo without your help.

---

## Total Effort & Calendar

| Phase | Days | Cumulative |
|-------|-----:|-----------:|
| 0 — Repo scaffolding | 0.5 | 0.5 |
| 1 — Dummy workload | 1 | 1.5 |
| 2 — Observability plumbing | 0.5 | 2 |
| 3 — Agent domain core | 2 | 4 |
| 4 — Application layer | 2 | 6 |
| 5 — Infrastructure adapters | 3 | 9 |
| 6 — Knowledge base seed | 0.5 | 9.5 |
| 7 — LangGraph state machine | 2 | 11.5 |
| 8 — FastAPI interface | 2 | 13.5 |
| 9 — Approval saga | 1 | 14.5 |
| 10 — Dashboard | 3 | 17.5 |
| 11 — Chaos UI | 0.5 | 18 |
| 12 — Demo + polish | 2 | 20 |

**Total: ~20 working days = 4 weeks of focused engineering.**

Add 1–2 weeks of slack for first-time learning of LangGraph, hexagonal architecture, etc. → **6 weeks** is a realistic MVP delivery for one engineer.

---

## Common Pitfalls (Top 10)

1. **Skipping hexagonal layering early** — easy to do, painful to refactor. Enforce with `import-linter` from week 1.
2. **Putting complex objects in LangGraph state** — they have to JSON-serialize for the checkpointer. Use a memory cache keyed by ID for big objects.
3. **Running the agent graph inside the request handler** — request times out. Always background-task it.
4. **Forgetting `NEXT_PUBLIC_*` is a build-time substitution** — runtime env var changes won't affect client JS unless you rebuild.
5. **Port collisions on localhost** — Next.js wants 3000; Grafana wants 3000; lots of dev tools want 3000. Pick non-overlapping ports.
6. **Pinning the wrong LLM model name** — model IDs evolve (`anthropic/claude-3.5-sonnet` → `anthropic/claude-sonnet-4.5`). Make it env-configurable.
7. **Forgetting to flush before inserting child rows** — SQLAlchemy with FK constraints + multiple inserts in same UoW: explicit `flush()` between parent and child.
8. **Loading sentence-transformers eagerly at startup** — slow boot. Use lazy load + async lock.
9. **Treating Prometheus and Loki as the same thing** — Prometheus stores metrics (numbers), Loki stores logs (text). Both useful, different APIs.
10. **Trying to integrate Microsoft Teams during the MVP** — Bot Framework setup, App Registration, manifest sideload — easy to lose 3 days. Defer to post-MVP.

---

## Definition of Done (MVP Acceptance)

The MVP is "done" when **all** of these are true:

- [ ] `git clone` + `cp .env.example .env` (set OpenRouter key) + `make dev-up` brings the full stack online in under 5 minutes.
- [ ] Demo flow takes 3 minutes from chaos injection to resolved incident.
- [ ] Agent's RCA includes the cited runbook ID.
- [ ] HIL approval works in the browser (Approve / Reject).
- [ ] Approve → fix actually happens (`kubectl get pods` shows the new pod).
- [ ] Reject → fix is NOT executed.
- [ ] After resolution, `/chat` answers questions about the incident with markdown.
- [ ] No infrastructure imports leak into `domain/` (verified by `import-linter` in CI).
- [ ] Unit tests pass (`pytest tests/unit/`) without docker.
- [ ] At least one integration test passes (`pytest tests/integration/`) with testcontainers.

---

## What to Build After MVP (priority order)

Once MVP ships and you've shown it to people, decide based on their feedback. Suggested order:

1. **Microsoft Teams bot** — biggest "wow" factor, gets the agent to where SREs live.
2. **Multi-channel alerting** (Jira + Email) — turns the demo into something operationally usable.
3. **Memory / lessons learnt** — every escalation captured, agent gets smarter over time.
4. **AKS deployment** — moves it from laptop to a real cluster, tests resilience.
5. **Manager dashboard** (richer views) — gets executive buy-in.
6. **Multi-source observability** (Grafana + Azure Monitor + ELK) — broadens what production environments it can plug into.
7. **Auth + SSO** — required before letting non-developers use it.
8. **Advisory mode** — turns the agent from operational tool into a product.
9. **Avatar on calls** — V3 stretch goal.

For the comprehensive long-term plan, see `docs/V2_BUILD_PLAN.md`.

---

## Appendix A — Recommended Stack for MVP

| Layer | Choice | Pinned version |
|-------|--------|----------------|
| Python | 3.12 | — |
| Web framework | FastAPI | 0.115.x |
| LLM client | openai (with OpenRouter base URL) | 1.54.x |
| Agent orchestration | LangGraph | 0.2.x |
| Vector DB | Qdrant | 1.12.x (Docker) |
| Embeddings | sentence-transformers | 3.2.x |
| State DB | Postgres | 16-alpine |
| ORM | SQLAlchemy + asyncpg | 2.0.x |
| Migrations | Alembic | 1.13.x |
| Metrics | Prometheus | 2.55.x (Docker) |
| Bot framework (post-MVP) | botbuilder-python | 4.16.x |
| Front-end | Next.js | 14.2.x |
| Front-end styling | Tailwind | 3.4.x |
| Markdown rendering | react-markdown + remark-gfm | 9.x + 4.x |
| Chaos UI | Streamlit | 1.40.x |
| Container orchestration | Docker Compose | v2.x |

---

## Appendix B — `.env.example` for the MVP

```dotenv
# LLM
OPENROUTER_API_KEY=sk-or-v1-XXXXXXXXXXXXXXXXXXXX
OPENROUTER_MODEL=anthropic/claude-sonnet-4.5
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Embeddings
EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDINGS_DIM=384

# Persistence
POSTGRES_DSN=postgresql+asyncpg://sre:sre@postgres:5432/sre_agent

# Vector DB
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=sre_knowledge

# Observability
PROMETHEUS_URL=http://prometheus:9090

# Kubernetes (optional for MVP — can be empty if running pure docker-compose)
K8S_IN_CLUSTER=false
TARGET_NAMESPACE=demo-store

# App
APP_ENV=dev
LOG_LEVEL=INFO
HTTP_PORT=8000
RCA_CONFIDENCE_THRESHOLD=0.7
HIL_TIMEOUT_SECONDS=300
```

---

## Appendix C — Daily Standup Checkpoints

If working solo, do a self-standup every morning. Three questions:

1. *What did I ship yesterday?* (Phase X complete? Half complete?)
2. *What will I ship today?* (Concrete deliverable for end of day)
3. *What's blocking me?* (LLM API down? K8s setup taking forever? Move on; flag the blocker.)

If a phase takes more than 2× the estimate, **stop and ask why**:
- Are you over-engineering? (Common — drop scope.)
- Are you fighting a tool? (Try a simpler one or a workaround.)
- Did the requirements creep? (Re-scope to MVP.)

---

## Closing Thought

The MVP is not the product — it's a **proof of life**. Once people see the loop work end-to-end, they'll have opinions about what to build next. Get there fast, then iterate based on real feedback rather than guessing.

Ship it.
