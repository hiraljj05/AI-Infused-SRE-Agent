# SRE Agent Platform V2 — Full Build Plan

**Document type**: Phased delivery plan
**Audience**: Engineering team executing the build, project leadership tracking progress
**Version**: 2.0 (V2 scope — major capability expansion over V1)
**Companion documents**: `docs/HLD.md`, `docs/LLD.md`, `docs/PROJECT_PLAN.md`

---

## 0. Context — What V2 Adds Over V1

V1 delivered the core incident loop (detect → diagnose → propose → HIL → execute → verify → postmortem) with a Microsoft Teams chatbot, web dashboard, and demo-grade infrastructure on Azure AKS.

V2 expands the agent into a full operational platform:

| Theme | V1 | V2 |
|-------|----|----|
| App onboarding | Edit YAML manually | Self-service wizard, DB-backed |
| Alerting | Teams only | Jira + Email + Teams fan-out, project-aware routing |
| K8s actions | 5 | 18 (incl. patch limits, exec, generic kubectl) |
| Chatbot | Read-only Q&A | Active operator (investigate + execute) |
| SLA tracking | Implicit | Explicit per-priority ack/RCA/resolve SLAs with breach escalation |
| Memory | Postmortem in vector DB | Structured lessons-learnt with LLM extraction + similarity-first lookup |
| Human escalation | Approval-only | Capture what humans did → feed memory → expand auto-fix scope over time |
| Observability sources | Prometheus | Prometheus + Grafana + Loki + ELK + Azure Monitor |
| Dashboard | Operations view | Full manager dashboard with 8 views (cost, attribution, reports) |
| Advisory | None | New-project SRE-stack consultation with checklist generator |
| Auth | None | Azure AD OIDC + role-based action gates |
| Avatar on calls | — | V3 (deferred) |

---

## 1. Plan Structure at a Glance

19 phases across 4 tracks. Foundation first; then 3 parallel tracks; then hardening; then deploy.

| Stage | Phases | Track | Calendar weeks |
|-------|--------|-------|----------------|
| **Foundation** | P1–P3 | sequential | Weeks 1–2 |
| **Core operational** | P4–P6 | Track A | Weeks 3–5 |
| **Memory & learning** | P7–P9 | Track B (parallel) | Weeks 3–4 |
| **Observability inputs** | P10–P12 | Track C (parallel) | Weeks 3–5 |
| **Manager UX** | P13–P14 | Track A continued | Weeks 6–7 |
| **Advisory** | P15 | independent | Week 6 |
| **Hardening** | P16–P18 | sequential | Week 8 |
| **Stretch** | P19 | deferred to V3 | — |

**Total: ~8 weeks** with one dev on critical path + parallelisable extras.
**Solo dev**: ~12 weeks.

---

## 2. Phase Catalogue

### Foundation Block — must finish before anything else

#### P1 — Project + App Registry (DB-backed) · 3 days

- New tables: `projects`, `apps`, `app_owners`, `app_channels`
- SQLAlchemy ORM + Alembic migration `0002_registry.py`
- Repositories: `ProjectRepository`, `AppRepository`
- REST CRUD: `/api/projects`, `/api/apps`
- New domain entities: `Project`, `App`
- Replaces the old YAML-based service catalogue (kept for backward compatibility)

#### P2 — App Onboarding Wizard · 2 days

- Dashboard page: `/apps/new` — form (name, owner, tier, namespace, channels, runbook template)
- Backend: `OnboardAppUseCase`
  - Validates inputs against K8s API
  - INSERTs project/app rows
  - Generates Grafana dashboard JSON from template, POSTs to Grafana API
  - Adds Prometheus scrape annotations to existing pods (or generates ServiceMonitor CRD)
  - Seeds runbook stub in Qdrant
- "App registered" success page with links to dashboard + Jira + runbook

#### P3 — Multi-Channel Alerting Fan-Out · 5 days

- New ports: `JiraPort`, `EmailPort`
- Adapters:
  - `JiraCloudAdapter` (Atlassian Cloud REST v3)
  - `SmtpEmailAdapter` (default; falls back to log-only for dev)
- New use case: `CreateIncidentTicketUseCase` — fan-out to Jira + Email + Teams in parallel
- Project-aware routing: looks up app → project → channels (Teams ID, Jira project key, email list)
- Auto-ack on Jira immediately after creation (closes SLA-ack timer)
- Wired into existing incident detection flow as a new node BEFORE evidence gathering

**Foundation deliverable**: A fresh app can be onboarded in ~30s; an alert on it creates a Jira ticket, sends an email, and posts a Teams card.

---

### Track A — Operational Core (after Foundation)

#### P4 — Extended Kubernetes Toolkit · 4 days

Expand allowed playbook actions from 5 → 18:

| Action | Class | HIL? |
|--------|-------|------|
| `restart_pod` | LOW | no |
| `rollout_restart` | LOW | no |
| `flush_cache` | LOW | no |
| `clear_redis_eviction` | LOW | no |
| `drain_connections` | LOW | no |
| `delete_completed_jobs` | LOW | no |
| `scale_deployment` | MEDIUM | yes |
| `patch_memory_limit` | MEDIUM | yes |
| `patch_cpu_limit` | MEDIUM | yes |
| `cordon_node` | MEDIUM | yes |
| `restart_statefulset` | MEDIUM | yes |
| `apply_patch` (image bump) | MEDIUM | yes (cure flow) |
| `rollback_deployment` | HIGH | yes |
| `failover_to_replica` | HIGH | yes |
| `exec_into_pod` (read-only commands) | HIGH | yes |
| `kubectl_exec` (generic, allowlisted verbs) | HIGH | yes |
| `taint_node` | HIGH | yes |
| `delete_pvc` | CRITICAL | yes (incident commander only) |

- Each action is a parameterised function plus a verb allow-list for `kubectl_exec`
- Action class drives HIL routing
- Adaptive Card shows the EXACT command before approval

#### P5 — Chatbot as Active Operator · 5 days

- New use case: `ParseChatIntentUseCase` — LLM extracts `(intent, app, action?, params?)` from free text
- Intents: `query`, `investigate_app`, `propose_action`, `execute_action`, `show_history`
- Investigation flow reuses `GatherEvidenceUseCase` + `DiagnoseIncidentUseCase` directly
- Action-triggering flow uses the same risk-class routing as auto-detected incidents
- Suggestion buttons in chat replies (1/2/3/4 choices) — each is a follow-up intent
- Multi-turn conversation state stored in Redis (TTL 30 min)
- Identity propagation: chat request carries authenticated user → `caused_by: user:<email>` in audit log
- Same chatbot brain works in Dashboard `/chat` AND Teams DM/mention

#### P6 — SLA-Driven Incident Management · 3 days

SLA matrix per priority:

| Sev | Ack | RCA | Resolve |
|-----|-----|-----|---------|
| P0 | 2 min | 10 min | 30 min |
| P1 | 5 min | 15 min | 1 hr |
| P2 | 15 min | 30 min | 4 hr |
| P3 | 1 hr | 4 hr | 24 hr |

- New entity: `SLATracker` per incident with `(sla_type, due_at, status)`
- New saga: `SLAMonitorScheduler` — wakes every 30s, posts "50% breached" warnings, triggers escalation on full breach
- Auto-ack: incident creation event → automatic ack within 30s (since the agent created the ticket)
- RCA SLA timer satisfied on `RCAGenerated` event
- Resolve SLA satisfied on `IncidentResolved` event
- Breach events fan out via P3 channels with breach context

---

### Track B — Memory & Learning (parallel to Track A)

#### P7 — Structured Lessons-Learnt Entity · 3 days

- New table `lessons_learnt`:
  - `id`, `incident_id`, `app_id`, `project_id`
  - `issue_category` (enum: `connection_pool`, `oom`, `latency`, `deploy_regression`, `network`, ...)
  - `root_cause` (text)
  - `fix_applied` (text + structured action ref)
  - `resolver` (`agent` | `user:<email>`)
  - `resolution_minutes`
  - `tags` (array)
  - `confidence` (LLM extraction confidence)
  - `human_verified` (boolean)
- New use case: `ExtractLessonsLearntUseCase` — runs after postmortem published
- LLM structured output extracts the fields from postmortem text
- Indexes the lesson into Qdrant (separate collection: `lessons_learnt`) for vector retrieval

#### P8 — Human Resolution Capture (Hybrid) · 3 days

- "Close Incident" form on the dashboard:
  - "What did you do?" (dropdown of common actions + free text)
  - "Why did it work?" (free text)
  - "Could agent do this next time?" (yes / no / with-approval)
  - "Tags" (auto-suggested + custom)
- Auto-fill from K8s audit log:
  - New adapter: `K8sAuditLogReader` — reads from in-cluster audit policy or Azure Activity Log
  - Pre-fills the form with detected commands by user during the incident window
- Human reviews and confirms → triggers `ExtractLessonsLearntUseCase`
- Stored against the user's identity for accountability

#### P9 — Memory-First Lookup · 2 days

- New node in LangGraph **between TRIAGE and GATHER**: `find_similar_incidents`
- Calls `FindSimilarIncidentsUseCase`:
  - Vector search Qdrant `lessons_learnt` collection
  - Filters: same app, same project, same issue category if known
  - Returns top 3 with similarity scores
- If top match ≥ 0.85: short-circuit to that fix (after HIL if action class is non-LOW)
- Below 0.85: continues to full evidence gathering, but the similar incidents are added to the LLM context for diagnosis
- Surfaces in Jira ticket comment: *"Similar past incidents: [INC-4288 87%, INC-3902 62%]"*

---

### Track C — Observability Inputs (parallel to Tracks A & B)

#### P10 — Grafana Dashboard Reader + Alert Webhook · 3 days

- New adapter: `GrafanaApiAdapter`
  - `list_dashboards()`, `get_dashboard(uid)`, `list_alert_rules()`
  - Reads alert thresholds defined in Grafana
- New endpoint: `POST /webhooks/grafana` — receives Grafana alert payload
- Translates Grafana alert → internal `Signal` → triggers agent flow
- New endpoint: `GET /apps/{id}/dashboards` — returns Grafana dashboards linked to this app

#### P11 — ELK / Elasticsearch Adapter · 3 days

- New adapter: `ElasticsearchLogsAdapter` implementing `LogsPort`
- Same interface as `LokiLogsAdapter`
- Auto-detect: if `ELASTICSEARCH_URL` is set, prefer ELK; else use Loki
- Composite adapter: `MultiSourceLogsAdapter` queries both and merges results

#### P12 — Azure Monitor Adapter · 4 days

- New adapter: `AzureMonitorMetricsAdapter` implementing `MetricsPort`
- Uses `azure-monitor-query` SDK
- New adapter: `AzureMonitorAlertsAdapter` — receives via Event Grid webhook
- New endpoint: `POST /webhooks/azure-monitor`
- Composite metrics adapter: queries Prometheus + Azure Monitor + merges by canonical metric name

---

### Manager UX (after some data exists)

#### P13 — Full Manager Dashboard · 7 days

8 views, listed in priority order:

1. **Overview** — service health map, live incidents, agent-vs-human donut, MTTR gauge, on-call workload
2. **Apps** — per-app: SLO compliance, MTTR, MTTD, error budget burn-down, recent incidents
3. **Incidents** — full table with filters; click → timeline view (every event with attribution)
4. **People** — per-engineer: incidents handled, avg response time, fix success rate
5. **Knowledge** — runbook library, lessons-learnt explorer, search
6. **Reports** — weekly digest, monthly compliance, exports
7. **Settings** — apps/projects/owners CRUD, SLO targets, allowed actions per app
8. **Cost** — LLM tokens per app/incident, infra cost breakdown

Tech: Next.js charts (Recharts), shadcn/ui components, server-side data fetching for big lists.

#### P14 — Reports & Auto-Digest · 3 days

- Weekly cron job: aggregates last week's data → posts summary to Teams `#sre-weekly` channel
- Monthly export: CSV (incidents, postmortems) + PDF (executive summary with charts)
- Postmortem completeness rate calculator
- Compliance audit log export (signed CSV)

---

### Independent Track

#### P15 — Advisory Mode · 5 days

- New use case: `RunAdvisoryConversationUseCase`
- LangGraph mini-flow: discovery questions → recommendation → checklist generation
- New knowledge base collection: `recommended_stacks` indexed by `(cloud × workload × scale × compliance)`
- Generates markdown checklist + downloadable PDF
- Entry points: dashboard `/advisor` page + Teams `@SRE-Agent advise me on a new project`

---

### Hardening

#### P16 — Auth + SSO · 3 days

- Azure AD OIDC for the dashboard
- JWT validation middleware on FastAPI
- Identity propagated from Teams (Bot Framework provides AAD object ID)
- Role-based gates on actions (only on-call / lead can approve high-risk actions)
- Audit `caused_by` field always populated with real identity

#### P17 — Compliance Polish · 2 days

- 36-month retention enforcement (cron job + soft-delete)
- PII detection + masking before LLM input (already exists; tighten)
- Encryption at rest (Azure-managed keys verification)
- Audit log integrity check (append-only DB grant)

#### P18 — Production Deploy to AKS · 3 days

- Helm apply: platform → sre-agent → dummy-app → chaos-ui → dashboard
- Sealed Secrets for OpenRouter, Jira, Email, Bot creds
- Argo CD app-of-apps wired
- Smoke tests post-deploy
- Backup cron: Postgres + Qdrant snapshots to Azure Blob

---

### Deferred (V3)

#### P19 — Avatar on Calls · 15 days

Azure Speech (STT/TTS) + real-time Bot Framework + Teams Live Meeting bot. Standalone effort. Not on the V2 critical path.

---

## 3. Dependency Graph

```
              P1 ──► P2 ──► P3
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
        Track A           Track B           Track C
        P4 ─► P5 ─► P6    P7 ─► P8 ─► P9   P10  P11  P12
                              │                 │
                              ▼                 ▼
                          (memory feeds)    (sources feed)
                              │                 │
                              ▼                 ▼
                                P13 ─► P14
                                   │
                                   ▼
                                 P15 (independent)
                                   │
                                   ▼
                            P16 ─► P17 ─► P18
                                   │
                                   ▼
                              [V3: P19]
```

---

## 4. Milestone Demos

| Milestone | After phase | Demo |
|-----------|-------------|------|
| **M1: "App onboarded → alert fans out"** | P3 | Add app via wizard → trigger fake alert → Jira + email + Teams ping all appear |
| **M2: "Chat-driven fix"** | P5 | In chat: *"check payments-api"* → RCA → *"fix it"* → HIL approval → fix runs → verified |
| **M3: "Memory works"** | P9 | Trigger same kind of incident twice; second time agent says *"this is INC-X again, last fix worked, want me to repeat?"* |
| **M4: "Multi-source observability"** | P12 | Fire alerts from Grafana + Azure Monitor + Prometheus → all flow through same agent |
| **M5: "Manager dashboard"** | P13 | Open dashboard → manager sees agent-vs-human split, recurring issues, SLO health |
| **M6: "Advisory works"** | P15 | New project chat → agent generates SRE checklist PDF |
| **M7: "Production"** | P18 | Full stack on AKS, real users, real load |

---

## 5. Total Timeline

| Setup | Solo dev | 2 devs (split tracks) |
|-------|----------|------------------------|
| All phases except P19 | ~12 weeks | ~7 weeks |
| Including P19 (avatar) | ~15 weeks | ~10 weeks |

---

## 6. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Jira API auth setup blocked by org admin | Medium | Build adapter behind feature flag; mock for dev |
| Azure AD OIDC needs tenant config | Medium | Defer to P16; dashboard public-by-default in dev |
| Grafana version differences | Low | Test against Grafana 10 + 11 |
| K8s `kubectl exec` security review | Medium | Strict verb allow-list (`get`, `describe`, `logs`); no `rm`, `delete` |
| Memory of lessons quality drift | Medium | `human_verified` flag; LLM-extracted lessons need approval before high-confidence reuse |
| Cost of LLM at scale | Low | Cache identical prompts; route low-stakes queries to a cheaper model |
| Avatar (P19) scope creep | Medium | Hard-deferred to V3; not blocking V2 |

---

## 7. Capability Decisions (Locked)

These were resolved via stakeholder Q&A and now drive the build:

| Decision | Choice |
|----------|--------|
| App onboarding | Wizard form (Option B): SRE Lead fills form, ~30 sec |
| K8s tool execution | Hybrid (Option C): predefined parameterised actions + generic `kubectl_exec` always behind HIL |
| Human resolution capture | Hybrid: "Close Incident" form (primary) + K8s audit log auto-fill (assistive) |
| Manager dashboard scope | All 8 views, full coverage |
| Chatbot scope | Active operator (Option X): identical capability in Teams and Dashboard |
| Project registry storage | Database (not YAML) with admin UI |
| Multi-channel alerting | Jira + Email + Teams to project-specific recipients |
| Escalation model | Single agent with extended toolkit (no separate specialised agents in V2) |
| Memory loop | Auto-extract from postmortems + capture every human resolution |
| Avatar on calls | Deferred to V3 |

---

## 8. Cross-References

- High-Level Design: `docs/HLD.md`
- Low-Level Design: `docs/LLD.md` (will need an addendum for V2 components)
- Original V1 plan: `docs/PROJECT_PLAN.md`
- Operations runbook: `docs/runbook.md`
- BRD requirement traceability: `docs/brd_traceability.md`
- Architecture Decision Records: `docs/adr/`

---

## 9. Execution Convention

For each phase:

1. Create a feature branch named `phase-NN-<slug>` (e.g., `phase-01-app-registry`)
2. Open a tracking issue listing acceptance criteria from this doc
3. Land changes in PRs that close the issue
4. Demo at the corresponding milestone (M1–M7)
5. Update this doc's checklist when the phase ships

### Phase status tracker

| Phase | Status | Owner | Started | Shipped |
|-------|--------|-------|---------|---------|
| P1 — Project + App Registry | not started | | | |
| P2 — App Onboarding Wizard | not started | | | |
| P3 — Multi-Channel Alerting | not started | | | |
| P4 — Extended K8s Toolkit | not started | | | |
| P5 — Chatbot Active Operator | not started | | | |
| P6 — SLA-Driven Incident Mgmt | not started | | | |
| P7 — Structured Lessons Learnt | not started | | | |
| P8 — Human Resolution Capture | not started | | | |
| P9 — Memory-First Lookup | not started | | | |
| P10 — Grafana Reader + Webhook | not started | | | |
| P11 — ELK Adapter | not started | | | |
| P12 — Azure Monitor Adapter | not started | | | |
| P13 — Full Manager Dashboard | not started | | | |
| P14 — Reports & Auto-Digest | not started | | | |
| P15 — Advisory Mode | not started | | | |
| P16 — Auth + SSO | not started | | | |
| P17 — Compliance Polish | not started | | | |
| P18 — Production Deploy to AKS | not started | | | |
| P19 — Avatar on Calls (V3) | deferred | — | — | — |
