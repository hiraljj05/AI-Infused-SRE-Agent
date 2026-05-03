"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Clock,
  Cpu,
  ExternalLink,
  FileText,
  Lightbulb,
  ScrollText,
  Sparkles,
  XCircle,
  Zap,
} from "lucide-react";
import {
  api,
  type EventView,
  type IncidentView,
  type InsightSummary,
  type LogsResponse,
  type PostmortemView,
} from "@/lib/api";
import { JiraStatusBadge } from "@/components/jira-status-badge";

import { GrafanaLogsChart } from "@/components/dashboard-charts";

const SEV_BG: Record<string, string> = {
  P1: "bg-red-50 text-red-700 border-red-200",
  P2: "bg-orange-50 text-orange-700 border-orange-200",
  P3: "bg-amber-50 text-amber-700 border-amber-200",
  P4: "bg-blue-50 text-blue-700 border-blue-200",
};

const STATUS_BG: Record<string, string> = {
  detected: "bg-sky-50 text-sky-700 border-sky-200",
  triaged: "bg-sky-50 text-sky-700 border-sky-200",
  diagnosing: "bg-violet-50 text-violet-700 border-violet-200",
  awaiting_approval: "bg-amber-50 text-amber-700 border-amber-200",
  executing: "bg-violet-50 text-violet-700 border-violet-200",
  verifying: "bg-violet-50 text-violet-700 border-violet-200",
  resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  escalated: "bg-rose-50 text-rose-700 border-rose-200",
  failed: "bg-red-50 text-red-700 border-red-200",
};

const WORKFLOW_STEPS = [
  { id: "detected", label: "Detected", Icon: AlertCircle },
  { id: "triaged", label: "Triaged", Icon: Activity },
  { id: "diagnosing", label: "Diagnosing", Icon: Cpu },
  { id: "awaiting_approval", label: "Approval", Icon: Clock },
  { id: "executing", label: "Executing", Icon: Zap },
  { id: "verifying", label: "Verifying", Icon: CheckCircle2 },
  { id: "resolved", label: "Resolved", Icon: CheckCircle2 },
];

function timeAgo(iso: string | undefined): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`;
}

// ─── workflow timeline ────────────────────────────────────────────────────

function WorkflowTimeline({ status }: { status: string }) {
  const currentIdx = WORKFLOW_STEPS.findIndex((s) => s.id === status);
  const isResolved = status === "resolved";
  const isFailed = status === "failed" || status === "escalated";

  return (
    <div className="card p-4">
      <div className="mb-3 text-[11px] font-bold uppercase tracking-widest text-slate-500 font-sans">
        Workflow
      </div>
      <div className="flex items-center justify-between gap-1 overflow-x-auto">
        {WORKFLOW_STEPS.map((step, idx) => {
          const isActive = idx === currentIdx && !isResolved;
          const isDone = idx < currentIdx || isResolved;
          const isPending = idx > currentIdx;
          const colorBg = isFailed
            ? "bg-rose-100 text-rose-600 border-rose-200"
            : isDone
            ? "bg-emerald-100 text-emerald-600 border-emerald-200"
            : isActive
            ? "bg-brand-100 text-brand-600 border-brand-300 ring-2 ring-brand-400 animate-pulse-slow"
            : "bg-slate-100 text-slate-400 border-slate-200";
          return (
            <div key={step.id} className="flex flex-1 items-center">
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`flex h-9 w-9 items-center justify-center rounded-full border ${colorBg} transition-all duration-300`}
                >
                  <step.Icon size={14} />
                </div>
                <div
                  className={`text-[10px] font-sans ${
                    isActive ? "text-brand-700 font-bold" : isDone ? "text-emerald-700 font-semibold" : "text-slate-400 font-medium"
                  }`}
                >
                  {step.label}
                </div>
              </div>
              {idx < WORKFLOW_STEPS.length - 1 && (
                <div
                  className={`mx-1 h-0.5 flex-1 ${
                    isDone ? "bg-emerald-300" : "bg-slate-200"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── agent commentary (chat-style) ────────────────────────────────────────

function eventBubble(e: EventView): { headline: string; tone: "info" | "ok" | "warn" | "danger" } {
  const p = e.payload as Record<string, unknown>;
  switch (e.event_type) {
    case "IncidentDetected": {
      const svc = (p.service as { value?: string })?.value || "?";
      return { headline: `🚨 Detected on ${svc} — ${String(p.initial_signal || "")}`, tone: "danger" };
    }
    case "IncidentTriaged":
      return {
        headline: `⚖️ Triaged ${String(p.severity || "")} — ${String((p.rationale as string) || "").slice(0, 200)}`,
        tone: "info",
      };
    case "EvidenceGathered":
      return {
        headline: `🔬 Pulled evidence: ${p.metric_snapshot_count} metric snapshots, ${p.log_line_count} log lines`,
        tone: "info",
      };
    case "RCAGenerated": {
      const top = (p.hypotheses as { description?: string; confidence?: { value?: number } }[])?.[0];
      const conf = top?.confidence?.value ? `${Math.round(top.confidence.value * 100)}%` : "?";
      return {
        headline: `🧠 Root cause hypothesis (${conf} confidence):\n${String(top?.description || "")}`,
        tone: "info",
      };
    }
    case "ActionProposed": {
      const blast = (p.blast_radius as { level?: string })?.level || "?";
      return {
        headline: `🔧 Proposing fix: **${String(p.action_name)}** (blast: ${blast}, ${
          p.requires_hil ? "HIL required" : "auto-execute"
        })\n${String(p.rationale || "").slice(0, 300)}`,
        tone: p.requires_hil ? "warn" : "info",
      };
    }
    case "ApprovalRequested":
      return { headline: `✋ Awaiting human approval — paged on-call`, tone: "warn" };
    case "ApprovalResolved":
      return {
        headline: `✅ Approval ${String(p.decision || "")} by ${e.caused_by}`,
        tone: p.decision === "approve" ? "ok" : "danger",
      };
    case "FixExecuted":
      return { headline: `⚡ Executed fix`, tone: "ok" };
    case "ResolutionVerified":
      return { headline: `🎯 Verified: service back to baseline`, tone: "ok" };
    case "IncidentResolved":
      return { headline: `✓ Incident resolved`, tone: "ok" };
    case "PostmortemGenerated":
      return { headline: `📝 Postmortem drafted`, tone: "info" };
    default:
      return { headline: e.event_type, tone: "info" };
  }
}

function AgentCommentary({ incidentId }: { incidentId: string }) {
  const { data: events } = useSWR<EventView[]>(
    `/api/events?incident_id=${incidentId}`,
    () => api.listEvents(incidentId, 100),
    { refreshInterval: 4000 }
  );

  const sorted = (events || []).slice().reverse();

  const toneClass: Record<string, string> = {
    info: "bg-white border-slate-200",
    ok: "bg-emerald-50 border-emerald-200",
    warn: "bg-amber-50 border-amber-200",
    danger: "bg-red-50 border-red-200",
  };

  return (
    <div className="card flex h-full min-h-0 flex-col">
      <div className="flex flex-shrink-0 items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-brand">
            <Bot size={14} className="text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-900">Agent Timeline</div>
            <div className="text-xs text-slate-500">
              {sorted.length} events · auto-refresh 4s
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
          LIVE
        </div>
      </div>
      <div className="scrollbar-thin flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {sorted.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center text-xs text-slate-400">
            <Bot size={28} className="mb-3 opacity-30" />
            <p>No agent activity yet for this incident.</p>
          </div>
        )}
        {sorted.map((e) => {
          const { headline, tone } = eventBubble(e);
          return (
            <div key={e.event_id} className="animate-slide-up flex items-start gap-3">
              <div className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full gradient-brand">
                <Sparkles size={11} className="text-white" />
              </div>
              <div
                className={`flex-1 rounded-2xl rounded-tl-sm border px-3 py-2 shadow-soft ${toneClass[tone]}`}
              >
                <div className="whitespace-pre-line text-[13px] leading-relaxed text-slate-800">
                  {headline}
                </div>
                <div className="mt-1.5 flex items-center gap-2 text-[10px] text-slate-400">
                  <span>{new Date(e.occurred_at).toLocaleTimeString()}</span>
                  <span>·</span>
                  <span>{timeAgo(e.occurred_at)}</span>
                  <span>·</span>
                  <span>{e.caused_by}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── insights panel ───────────────────────────────────────────────────────

const INSIGHT_BADGE: Record<string, string> = {
  critical: "bg-red-50 text-red-700 border-red-200",
  warn: "bg-amber-50 text-amber-700 border-amber-200",
  info: "bg-sky-50 text-sky-700 border-sky-200",
};

function InsightsPanel({ service }: { service: string }) {
  const { data: insight, isLoading } = useSWR<InsightSummary>(
    `insight:${service}`,
    () =>
      fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "/api/agent"}/api/insights/${encodeURIComponent(service)}`,
        { credentials: "include" }
      ).then((r) => r.json()),
    { refreshInterval: 30000 }
  );

  return (
    <div className="card flex flex-col">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-brand-50 text-brand-600">
            <Lightbulb size={12} />
          </div>
          <div className="text-[13px] font-bold text-slate-900 font-sans">AI Log Insights</div>
        </div>
        <div className="text-[10px] text-slate-500 font-sans">
          from <span className="font-mono">{service}</span>
        </div>
      </div>
      <div className="space-y-2 p-3">
        {isLoading && !insight && <div className="skeleton h-16 rounded-lg" />}
        {insight && insight.insights.length === 0 && (
          <div className="text-[11px] text-slate-400 font-sans">No insights yet.</div>
        )}
        {insight?.insights.slice(0, 3).map((ins, i) => (
          <div
            key={i}
            className={`rounded-lg border p-2.5 ${INSIGHT_BADGE[ins.severity]}`}
          >
            <div className="flex items-start gap-2">
              <span className="mt-0.5 flex-shrink-0">
                {ins.severity === "critical" ? (
                  <AlertCircle size={13} />
                ) : ins.severity === "warn" ? (
                  <AlertTriangle size={13} />
                ) : (
                  <CheckCircle2 size={13} />
                )}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-[11px] font-bold leading-snug font-sans">{ins.headline}</div>
                {ins.evidence && (
                  <div className="mt-1 text-[10px] opacity-80 font-sans line-clamp-2">{ins.evidence}</div>
                )}
              </div>
            </div>
          </div>
        ))}
        {insight && (
          <div className="pt-1 text-[9.5px] text-slate-400 font-sans text-right">
            {insight.line_count} lines · {insight.error_count} errors · {insight.warn_count} warns
          </div>
        )}
      </div>
    </div>
  );
}

// ─── grafana embed ────────────────────────────────────────────────────────

function GrafanaEmbed({ service }: { service: string }) {
  const { data } = useSWR<{ url: string; kind: string }>(
    `grafana:${service}`,
    () => api.grafanaEmbedUrl(service)
  );
  const [open, setOpen] = useState(true);

  return (
    <div className="card flex flex-col">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-50">
            <Activity size={14} className="text-amber-600" />
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-900">Grafana</div>
            <div className="text-xs text-slate-500">
              {data?.kind === "dashboard" ? "Provisioned dashboard" : "Loki Explore"}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {data?.url && (
            <a
              href={data.url}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1 text-xs text-brand-600 hover:underline"
            >
              <ExternalLink size={11} />
              Open
            </a>
          )}
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>
      {open && (
        <div className="h-[360px] overflow-hidden rounded-b-xl bg-slate-50">
          {data?.url ? (
            <iframe
              src={data.url}
              className="h-full w-full border-0"
              title="Grafana"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-slate-400">
              Loading Grafana…
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── raw logs (collapsible) ───────────────────────────────────────────────

function RawLogs({ service }: { service: string }) {
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useSWR<LogsResponse>(
    open ? `logs:${service}:60` : null,
    () => api.queryLogs({ service, minutes: 60, limit: 200, level: "DEBUG" }),
    { refreshInterval: open ? 10000 : 0 }
  );
  const lines = data?.lines || [];

  const LEVEL_CLASS: Record<string, string> = {
    DEBUG: "text-slate-400",
    INFO: "text-slate-700",
    WARN: "text-amber-600",
    ERROR: "text-red-600",
    FATAL: "font-semibold text-red-700",
  };

  return (
    <div className="card flex flex-col">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100">
            <ScrollText size={14} className="text-slate-600" />
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-900">Raw logs & Log Volume</div>
            <div className="text-xs text-slate-500">
              {open
                ? `${lines.length} lines · auto-refresh 10s`
                : "Click to expand (insights above are usually enough)"}
            </div>
          </div>
        </div>
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {open && (
        <div className="flex flex-col">
          <div className="border-b border-slate-100 p-4">
            <div className="mb-2 text-xs font-semibold text-slate-700">Log Volume (last 60m)</div>
            <GrafanaLogsChart lines={lines} />
          </div>
          <div className="scrollbar-thin h-[280px] overflow-y-auto bg-slate-950 p-3 font-mono text-[11px] leading-relaxed">
          {isLoading && <div className="text-slate-500">Loading…</div>}
          {!isLoading && lines.length === 0 && (
            <div className="text-slate-500">No log lines in last 60 minutes.</div>
          )}
          {lines.map((ln, i) => {
            const t = new Date(ln.timestamp);
            const ts = `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}:${String(t.getSeconds()).padStart(2, "0")}`;
            return (
              <div key={i} className="flex gap-2">
                <span className="flex-shrink-0 text-slate-500">{ts}</span>
                <span className={`flex-shrink-0 ${LEVEL_CLASS[ln.level]}`}>
                  {ln.level.padEnd(5, " ")}
                </span>
                <span className="break-all text-slate-300">{ln.message}</span>
              </div>
            );
          })}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── main page ────────────────────────────────────────────────────────────

export default function CommandCenter() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const { data, isLoading, error } = useSWR<IncidentView>(
    id ? `/incidents/${id}` : null,
    () => api.getIncident(id!),
    { refreshInterval: 4000 }
  );

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-400">
        Loading incident…
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-slate-400">
        <XCircle size={28} className="text-red-400" />
        <p>Incident not found.</p>
        <Link href="/incidents" className="btn-secondary">
          <ArrowLeft size={13} /> Back to incidents
        </Link>
      </div>
    );
  }

  const sevColor = SEV_BG[data.severity || "P4"];
  const statusColor = STATUS_BG[data.status] || "bg-slate-50 text-slate-600 border-slate-200";

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex flex-shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-8 py-5 section-desc">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href="/incidents"
            className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-700 shadow-sm"
          >
            <ArrowLeft size={18} />
          </Link>
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-rose-50 border border-rose-100 shadow-sm">
            <AlertTriangle size={18} className="text-rose-600" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="font-mono text-[18px] font-extrabold text-slate-900">{data.id}</h1>
              <span className={`badge border ${sevColor}`}>{data.severity || "—"}</span>
              <span className={`badge border ${statusColor}`}>
                {data.status.replace("_", " ")}
              </span>
            </div>
            <p className="truncate text-[12.5px] text-slate-500 font-sans mt-0.5">
              <span className="font-mono text-slate-700 font-bold">{data.service}</span> · {data.initial_signal}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {data.jira_ticket_key && (
            <div className="flex items-center gap-1.5">
              {data.jira_ticket_url ? (
                <a
                  href={data.jira_ticket_url}
                  target="_blank"
                  rel="noreferrer"
                  className="badge border border-brand-300 bg-brand-50 text-brand-700 hover:bg-brand-100 shadow-sm"
                >
                  <ExternalLink size={12} className="mr-1" />
                  <span className="font-mono font-bold">{data.jira_ticket_key}</span>
                </a>
              ) : (
                <span className="badge border border-brand-300 bg-brand-50 text-brand-700 shadow-sm">
                  <span className="font-mono font-bold">{data.jira_ticket_key}</span>
                </span>
              )}
              <JiraStatusBadge
                status={data.jira_ticket_status}
                updatedAt={data.jira_ticket_status_updated_at}
              />
            </div>
          )}
          {data.proposed_action?.requires_hil && (
            <Link
              href={`/incidents/${data.id}#approve`}
              className="badge border border-amber-300 bg-amber-100 text-amber-800 font-sans shadow-sm"
            >
              <ChevronRight size={12} className="mr-1" /> HIL approval pending
            </Link>
          )}
          <span className="text-[11px] font-medium text-slate-400 font-sans bg-slate-50 px-2 py-1 rounded-full border border-slate-200">
            <Clock size={12} className="mr-1 inline" /> auto-refresh 4s
          </span>
        </div>
      </div>

      {/* Body */}
      <div className="scrollbar-thin flex-1 space-y-4 overflow-y-auto p-6">
        <WorkflowTimeline status={data.status} />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_minmax(0,420px)]">
          <div className="h-[640px]">
            <AgentCommentary incidentId={data.id} />
          </div>
          <div className="space-y-4">
            <InsightsPanel service={data.service} />
            <GrafanaEmbed service={data.service} />
            <RawLogs service={data.service} />
          </div>
        </div>

        {/* RCA hypotheses summary */}
        {data.rca_hypotheses.length > 0 && (
          <div className="card p-5">
            <div className="mb-3 flex items-center gap-2">
              <FileText size={14} className="text-brand-600" />
              <h3 className="text-sm font-semibold text-slate-900">RCA Hypotheses</h3>
            </div>
            <div className="space-y-3">
              {data.rca_hypotheses.map((h, i) => (
                <div
                  key={i}
                  className="rounded-lg border border-slate-200 bg-slate-50 p-3"
                >
                  <div className="mb-1.5 flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-400">#{i + 1}</span>
                    <span className="badge border border-brand-200 bg-brand-50 text-brand-700">
                      {h.confidence_label} · {(h.confidence * 100).toFixed(0)}%
                    </span>
                    {h.referenced_runbook_ids.length > 0 && (
                      <span className="text-xs text-slate-500">
                        runbooks: {h.referenced_runbook_ids.join(", ")}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-slate-800">{h.description}</p>
                  {h.supporting_evidence.length > 0 && (
                    <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-slate-600">
                      {h.supporting_evidence.map((e, j) => (
                        <li key={j}>{e}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <PostmortemPanel incidentId={data.id} />
      </div>
    </div>
  );
}

function PostmortemPanel({ incidentId }: { incidentId: string }) {
  const { data, error } = useSWR<PostmortemView>(
    incidentId ? `/postmortems/by-incident/${incidentId}` : null,
    () => api.getPostmortemForIncident(incidentId),
    { refreshInterval: 30000, shouldRetryOnError: false },
  );
  if (error || !data) return null;
  return (
    <div className="card p-5">
      <div className="mb-3 flex items-center gap-2">
        <ScrollText size={14} className="text-indigo-600" />
        <h3 className="text-sm font-semibold text-slate-900">Postmortem</h3>
        <span className="font-mono text-[11px] text-slate-400">{data.id}</span>
        {data.is_published ? (
          <span className="badge-success">
            <CheckCircle2 size={10} /> published
          </span>
        ) : (
          <span className="badge-warn">
            <Sparkles size={10} /> draft
          </span>
        )}
      </div>
      <div className="text-[14px] font-semibold text-slate-900">{data.title}</div>
      <PMSection label="Summary" body={data.summary} />
      <PMSection label="Root cause" body={data.root_cause} />
      <PMSection label="Impact" body={data.impact} />
      <PMSection label="Lessons learned" body={data.lessons_learned} />
      {data.timeline.length > 0 && (
        <div className="mt-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Timeline
          </div>
          <ol className="mt-2 border-l border-slate-200 pl-4">
            {data.timeline.map((t, i) => (
              <li key={i} className="relative mb-2 text-[12.5px]">
                <span className="absolute -left-[19px] top-1.5 h-2 w-2 rounded-full bg-indigo-400" />
                <span className="font-mono mr-2 text-[10.5px] text-slate-500">
                  {new Date(t.at).toLocaleTimeString()}
                </span>
                <span className="text-slate-700">{t.event}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
      {data.corrective_actions.length > 0 && (
        <div className="mt-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Corrective actions ({data.corrective_actions.length})
          </div>
          <ul className="mt-2 space-y-2">
            {data.corrective_actions.map((a, i) => (
              <li
                key={i}
                className="flex items-start justify-between gap-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-[12.5px]"
              >
                <div className="min-w-0">
                  <div className="font-semibold text-slate-800">{a.description}</div>
                  <div className="mt-0.5 text-[11px] text-slate-500">
                    owner: <span className="font-mono">{a.owner}</span>
                    {a.due_date && ` · due ${new Date(a.due_date).toLocaleDateString()}`}
                  </div>
                </div>
                {a.jira_ticket && (
                  <a
                    href={a.jira_ticket}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex flex-shrink-0 items-center gap-1 rounded-md bg-white px-2 py-1 text-[11px] font-semibold text-indigo-700 ring-1 ring-indigo-200 hover:bg-indigo-50"
                  >
                    {a.jira_ticket}
                    <ExternalLink size={10} />
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function PMSection({ label, body }: { label: string; body: string }) {
  if (!body) return null;
  return (
    <div className="mt-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <p className="mt-1 whitespace-pre-wrap text-[13px] leading-relaxed text-slate-700">
        {body}
      </p>
    </div>
  );
}
