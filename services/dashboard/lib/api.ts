const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/agent";

export type Severity = "P1" | "P2" | "P3" | "P4" | null;

export type RCAHypothesis = {
  description: string;
  confidence: number;
  confidence_label: string;
  supporting_evidence: string[];
  referenced_runbook_ids: string[];
};

export type ProposedAction = {
  name: string;
  parameters: Record<string, string>;
  rationale: string;
  confidence: number;
  requires_hil: boolean;
  blast_radius_level: string;
};

export type IncidentView = {
  id: string;
  service: string;
  status: string;
  severity: Severity;
  initial_signal: string;
  signal_sources: string[];
  detected_at: string;
  resolved_at: string | null;
  rca_hypotheses: RCAHypothesis[];
  proposed_action: ProposedAction | null;
  blast_radius_summary: string | null;
  jira_ticket_key: string | null;
  jira_ticket_url: string | null;
  jira_ticket_status: string | null;
  jira_ticket_status_updated_at: string | null;
};

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    throw new Error(`API ${path} -> ${res.status}`);
  }
  return (await res.json()) as T;
}

export type AuthState =
  | { authenticated: false }
  | { authenticated: true; email: string; name: string; roles: string[] };

export async function fetchAuthState(): Promise<AuthState> {
  return fetchJson<AuthState>("/auth/me");
}

export const AUTH_LOGIN_URL = `${API_BASE}/auth/login`;
export const AUTH_LOGOUT_URL = `${API_BASE}/auth/logout`;

export type AppOwner = { email: string; role: "primary" | "secondary" };

export type AppView = {
  id: string;
  project_id: string;
  name: string;
  namespace: string;
  tier: string;
  owners: AppOwner[];
  runbook_template_id: string;
  grafana_dashboard_uid: string | null;
  enabled: boolean;
  created_at: string;
  metadata: Record<string, string>;
};

export type ProjectView = {
  id: string;
  key: string;
  name: string;
  description: string;
  teams_channel_id: string | null;
  jira_project_key: string | null;
  email_distribution: string | null;
  incident_commander_group: string;
  created_at: string;
};

export type LessonView = {
  id: string;
  incident_id: string;
  app_id: string | null;
  project_id: string | null;
  issue_category: string;
  root_cause: string;
  fix_applied: string;
  resolver: string;
  resolution_minutes: number;
  tags: string[];
  confidence: number;
  human_verified: boolean;
  created_at: string;
};

export type PeopleAggregate = {
  resolver: string;
  total_resolutions: number;
  agent_resolutions: number;
  human_resolutions: number;
  avg_resolution_minutes: number;
  top_categories: { category: string; count: number }[];
};

export type CostBreakdown = {
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  estimated_usd: number;
  by_model: { model: string; tokens: number; usd: number }[];
  by_day: { day: string; tokens: number }[];
  source: string;
  notes: string;
};

export const api = {
  listIncidents: () => fetchJson<IncidentView[]>("/incidents"),
  getIncident: (id: string) => fetchJson<IncidentView>(`/incidents/${id}`),
  ask: (question: string, service?: string) =>
    fetchJson<{ answer: string; cited_docs: string[]; model: string }>("/chat", {
      method: "POST",
      body: JSON.stringify({ question, service }),
    }),
  resolveApproval: (approval_id: string, decision: "approve" | "reject", actor: string, reason?: string) =>
    fetchJson<{ approval_id: string; state: string; finalized: boolean }>("/approvals/resolve", {
      method: "POST",
      body: JSON.stringify({ approval_id, decision, actor, reason }),
    }),
  listOpenApprovals: () => fetchJson<OpenApprovalView[]>("/approvals"),
  listEscalatedIncidents: () =>
    fetchJson<IncidentView[]>("/incidents?status=escalated"),
  forceResolveIncident: (incident_id: string) =>
    fetchJson<{ incident_id: string; service: string; status: string; deployment_restore: string }>(
      `/incidents/_admin/resolve/${incident_id}`,
      { method: "POST" },
    ),
  listPostmortems: () => fetchJson<PostmortemView[]>("/postmortems"),
  getPostmortemForIncident: (incident_id: string) =>
    fetchJson<PostmortemView>(`/postmortems/by-incident/${incident_id}`),
  listApps: () => fetchJson<AppView[]>("/api/apps"),
  getApp: (id: string) => fetchJson<AppView>(`/api/apps/${id}`),
  listProjects: () => fetchJson<ProjectView[]>("/api/projects"),
  listLessons: (params?: { category?: string; resolver?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.category) q.set("category", params.category);
    if (params?.resolver) q.set("resolver", params.resolver);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return fetchJson<LessonView[]>(`/api/lessons${qs ? `?${qs}` : ""}`);
  },
  peopleAggregates: () => fetchJson<PeopleAggregate[]>("/api/people/aggregates"),
  costBreakdown: () => fetchJson<CostBreakdown>("/api/cost/llm-tokens"),
  advise: (body: AdvisorRequest) =>
    fetchJson<AdvisorResponse>("/api/advisor", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listSLA: () => fetchJson<SLATracker[]>("/api/sla?only_open=true"),
  listEvents: (incident_id?: string, limit = 30) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (incident_id) q.set("incident_id", incident_id);
    return fetchJson<EventView[]>(`/api/events?${q.toString()}`);
  },
  listInsights: () => fetchJson<{ services: InsightSummary[] }>("/api/insights"),
  refreshInsights: () =>
    fetchJson<{ refreshed: number; services: string[] }>("/api/insights/refresh", {
      method: "POST",
    }),
  grafanaEmbedUrl: (service: string) =>
    fetchJson<{ service: string; url: string; kind: string }>(
      `/api/insights/embed/${encodeURIComponent(service)}/grafana-url`
    ),
  pushSignal: (body: {
    service: string;
    initial_signal: string;
    signal_sources?: string[];
    namespace?: string;
  }) =>
    fetchJson<{ incident_id: string; status: string; started_agent_run: boolean }>(
      "/signals",
      { method: "POST", body: JSON.stringify(body) }
    ),
  resolveAllIncidents: () =>
    fetchJson<{ incidents_resolved: number; slas_closed: number; approvals_timed_out: number }>(
      "/incidents/_admin/resolve-all",
      { method: "POST" }
    ),
  k8sChaosOOM: (service: string, memory = "8Mi") =>
    fetchJson<{ incident_id: string; patched: string }>(
      `/api/k8s-chaos/oom?service=${encodeURIComponent(service)}&memory=${memory}`,
      { method: "POST" }
    ),
  k8sChaosCPU: (service: string, cpu = "10m") =>
    fetchJson<{ incident_id: string; patched: string }>(
      `/api/k8s-chaos/cpu-throttle?service=${encodeURIComponent(service)}&cpu=${cpu}`,
      { method: "POST" }
    ),
  k8sChaosScaleZero: (service: string) =>
    fetchJson<{ incident_id: string; patched: string }>(
      `/api/k8s-chaos/scale-zero?service=${encodeURIComponent(service)}`,
      { method: "POST" }
    ),
  k8sChaosRestore: (service: string) =>
    fetchJson<{ applied: string[] }>(
      `/api/k8s-chaos/restore?service=${encodeURIComponent(service)}`,
      { method: "POST" }
    ),
  queryLogs: (params: {
    service?: string;
    logql?: string;
    minutes?: number;
    level?: string;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params.service) q.set("service", params.service);
    if (params.logql) q.set("logql", params.logql);
    if (params.minutes) q.set("minutes", String(params.minutes));
    if (params.level) q.set("level", params.level);
    if (params.limit) q.set("limit", String(params.limit));
    return fetchJson<LogsResponse>(`/api/logs?${q.toString()}`);
  },
};

export type SLATracker = {
  id: string;
  incident_id: string;
  sla_type: string;
  severity: string;
  started_at: string;
  due_at: string;
  status: string;
  satisfied_at: string | null;
  elapsed_pct: number;
};

export type EventView = {
  event_id: string;
  incident_id: string;
  event_type: string;
  occurred_at: string;
  caused_by: string;
  payload: Record<string, unknown>;
};

export type InsightView = {
  severity: "info" | "warn" | "critical";
  headline: string;
  evidence: string;
};

export type InsightSummary = {
  service: string;
  window_minutes: number;
  line_count: number;
  error_count: number;
  warn_count: number;
  insights: InsightView[];
  generated_at: string;
  model: string;
};

export type LogLine = {
  timestamp: string;
  level: string;
  message: string;
  source: string;
};

export type LogsResponse = {
  service: string | null;
  logql: string | null;
  minutes: number;
  count: number;
  lines: LogLine[];
};

export type AdvisorRequest = {
  cloud: "azure" | "aws" | "gcp" | "on-prem" | "multi";
  workload_type: "web" | "api" | "batch" | "ml" | "data-pipeline" | "iot" | "other";
  scale: "startup" | "growth" | "enterprise";
  compliance: string[];
  latency_target_ms: number;
  extra_context: string;
};

export type AdvisorResponse = {
  recommendation_markdown: string;
  cited_docs: string[];
  model: string;
};

export type TimelineEntryView = { at: string; event: string };
export type CorrectiveActionView = {
  description: string;
  owner: string;
  due_date: string | null;
  jira_ticket: string | null;
};

export type PostmortemView = {
  id: string;
  incident_id: string;
  title: string;
  summary: string;
  root_cause: string;
  impact: string;
  lessons_learned: string;
  timeline: TimelineEntryView[];
  corrective_actions: CorrectiveActionView[];
  drafted_at: string;
  published_at: string | null;
  signed_off_by: string | null;
  word_count: number;
  is_published: boolean;
  service: string | null;
  severity: Severity;
  initial_signal: string | null;
  detected_at: string | null;
  resolved_at: string | null;
};

export type OpenApprovalView = {
  approval_id: string;
  incident_id: string;
  state: string;
  created_at: string;
  incident_severity: Severity;
  incident_service: string;
  incident_signal: string;
  action_name: string;
  action_rationale: string;
  action_blast_radius: string;
};
