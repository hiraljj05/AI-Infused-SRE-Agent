# SRE Agent Platform — Problem Statement, Story & Solution

> A production-grade AI Site Reliability Engineer that detects real Kubernetes
> failures, diagnoses them with LLM-grounded RAG, requests human approval over
> Microsoft Teams, executes a real `kubectl patch` against AKS, and writes the
> outcome back to Jira — end to end, with a Next.js command center on top.

---

## 1. Problem statement

### 1.1 What's broken in incident response today

Modern SaaS reliability has become a coordination problem more than an
engineering problem. When something breaks in production, the bottleneck isn't
the fix — it's the 25 minutes of human glue around the fix:

| Step | Where time goes today | Human cost |
|---|---|---|
| **Detection** | A Prometheus alert fires in #alerts. Someone notices. | 1–5 min context-switch tax |
| **Triage** | On-call opens 4 tabs (Grafana, Loki, kubectl, runbook wiki) | 5–10 min before they even understand the failure mode |
| **Ticket** | They paste a summary into Jira, tag the right project, set priority | 2–3 min, often skipped, and the post-mortem suffers |
| **RCA** | They walk the deployment history, recent commits, dashboards | 10–20 min, deeply context-dependent |
| **Remediation** | They run `kubectl rollout undo` or `kubectl patch` | 30 sec of typing, gated behind 5 min of "should I?" |
| **Comms** | Tell the channel, update the ticket, notify stakeholders | 3–5 min and often forgotten |
| **Post-mortem** | Two days later, summarize from memory | 60+ min, low quality |

That sequence repeats **every single incident**, even when the failure is one
the team has seen ten times before.

### 1.2 The deeper problem: institutional memory loss

Every incident generates a small amount of *institutional knowledge* — "when
the orders-api shows P99 > 800ms with errors=0, it's the connection pool, not
the DB." That knowledge currently lives in:

- A senior engineer's head (rotates out, leaves the team)
- An ad-hoc Notion page (out of date in 6 months)
- A Slack thread (unsearchable, gone in 90 days on free tier)

So the next on-call rediscovers the same root cause from scratch. **Mean
Time To Resolution stays flat year over year**, even as the team gets better
at writing code.

### 1.3 Why existing tools don't solve this

| Tool category | What it does | What it can't do |
|---|---|---|
| **PagerDuty / Opsgenie** | Routes the page to the right human | Can't diagnose; just hands the panic to a person |
| **Datadog Watchdog** | Detects anomalies | Tells you something is wrong; not what or how to fix |
| **Runbook automation (Rundeck, StackStorm)** | Runs a script when triggered | Pre-canned playbooks; brittle to new failure modes |
| **ChatOps (HuBot etc.)** | Lets you `!restart pod foo` from chat | Still requires the human to know which command to run |
| **GenAI copilots in IDEs** | Help you write code | Don't touch production; don't reason over telemetry |

There's no tool that **reasons over live telemetry, decides what to do, asks
permission, and acts on the cluster** — with full auditability and the
ability to learn from each resolution.

---

## 2. The story we're telling

### 2.1 The 90-second demo narrative

> *"It's 2 AM. The food-orders pod just OOM-killed in production. Watch what
> the agent does — without anyone touching a keyboard."*

1. **Chaos injected** (operator clicks "OOM" in the dashboard)
   The dashboard hits `/api/k8s-chaos/oom` which runs a real `kubectl patch`
   on AKS, dropping the deployment's memory limit to 8Mi. Within 10 seconds
   the pod dies with exit code 137.

2. **Signal received** (~5 seconds later)
   The chaos endpoint POSTs to `/signals` with the failure description.
   The agent's LangGraph state machine boots an incident workflow on a
   per-incident `thread_id`, persisted in Postgres.

3. **Triage + ticket fan-out** (~10 seconds)
   Agent looks up the service in the App registry, finds the owning
   Project, and in parallel:
   - Creates a Jira ticket in the project's `jira_project_key` (real
     Atlassian REST API call — ticket SCRUM-9, etc.)
   - DMs the on-call engineer in Microsoft Teams with a status card
     containing the Jira link
   - (Optionally) emails the project's distribution list

4. **Evidence gathering + RCA** (~20–40 seconds)
   In parallel the agent:
   - Pulls Prometheus metric snapshots (CPU, memory, p99, error rate)
   - Pulls Loki log lines (last 60 min, at INFO+)
   - Calls `kubectl get pods` and reads `restart_count`, `exit_code`
   - Reads the deployment history to spot recent rollouts
   Then calls Claude (via OpenRouter) with the evidence summary + the
   matching runbook chunks (RAG over Qdrant) and asks for ranked RCA
   hypotheses with confidence scores.

5. **Action proposal**
   Agent decides on a remediation: `restart_pods`, `rollback_deployment`,
   `scale_up`, `patch_resource_limits`, etc. Each action carries a
   `blast_radius` (low/medium/high) and a `requires_hil` flag derived from
   `MAX_AUTO_REMEDIATION_BLAST_RADIUS`.

6. **Approval card in Teams**
   For HIL-required actions, the agent posts an Adaptive Card to the
   on-call user's DM with: incident ID, service, severity, **Jira link
   (clickable)**, proposed action, RCA confidence, blast radius, and
   `Approve` / `Reject` buttons.

7. **Human clicks Approve**
   The card POSTs back to `/api/messages`. The agent resumes the LangGraph
   from the `interrupt_before` checkpoint, runs the actual `kubectl patch`
   via the SA-token kubeconfig (no admin creds), waits, then verifies
   metrics returned to baseline.

8. **Resolution + lesson**
   Agent generates a postmortem (LLM), stores a `LessonLearnt` row +
   embedding in Qdrant for next time, comments on the Jira ticket with the
   resolution and MTTR, and posts a green "Resolved" card back to Teams.

The dashboard auto-refreshes every 4 seconds throughout, so a manager
watching it sees the entire workflow play out as a chat-style timeline.

### 2.2 Who this is for

- **The on-call engineer** — gets a smart copilot, not a dumb pager
- **Engineering leadership** — sees MTTR drop and gets clean post-mortems
- **The new hire** — has a system that explains *why* a fix was applied
- **Compliance** — every action is logged with actor + reason + outcome

---

## 3. The full solution we built

### 3.1 Architecture at a glance

```
┌─────────────────────────────────────────────────────────────────┐
│                        Microsoft Teams                          │
│  ┌─────────────┐         ┌──────────────┐    ┌──────────────┐   │
│  │ Status DMs  │         │ Approval     │    │ Q&A chat     │   │
│  │ "🎫 Jira #" │         │ Adaptive Card│    │ "what is..."  │   │
│  └──────▲──────┘         └──────▲───────┘    └──────▲────────┘  │
└─────────┼───────────────────────┼────────────────────┼──────────┘
          │  Bot Framework (ngrok HTTPS tunnel in dev)            │
┌─────────┴───────────────────────┴────────────────────┴──────────┐
│  FastAPI (services/agent)  ◄── Next.js dashboard (services/...)│
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  LangGraph State Machine (per-incident thread_id)         │ │
│  │  detect → triage → ticket → memory_lookup → gather →      │ │
│  │  diagnose → propose → [HIL interrupt] → execute → verify  │ │
│  │  → postmortem → extract_lesson                            │ │
│  └──────────────────────────────────────────────────────────┘  │
│  Hexagonal — domain (entities/ports), application (use cases), │
│  infrastructure (adapters), interface (REST / Bot)             │
└────┬────────┬────────┬────────┬────────┬─────────┬─────────────┘
     │        │        │        │        │         │
   Postgres  Qdrant   Redis  Prometheus Loki    Grafana
   (state)  (RAG)   (cache)  (metrics) (logs) (dashboards)
                                                             │
     OpenRouter ◄── LLM calls (Claude Sonnet 4.5)            │
     Atlassian Jira ◄── REST tickets + comments              │
     Azure AKS ◄────────── kubectl patch via SA token ───────┘
                          (scoped ClusterRole, no admin creds)
```

### 3.2 The 12 demo containers

| Service | Port | Role |
|---|---|---|
| `agent` | 8000 | FastAPI brain, hosts LangGraph + Bot Framework adapter |
| `dashboard` | 3030 | Next.js 14 command center (App Router, Tailwind) |
| `postgres` | 5432 | Incidents, approvals, SLA trackers, lessons, app/project registry |
| `qdrant` | 6333 | Vector store — knowledge base + lesson embeddings |
| `redis` | 6379 | Cache, ephemeral state |
| `prometheus` | 9090 | Scrapes both demo apps + the agent itself |
| `grafana` | 3001 | Dashboards (admin/admin), provisioned per-service |
| `loki` | 3100 | Log aggregation |
| `promtail` | — | Ships docker logs into Loki |
| `portfolio-web` | 8081 | Demo app #1 — Flask blog, generates realistic logs |
| `food-orders` | 8082 | Demo app #2 — Flask order taker, generates realistic logs |
| `chaos-ui` | 8501 | Streamlit panel (legacy; kept for fallback) |

### 3.3 The agent's domain model

We modeled the SRE workflow as proper DDD aggregates so the agent can reason
over them and the database matches the way humans think about incidents:

- **`Incident`** — aggregate root with status (`detected → triaged →
  diagnosing → awaiting_approval → executing → verifying → resolved` /
  `escalated` / `failed`), severity, blast radius, RCA hypotheses, proposed
  action, **and now `jira_ticket_key` + `jira_ticket_url`** so the link
  surfaces everywhere.
- **`Approval`** — saga state for HIL: `notified_primary →
  notified_secondary → escalated_to_commander → approved / rejected /
  timed_out`.
- **`Project` / `App`** — registry that maps a service name to its Jira
  project, Teams channel, on-call rotation, runbook template, and Grafana
  dashboard UID.
- **`SLATracker`** — separate trackers for ack / RCA / resolve, each with a
  due time and `elapsed_pct`.
- **`LessonLearnt`** — a structured row written after every resolution,
  embedded into Qdrant so the next similar incident can find it via vector
  search.
- **`Postmortem`** — full markdown doc generated by the LLM at close-out.

### 3.4 The LangGraph state machine

```
START
  ↓
detect          (writes Incident + IncidentDetected event)
  ↓
triage          (LLM picks severity + blast radius)
  ↓
start_slas      (kicks off ack / RCA / resolve trackers)
  ↓
fan_out_ticket  (parallel: Jira + email + Teams card; persists ticket key on Incident)
  ↓
memory_lookup   (Qdrant search for prior lessons; if HIGH match, biases the proposal)
  ↓
gather_evidence (Prometheus + Loki + kubectl in parallel)
  ↓
diagnose        (LLM: ranked RCA hypotheses with confidence + evidence cites)
  ↓
propose         (LLM: action + parameters + rationale + blast_radius)
  ↓
[branch: requires_hil?]
  ├── yes → notify_hil (Teams Approval Card with Jira link + Open in Jira button)
  │          ↓
  │       interrupt_before('execute')   ← LangGraph pauses, persisted in Postgres
  │          ↓                          ← human clicks Approve in Teams
  │       resume on /api/messages callback
  │
  └── no  → (auto-execute path, only when blast=low and conf > threshold)

execute         (real kubectl patch via SA-token kubeconfig)
  ↓
verify          (re-poll Prometheus for ~30s; confirm metrics returned to baseline)
  ↓
postmortem      (LLM drafts markdown postmortem)
  ↓
extract_lesson  (LLM extracts structured LessonLearnt + writes to Qdrant)
  ↓
END (Incident.resolve())
```

State is **checkpointed in Postgres** per `thread_id` — the agent can crash
and resume mid-flight; it can pause for hours awaiting approval.

### 3.5 Hexagonal architecture (why the code is structured this way)

```
domain/        ← entities + value objects + ports (Protocols), zero IO, fully testable
application/   ← use cases + LangGraph nodes — orchestrate via ports
infrastructure/← adapters that implement ports (Postgres, Qdrant, Loki, k8s, OpenRouter…)
interface/     ← REST routers + Bot handler — the outside world
composition_root.py ← wires everything; the only place that knows the concrete adapters
```

Why this matters in practice:
- The agent has a `LogQueryPort`. Today it's implemented by `LokiAdapter`.
  Tomorrow we add `ElasticsearchAdapter` — the use cases don't change.
- The `TicketingPort` has a `LogOnlyJiraAdapter` for local dev (no creds
  needed) and a real `JiraAdapter` for prod. Same code path.
- Every external call goes through a port, so unit tests use in-memory fakes.

### 3.6 RAG — grounding the LLM

The knowledge base under `knowledge_base/` is read on agent boot and
embedded into Qdrant:

- **`runbooks/`** — `RB-OOMKILL.md`, `RB-POD-CRASHLOOP.md`,
  `RB-PAYMENTS-LATENCY.md`, etc. The agent retrieves the top-k chunks
  before asking the LLM for a fix proposal.
- **`services/`** — per-service YAMLs (owners, SLOs, dependencies,
  dashboards, common failure modes).
- **`policies/`** — what's safe to auto-execute, what needs HIL.
- **`history/`** — sample past incidents.
- **`recommended_stacks/`** — used by the Advisor mode for "what should I
  build on?" questions.
- **`lessons_learnt`** collection in Qdrant — populated automatically from
  every resolution, so the system gets smarter over time.

### 3.7 Real chaos, real Kubernetes

Earlier iterations used mocked failures. The current build does not:

- `POST /api/k8s-chaos/oom?service=food-orders&memory=8Mi` runs a real
  `kubectl patch deployment` against AKS, dropping the memory limit until
  the pod actually OOM-kills with exit code 137.
- `POST /api/k8s-chaos/cpu-throttle` patches CPU limits to 10m to pin
  every request behind throttle queues.
- `POST /api/k8s-chaos/scale-zero` scales the deployment to 0 replicas.
- `POST /api/k8s-chaos/restore` restores healthy defaults
  (memory 256Mi, cpu 500m, replicas 2).

The agent's remediation goes through the **same path** — there is no
"demo mode". When you click Approve, real `kubectl patch` runs.

### 3.8 Microsoft Teams integration

- **AAD app** (SingleTenant) registered via `az ad app create`, with a
  client secret and a service principal so the bot can be used in this
  tenant.
- **Azure Bot Service** points at `https://<ngrok>/api/messages`.
- **Sideloaded Teams app** (`infra/teams/sre-agent-teams-app.zip`) so any
  user in the tenant can DM the bot.
- **Conversation references** are persisted to disk
  (`/app/data/conversation_refs.json`) so the bot can proactively message
  users after a restart.
- **Adaptive Cards** for status updates and approval requests, with
  `Action.OpenUrl` buttons that link straight to the Jira ticket.

### 3.9 Dashboard — the operator command center

Next.js 14 App Router. Twelve pages, all wired to the agent's REST API:

| Route | Purpose |
|---|---|
| `/` | Live ops summary (active incidents, SLA burn, agent activity) |
| `/incidents` | Sortable list of all incidents (status, sev, **Jira ticket**, top RCA) |
| `/incidents/[id]` | Per-incident command center — workflow timeline, agent commentary, AI insights, embedded Grafana, raw logs, RCA hypotheses, **Jira ticket badge with Open-in-Jira link** |
| `/chat` | Conversational interface — same Q&A the Teams bot exposes, with citations |
| `/chaos` | Chaos lab — push real failures to AKS without leaving the app |
| `/apps`, `/apps/new` | App + project registry (onboard a new service) |
| `/knowledge` | Browse the runbook library |
| `/people` | Resolver leaderboard (who closes what) |
| `/cost` | LLM token spend breakdown by model + day |
| `/reports` | Auto-digest exports |
| `/advisor` | "What should I build on?" advisory mode |
| `/settings` | OIDC login, env config snapshot |

Every page polls every 4–10s. Incident list refreshes 5s. The "Agent
Timeline" component on the incident detail page renders agent events as a
chat thread so non-engineers can watch the agent work in real time.

### 3.10 Authentication

- **Bot side** — Bot Framework JWT validation, SingleTenant.
- **Dashboard side** — separate AAD OIDC app, HMAC-signed cookie
  sessions, `auth_required=false` for the demo, flippable to true for
  prod. Admin emails configured via `AUTH_ADMIN_EMAILS`.

### 3.11 Observability of the agent itself

The agent emits Prometheus metrics on `/metrics`:
- `sre_agent_llm_tokens_used_total{model}` — LLM spend tracking
- `sre_agent_incidents_total{status,severity}`
- `sre_agent_actions_executed_total{action,success}`
- Standard FastAPI request timings

These power the `/cost` page in the dashboard and a provisioned Grafana
dashboard.

### 3.12 What we deliberately did NOT build

To stay shippable in the demo window:
- No multi-cluster support (one AKS cluster, one namespace)
- No real OAuth refresh handling for Jira (uses long-lived API tokens)
- No PagerDuty / Slack adapter (Teams + email only)
- No formal RBAC inside the dashboard (just admin emails)
- No on-call schedule integration (uses static `DEFAULT_ON_CALL_*` env vars)
- No load testing or chaos in CI (chaos is a demo button, not an SLO)

All of these are clean extensions because of the hexagonal architecture —
add an adapter, wire it in `composition_root.py`, the use cases don't
change.

---

## 4. Why this matters

### 4.1 The before/after for a single OOMKill incident

| Phase | Without agent | With agent |
|---|---|---|
| Detection | 2 min (someone sees alert) | 5 sec (signal pushed automatically) |
| Triage | 8 min (open tabs, read logs) | 15 sec (agent gathers in parallel) |
| Ticket | 3 min (manual paste) | 2 sec (auto-created with full context) |
| RCA | 12 min (correlate by hand) | 30 sec (LLM + RAG over runbooks) |
| Approval | 0 min (just acted) | 30 sec (Teams card → click) |
| Fix | 30 sec (kubectl patch) | 5 sec (same kubectl patch, by agent) |
| Verify | 5 min (eyeball Grafana) | 30 sec (auto-poll metrics) |
| Postmortem | 60 min (next day, from memory) | 10 sec (LLM-drafted, ready to edit) |
| **Total wall-clock** | **~30 min + 1h post** | **~2 min, postmortem inline** |

### 4.2 The compounding win

The agent also writes a `LessonLearnt` row after every resolution. The
*next* OOMKill incident on the *next* service starts with the agent
already knowing "last time this looked like X, the fix was Y." The
system gets faster the more it's used — the opposite of how human-only
on-call rotations work.

### 4.3 What this proves

You can build a production-grade agentic system on a $150 Azure trial:
- Every adapter is real (Postgres, AKS, Jira, Teams, OpenRouter, Loki…)
- Every action is auditable (event store + structured logs)
- Every dependency is swappable (hexagonal ports)
- Every workflow step is resumable (LangGraph + Postgres checkpointer)
- Every LLM call is cost-tracked (Prometheus counter → /cost page)

That's the bar. Anything less is a slideware demo.

---

## 5. Where to look in the code

| You want to understand… | Read this |
|---|---|
| The whole story | [SETUP.md](SETUP.md) for setup, this file for context |
| The agent's brain | [services/agent/src/sre_agent/application/agent_graph/nodes.py](services/agent/src/sre_agent/application/agent_graph/nodes.py) |
| The fan-out (Jira + email + Teams) | [services/agent/src/sre_agent/application/use_cases/create_incident_ticket.py](services/agent/src/sre_agent/application/use_cases/create_incident_ticket.py) |
| The LLM RCA + proposal prompts | [services/agent/src/sre_agent/application/use_cases/diagnose_incident.py](services/agent/src/sre_agent/application/use_cases/diagnose_incident.py), [propose_remediation.py](services/agent/src/sre_agent/application/use_cases/propose_remediation.py) |
| Real Kubernetes chaos endpoints | [services/agent/src/sre_agent/interface/rest/routers/k8s_chaos.py](services/agent/src/sre_agent/interface/rest/routers/k8s_chaos.py) |
| Teams Adaptive Cards | [services/agent/src/sre_agent/infrastructure/messaging/adaptive_cards.py](services/agent/src/sre_agent/infrastructure/messaging/adaptive_cards.py) |
| Bot conversation persistence | [services/agent/src/sre_agent/infrastructure/messaging/teams_adapter.py](services/agent/src/sre_agent/infrastructure/messaging/teams_adapter.py) |
| Knowledge base content | [knowledge_base/](knowledge_base/) |
| Dashboard incident detail page | [services/dashboard/app/incidents/[id]/page.tsx](services/dashboard/app/incidents/[id]/page.tsx) |
| Composition root (where everything is wired) | [services/agent/src/sre_agent/composition_root.py](services/agent/src/sre_agent/composition_root.py) |

---

*Written 2026-04-23. Build state: V1 + V2 phases P1–P10 complete; real AKS chaos
loop verified end-to-end; Jira ticket linkage now surfaced in dashboard +
Teams cards.*
