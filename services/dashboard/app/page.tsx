"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowUpRight,
  Bot,
  Boxes,
  CheckCircle2,
  Cpu,
  RefreshCw,
  Sparkles,
  TestTube2,
  Server,
  Database,
  CreditCard,
  Send
} from "lucide-react";
import {
  api,
  type AppView,
  type EventView,
  type IncidentView,
  type InsightSummary,
  type SLATracker,
  type CostBreakdown,
  type PeopleAggregate,
  type OpenApprovalView,
} from "@/lib/api";
import { PageShell } from "@/components/page-shell";
import { SeverityBadge } from "@/components/severity-badge";
import {
  ACTIVE_STATUSES,
  IncidentStatusBadge,
} from "@/components/incident-status";

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

function eventHeadline(e: EventView): string {
  const p = e.payload as Record<string, unknown>;
  switch (e.event_type) {
    case "IncidentDetected": {
      const svc = (p.service as { value?: string })?.value || "?";
      return `🚨 Detected on ${svc} — ${String(p.initial_signal || "")}`;
    }
    case "IncidentTriaged":
      return `⚖️ Triaged ${String(p.severity || "")} — ${String((p.rationale as string) || "").slice(0, 120)}`;
    case "EvidenceGathered":
      return `🔬 Gathered evidence: ${p.metric_snapshot_count} metric snapshots, ${p.log_line_count} log lines`;
    case "RCAGenerated": {
      const top = (p.hypotheses as { description?: string; confidence?: { value?: number } }[])?.[0];
      const conf = top?.confidence?.value ? ` (${Math.round(top.confidence.value * 100)}% conf)` : "";
      return `🧠 RCA${conf}: ${String(top?.description || "").slice(0, 140)}`;
    }
    case "ActionProposed":
      return `🔧 Proposed ${String(p.action_name)} (HIL: ${p.requires_hil ? "yes" : "no"}, blast: ${(p.blast_radius as { level?: string })?.level || "?"})`;
    case "ApprovalRequested":
      return `✋ Awaiting human approval`;
    case "ApprovalResolved":
      return `✅ Approval resolved: ${String(p.decision || "")} by ${e.caused_by}`;
    case "ApprovalGranted":
      return `✅ Approval granted by ${e.caused_by}`;
    case "ApprovalRejected":
      return `❌ Approval rejected`;
    case "FixExecuted":
      return `⚡ Executed fix`;
    case "ResolutionVerified":
      return `🎯 Verified resolution`;
    case "IncidentResolved":
      return `✓ Incident resolved`;
    case "IncidentEscalated":
      return `🚨 Escalated to commander`;
    case "PostmortemGenerated":
      return `📝 Postmortem drafted`;
    default:
      return e.event_type;
  }
}

// ────────────────────────────────────────────────────────────────────────────
//  Brand hero strip
// ────────────────────────────────────────────────────────────────────────────
function HeroStrip({
  active,
  incidents,
  lastEventAt,
}: {
  active: number;
  incidents: IncidentView[];
  lastEventAt: string | null;
}) {
  const resolved = incidents.filter(
    (i) => i.status.toLowerCase() === "resolved" && i.resolved_at,
  );
  const mttrMin =
    resolved.length === 0
      ? null
      : resolved.reduce(
          (s, i) =>
            s +
            (new Date(i.resolved_at!).getTime() -
              new Date(i.detected_at).getTime()) /
              60000,
          0,
        ) / resolved.length;
  const successRate =
    incidents.length === 0
      ? null
      : (resolved.length / incidents.length) * 100;

  function fmtMin(m: number | null) {
    if (m === null) return "—";
    if (m < 1) return `${Math.round(m * 60)}s`;
    if (m < 60) return `${m.toFixed(1)}m`;
    return `${Math.floor(m / 60)}h ${Math.round(m % 60)}m`;
  }

  function syncLabel(iso: string | null) {
    if (!iso) return "no agent activity yet";
    const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
    if (s < 60) return `last event ${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `last event ${m}m ago`;
    return `last event ${Math.floor(m / 60)}h ago`;
  }

  return (
    <div
      className="mb-5 grid gap-4 rounded-2xl px-6 py-5 text-slate-900 lg:grid-cols-[minmax(0,1fr),repeat(4,minmax(0,auto))] lg:items-center border border-brand-200"
      style={{
        background: "var(--gradient-banner)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-white shadow-sm border border-brand-100 text-brand-600">
          <Sparkles size={20} />
        </div>
        <div>
          <div className="text-[15px] font-bold leading-tight font-sans text-slate-900">
            SRE Agent · Continuous monitoring across App & Agent Metrics
          </div>
          <div className="mt-1 text-[11px] text-slate-500 font-sans">
            Prometheus · Datadog · CloudWatch · APM · Synthetic · {syncLabel(lastEventAt)}
          </div>
        </div>
      </div>

      <KPI label="Active" value={String(active)} danger={active > 0} />
      <KPI
        label="Avg SLO"
        value="97.3%"
        success
      />
      <KPI label="MTTD" value="2.1m" />
      <KPI label="MTTR" value={fmtMin(mttrMin)} />
    </div>
  );
}

function KPI({ label, value, danger, success }: { label: string; value: string, danger?: boolean, success?: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center text-center min-w-[80px]">
      <div className={`text-[18px] font-extrabold leading-none font-sans ${danger ? 'text-rose-600' : success ? 'text-emerald-600' : 'text-brand-600'}`}>
        {value}
      </div>
      <div className="mt-1 text-[9px] font-bold uppercase tracking-[.08em] text-slate-500 font-sans">
        {label}
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
//  Tabs
// ────────────────────────────────────────────────────────────────────────────
type TabId = "app" | "infra" | "txn" | "agent";

function LayerTabs({ activeTab, onChange, appsCount }: { activeTab: TabId, onChange: (id: TabId) => void, appsCount: number }) {
  return (
    <div className="mb-4 flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-white p-1.5 shadow-sm">
      <TabButton
        id="app"
        active={activeTab === "app"}
        onClick={() => onChange("app")}
        icon={<Activity size={16} />}
        title="Application"
        sub="Services, APIs, SLOs, deploys"
        kpis={<><span>Svc <b className="text-slate-900">{appsCount}</b></span><span>SLO <b className="text-slate-900">97.3%</b></span></>}
        grad="linear-gradient(135deg, #5929d0, #9B8EDE)"
      />
      <TabButton
        id="agent"
        active={activeTab === "agent"}
        onClick={() => onChange("agent")}
        icon={<Bot size={16} />}
        title="Agent Metrics"
        sub="LLM, RCA, HIL, ingestion"
        kpis={<><span>Tokens <b className="text-slate-900">Live</b></span><span>Err <b className="text-slate-900">0.0%</b></span></>}
        grad="linear-gradient(135deg, #01CAB8, #5929d0)"
        badge="Lead only"
      />
    </div>
  );
}

function TabButton({ id, active, onClick, icon, title, sub, kpis, grad, badge }: any) {
  return (
    <button
      onClick={onClick}
      className={`flex flex-1 min-w-[200px] items-center gap-3 rounded-lg p-2.5 text-left transition-all ${
        active ? "bg-slate-50 ring-1 ring-slate-200 shadow-sm" : "hover:bg-slate-50"
      }`}
      style={active && id === 'agent' ? { background: 'linear-gradient(135deg, #CFFAFE, #E8E5FF)' } : active ? { background: 'linear-gradient(135deg, var(--primary-light), var(--cyan-light))' } : {}}
    >
      <div
        className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg text-white shadow-sm"
        style={{ background: grad }}
      >
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <div className={`text-[12.5px] font-bold leading-tight font-sans ${active ? 'text-brand-600' : 'text-slate-800'}`}>
          {title}
          {badge && <span className="ml-1.5 rounded bg-slate-800 px-1.5 py-0.5 text-[8px] font-bold text-white tracking-widest uppercase">{badge}</span>}
        </div>
        <div className="mt-0.5 text-[10px] text-slate-500 font-sans">{sub}</div>
      </div>
      <div className="hidden flex-col items-end gap-1 text-[10px] text-slate-500 xl:flex font-sans">
        {kpis}
      </div>
    </button>
  );
}

// ────────────────────────────────────────────────────────────────────────────
//  Application Tab
// ────────────────────────────────────────────────────────────────────────────
function ApplicationTab({ incidents, apps, slas }: { incidents: IncidentView[], apps: AppView[], slas: SLATracker[] }) {
  const active = incidents.filter((i) => ACTIVE_STATUSES.has(i.status.toLowerCase()));
  const p1s = active.filter(i => i.severity === 'P1').length;
  
  return (
    <div className="flex flex-col gap-4 animate-fade-in">
      {/* KPIs */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <AppKpi label="Active Incidents" val={String(active.length)} tgt={`${p1s} P1 · ${active.length - p1s} other`} danger={active.length > 0} />
        <AppKpi label="Apps Monitored" val={String(apps.length)} tgt="All tiers" success />
        <AppKpi label="SLO Compliance" val="97.3%" tgt="Target ≥ 95% · on track" primary />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr,320px]">
        <div className="flex flex-col gap-4">
          <div className="grid gap-4 md:grid-cols-2">
            <ActiveIncidentsCard incidents={incidents} />
            <ServiceHealthCard apps={apps} incidents={incidents} />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <DeployHealthCard apps={apps} />
            <InfrastructureSummaryCard />
          </div>
        </div>
        <LiveCommentaryAside />
      </div>
    </div>
  );
}

function InfrastructureSummaryCard() {
  return (
    <div className="card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-brand-50 text-brand-600"><Database size={12} /></div>
          <div className="text-[13px] font-bold text-slate-900 font-sans">Infrastructure & DBs</div>
        </div>
      </div>
      <div className="space-y-3">
        <div>
          <div className="flex justify-between text-[11.5px] font-bold mb-1 font-sans">
            <span className="text-slate-900">PostgreSQL (orders-db)</span>
            <span className="text-amber-600">84% Conns</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
            <div className="h-full bg-amber-500" style={{ width: '84%' }} />
          </div>
          <div className="mt-1 flex justify-between text-[9px] text-slate-500 font-sans">
            <span>170/200 pool</span>
            <span>4.2k QPS</span>
          </div>
        </div>
        <div>
          <div className="flex justify-between text-[11.5px] font-bold mb-1 font-sans">
            <span className="text-slate-900">Redis Cache</span>
            <span className="text-emerald-600">48% Mem</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
            <div className="h-full bg-emerald-500" style={{ width: '48%' }} />
          </div>
          <div className="mt-1 flex justify-between text-[9px] text-slate-500 font-sans">
            <span>98.4% Hit Rate</span>
            <span>9.1k Ops/s</span>
          </div>
        </div>
        <div>
          <div className="flex justify-between text-[11.5px] font-bold mb-1 font-sans">
            <span className="text-slate-900">Kafka (events)</span>
            <span className="text-emerald-600">Healthy</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
            <div className="h-full bg-emerald-500" style={{ width: '15%' }} />
          </div>
          <div className="mt-1 flex justify-between text-[9px] text-slate-500 font-sans">
            <span>0 Lag</span>
            <span>3/3 Brokers</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function AppKpi({ label, val, tgt, danger, success, primary }: any) {
  let color = "text-slate-900";
  let border = "border-slate-200";
  if (danger) { color = "text-rose-600"; border = "border-rose-500"; }
  if (success) { color = "text-emerald-600"; border = "border-emerald-500"; }
  if (primary) { color = "text-brand-600"; border = "border-brand-500"; }

  return (
    <div className={`relative overflow-hidden rounded-xl border bg-white p-3.5 shadow-sm ${border} border-t-2`}>
      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 font-sans">
        {label}
      </div>
      <div className={`mt-1 text-[24px] font-extrabold leading-none font-sans ${color}`}>
        {val}
      </div>
      <div className="mt-2 text-[10px] text-slate-500 font-sans">{tgt}</div>
    </div>
  );
}

function ActiveIncidentsCard({ incidents }: { incidents: IncidentView[] }) {
  const active = incidents
    .filter((i) => ACTIVE_STATUSES.has(i.status.toLowerCase()))
    .slice(0, 4);

  return (
    <div className="card flex h-full min-h-0 flex-col">
      <div className="flex flex-shrink-0 items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-brand-50 text-brand-600">
            <AlertTriangle size={12} />
          </div>
          <div className="text-[13px] font-bold text-slate-900 font-sans">Active Incidents</div>
        </div>
        <Link href="/incidents" className="text-[11px] font-semibold text-brand-600 hover:underline font-sans">All →</Link>
      </div>
      <div className="scrollbar-thin flex-1 space-y-2 overflow-y-auto p-3">
        {active.length === 0 && (
          <div className="flex h-32 flex-col items-center justify-center text-center text-[12px] text-slate-400 font-sans">
            <CheckCircle2 size={24} className="mb-2 text-emerald-400 opacity-60" />
            All clear — no active incidents.
          </div>
        )}
        {active.map((i) => (
          <Link key={i.id} href={`/incidents/${i.id}`} className={`inc-card ${i.severity?.toLowerCase() || 'p3'}`}>
            <SeverityBadge severity={i.severity} />
            <div className="min-w-0">
              <div className="truncate text-[12px] font-bold text-slate-900 font-sans">{i.id} · {i.service}</div>
              <div className="mt-0.5 truncate text-[10px] text-slate-500 font-sans">{i.initial_signal}</div>
            </div>
            {i.proposed_action?.requires_hil ? (
              <span className="rounded bg-emerald-500 px-2 py-1 text-[9px] font-bold text-white shadow-sm font-sans">Approve</span>
            ) : (
              <span className="rounded border border-brand-200 bg-brand-50 px-2 py-1 text-[9px] font-bold text-brand-700 font-sans">Review</span>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}

function ServiceHealthCard({ apps, incidents }: { apps: AppView[], incidents: IncidentView[] }) {
  const activeIncidents = incidents.filter(i => ACTIVE_STATUSES.has(i.status.toLowerCase()));
  
  return (
    <div className="card flex h-full min-h-0 flex-col">
      <div className="flex flex-shrink-0 items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-brand-50 text-brand-600">
            <Activity size={12} />
          </div>
          <div className="text-[13px] font-bold text-slate-900 font-sans">Service Health</div>
        </div>
        <span className="text-[10px] text-slate-500 font-sans">{apps.length} svc · auto-refresh</span>
      </div>
      <div className="scrollbar-thin grid grid-cols-2 gap-2 overflow-y-auto p-3">
        {apps.length === 0 && (
          <div className="col-span-2 text-center text-[12px] text-slate-400 py-4">No services monitored.</div>
        )}
        {apps.map(app => {
          const appIncidents = activeIncidents.filter(i => i.service === app.name);
          const hasP1 = appIncidents.some(i => i.severity === 'P1');
          const hasAny = appIncidents.length > 0;
          
          let statusClass = "healthy";
          let dotClass = "dot-success";
          let statusText = "Healthy";
          let textColor = "text-emerald-600";
          let subText = "99.9%";
          
          if (hasP1) {
            statusClass = "error";
            dotClass = "dot-error";
            statusText = "P1 Active";
            textColor = "text-rose-600";
            subText = appIncidents.find(i => i.severity === 'P1')?.id || "Degraded";
          } else if (hasAny) {
            statusClass = "warning";
            dotClass = "dot-warning";
            statusText = "Degraded";
            textColor = "text-amber-600";
            subText = appIncidents[0].id;
          } else if (!app.enabled) {
            statusClass = "neutral";
            dotClass = "dot-neutral";
            statusText = "Disabled";
            textColor = "text-slate-500";
            subText = "Not monitored";
          }

          return (
            <div key={app.id} className={`svc-card ${statusClass}`}>
              <div className="flex justify-between">
                <span className="text-[11px] font-bold text-slate-900 font-sans truncate pr-2">{app.name}</span>
                <span className="rounded bg-slate-100 px-1 py-0.5 text-[8px] font-bold text-slate-500">{app.tier}</span>
              </div>
              <div className={`flex items-center gap-1.5 text-[10px] font-bold ${textColor} font-sans`}>
                <span className={`dot ${dotClass}`} /> {statusText}
              </div>
              <div className="text-[9px] text-slate-500 font-sans truncate">{subText}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SloComplianceCard({ slas }: { slas: SLATracker[] }) {
  return (
    <div className="card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-brand-50 text-brand-600"><AlertCircle size={12} /></div>
          <div className="text-[13px] font-bold text-slate-900 font-sans">Active SLAs</div>
        </div>
        <Link href="/incidents" className="text-[11px] font-semibold text-brand-600 hover:underline cursor-pointer font-sans">All →</Link>
      </div>
      <div className="space-y-3">
        {slas.length === 0 && (
          <div className="text-center text-[12px] text-slate-400 py-4">No active SLAs tracked.</div>
        )}
        {slas.map(sla => {
          let color = "emerald";
          if (sla.status === "breached") color = "rose";
          else if (sla.elapsed_pct > 75) color = "amber";
          
          return (
            <div key={sla.id}>
              <div className="flex justify-between text-[11.5px] font-bold mb-1 font-sans">
                <span className="text-slate-900">{sla.incident_id} · {sla.sla_type}</span>
                <span className={`text-${color}-600`}>{Math.round(sla.elapsed_pct)}% elapsed</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                <div className={`h-full bg-${color}-500`} style={{ width: `${Math.min(100, sla.elapsed_pct)}%` }} />
              </div>
              <div className="mt-1 flex justify-between text-[9px] text-slate-500 font-sans">
                <span>Severity {sla.severity}</span>
                <span className={`font-bold text-${color}-600`}>{sla.status}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DeployHealthCard({ apps }: { apps: AppView[] }) {
  // We don't have real deployment data, so we'll show the apps and their tier/namespace
  return (
    <div className="card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-brand-50 text-brand-600"><TestTube2 size={12} /></div>
          <div className="text-[13px] font-bold text-slate-900 font-sans">App Environments</div>
        </div>
        <Link href="/apps" className="text-[11px] font-semibold text-brand-600 hover:underline cursor-pointer font-sans">All →</Link>
      </div>
      <div className="space-y-2 max-h-[160px] overflow-y-auto scrollbar-thin">
        {apps.length === 0 && (
          <div className="text-center text-[12px] text-slate-400 py-4">No apps registered.</div>
        )}
        {apps.map(app => (
          <div key={app.id} className="flex items-center justify-between rounded-lg border border-slate-200 p-2">
            <div className="min-w-0 pr-2">
              <div className="text-[11px] font-bold text-slate-900 font-sans truncate">{app.name}</div>
              <div className="text-[9.5px] text-slate-500 font-sans truncate">ns: {app.namespace}</div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold font-sans ${app.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                {app.enabled ? 'ACTIVE' : 'DISABLED'}
              </span>
              <Link href={`/apps`} className="rounded border border-brand-200 bg-brand-50 px-2 py-1 text-[9px] font-bold text-brand-700 font-sans">Details</Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LiveCommentaryAside() {
  const { data: events } = useSWR<EventView[]>(
    "/api/events?global",
    () => api.listEvents(undefined, 30),
    { refreshInterval: 4000 },
  );
  const { data: approvals } = useSWR<OpenApprovalView[]>(
    "/approvals",
    api.listOpenApprovals,
    { refreshInterval: 10000 },
  );
  const { data: people } = useSWR<PeopleAggregate[]>(
    "/api/people/aggregates",
    api.peopleAggregates,
    { refreshInterval: 60000 },
  );

  const list = events || [];
  const hilCount = approvals?.length || 0;
  
  const agentResolutions = people?.reduce((acc, p) => acc + p.agent_resolutions, 0) || 0;
  const totalResolutions = people?.reduce((acc, p) => acc + p.total_resolutions, 0) || 0;
  const autofixRate = totalResolutions > 0 ? Math.round((agentResolutions / totalResolutions) * 100) : 0;

  return (
    <div className="card flex flex-col overflow-hidden bg-gradient-to-b from-slate-50/50 to-white h-[540px]">
      <div className="flex flex-shrink-0 items-center justify-between border-b border-brand-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="text-[13px] font-bold text-slate-900 font-sans">📡 Live Commentary</div>
          <Link href="/audit" className="text-[10px] font-semibold text-brand-600 hover:underline font-sans">View All</Link>
        </div>
        <div className="flex items-center gap-1.5 rounded-full border border-emerald-200/50 bg-emerald-50 px-2 py-0.5 text-[9px] font-bold text-emerald-600 font-sans">
          <span className="dot dot-success" /> LIVE
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 border-b border-slate-200 p-2.5">
        <div className="rounded-lg border border-brand-200 bg-white p-2 text-center shadow-sm">
          <div className="text-[16px] font-extrabold text-brand-600 font-sans leading-none">{hilCount}</div>
          <div className="mt-1 text-[9px] text-slate-500 font-sans">HIL queued</div>
        </div>
        <div className="rounded-lg border border-brand-200 bg-white p-2 text-center shadow-sm">
          <div className="text-[16px] font-extrabold text-brand-600 font-sans leading-none">{autofixRate}%</div>
          <div className="mt-1 text-[9px] text-slate-500 font-sans">Auto-fix rate</div>
        </div>
      </div>
      <div className="scrollbar-thin flex-1 space-y-3 overflow-y-auto p-3">
        {list.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center text-[11.5px] text-slate-400 font-sans">
            <Bot size={24} className="mb-2 opacity-30" />
            No agent activity yet.
          </div>
        )}
        {list.slice(0, 10).map((e) => (
          <div key={e.event_id} className="animate-slide-up rounded-lg bg-brand-50/30 p-2.5 border border-brand-100">
            <div className="flex items-center justify-between mb-1.5">
              <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[9px] font-bold text-brand-700 font-sans uppercase tracking-wider">Event</span>
              <span className="text-[9px] text-slate-400 font-sans">{timeAgo(e.occurred_at)}</span>
            </div>
            <div className="text-[11px] leading-snug text-slate-800 font-sans">
              {eventHeadline(e)}
            </div>
            <div className="mt-1.5 text-[10px] font-bold text-brand-600 hover:underline font-sans cursor-pointer">
              {e.incident_id}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
//  Infrastructure Tab (Mocked for visual demonstration)
// ────────────────────────────────────────────────────────────────────────────
function InfrastructureTab() {
  return (
    <div className="flex flex-col gap-4 animate-fade-in">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <AppKpi label="Avg CPU" val="62%" tgt="Peak 88% · node-w4" />
        <AppKpi label="Avg Memory" val="71%" tgt="2 hosts > 85%" danger />
        <AppKpi label="Network Egress" val="3.2 Gbps" tgt="Within budget" primary />
        <AppKpi label="DB Connections" val="84%" tgt="orders-db pool 170/200" danger />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card p-4">
          <div className="mb-3 flex items-center gap-2 text-[13px] font-bold text-slate-900 font-sans">
            <Server size={14} className="text-brand-600" /> Compute & Nodes
          </div>
          <div className="grid grid-cols-2 gap-2">
            <InfraTile name="node-w1" sub="16 vCPU · 64 GiB" val="48%" metric="CPU" ok />
            <InfraTile name="node-w4" sub="16 vCPU · 64 GiB" val="88%" metric="CPU" danger />
            <InfraTile name="node-w2" sub="16 vCPU · 64 GiB" val="71%" metric="CPU" warn />
            <InfraTile name="node-w3" sub="16 vCPU · 64 GiB" val="54%" metric="CPU" ok />
          </div>
        </div>
        <div className="card p-4">
          <div className="mb-3 flex items-center gap-2 text-[13px] font-bold text-slate-900 font-sans">
            <Database size={14} className="text-brand-600" /> Databases & Queues
          </div>
          <div className="space-y-2">
            <DbTile name="orders-db (PostgreSQL primary)" sub="pool near cap" danger stats={[{l:"Conns", v:"170/200", d:true}, {l:"QPS", v:"4.2k"}, {l:"Repl lag", v:"0.2s", ok:true}, {l:"p95 query", v:"86ms", w:true}]} />
            <DbTile name="inventory-db (PostgreSQL)" sub="healthy" ok stats={[{l:"Conns", v:"42/200"}, {l:"QPS", v:"1.8k"}, {l:"Repl lag", v:"0.1s", ok:true}, {l:"p95 query", v:"22ms"}]} />
            <DbTile name="redis-sessions (cluster)" sub="healthy" ok stats={[{l:"Hit rate", v:"98.4%", ok:true}, {l:"Mem", v:"48%"}, {l:"Evict/s", v:"12"}, {l:"Ops", v:"9.1k"}]} />
            <DbTile name="kafka · orders-events" sub="consumer lag" warn stats={[{l:"Lag", v:"8.4k", w:true}, {l:"Msg/s", v:"3.2k"}, {l:"Brokers", v:"3/3"}, {l:"Under-rep", v:"0"}]} />
          </div>
        </div>
      </div>
    </div>
  );
}

function InfraTile({ name, sub, val, metric, ok, warn, danger }: any) {
  let color = "bg-slate-500";
  let text = "text-slate-900";
  if (ok) { color = "bg-emerald-500"; text = "text-emerald-600"; }
  if (warn) { color = "bg-amber-500"; text = "text-amber-600"; }
  if (danger) { color = "bg-rose-500"; text = "text-rose-600"; }
  
  return (
    <div className="rounded-lg border border-slate-200 p-2.5 shadow-sm">
      <div className="text-[11px] font-bold text-slate-900 font-sans">{name}</div>
      <div className="text-[9.5px] text-slate-500 font-sans mb-2">{sub}</div>
      <div className="flex items-baseline justify-between mb-1">
        <span className={`text-[18px] font-extrabold font-sans ${text}`}>{val}</span>
        <span className="text-[9.5px] text-slate-500 font-sans">{metric}</span>
      </div>
      <div className="h-1 w-full rounded-full bg-slate-100 overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: val }} />
      </div>
    </div>
  );
}

function DbTile({ name, sub, stats, ok, warn, danger }: any) {
  let subColor = "text-slate-500";
  if (ok) subColor = "text-emerald-600";
  if (warn) subColor = "text-amber-600";
  if (danger) subColor = "text-rose-600";

  return (
    <div className="rounded-lg border border-slate-200 p-2.5 shadow-sm">
      <div className="flex justify-between mb-2">
        <div className="text-[11px] font-bold text-slate-900 font-sans">{name}</div>
        <div className={`text-[9.5px] font-bold font-sans ${subColor}`}>● {sub}</div>
      </div>
      <div className="grid grid-cols-4 gap-2">
        {stats.map((s: any, i: number) => (
          <div key={i}>
            <div className="text-[9.5px] text-slate-500 font-sans">{s.l}</div>
            <div className={`text-[13px] font-bold font-sans ${s.d ? 'text-rose-600' : s.ok ? 'text-emerald-600' : s.w ? 'text-amber-600' : 'text-slate-900'}`}>{s.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
//  Transactional Tab (Mocked for visual demonstration)
// ────────────────────────────────────────────────────────────────────────────
function TransactionalTab() {
  return (
    <div className="flex flex-col gap-4 animate-fade-in">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <AppKpi label="Txn Success Rate" val="98.6%" tgt="Target ≥ 99.5%" success />
        <AppKpi label="Throughput (TPS)" val="2,418" tgt="Peak today 3,104" primary />
        <AppKpi label="p95 Checkout" val="2.8s" tgt="Target ≤ 2.0s" danger />
        <AppKpi label="Failed Payments (1h)" val="342" tgt="$82K at risk" danger />
      </div>
      <div className="card p-4">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-[13px] font-bold text-slate-900 font-sans">
            <CreditCard size={14} className="text-brand-600" /> Checkout Journey · Step Health (last 1h)
          </div>
          <span className="text-[10px] text-slate-500 font-sans">4.2M users · 2.4k TPS</span>
        </div>
        <div className="grid grid-cols-5 gap-3">
          <TxnStep name="🏠 Browse" val="99.9%" sub="p95 420ms · 4.2M" ok />
          <TxnStep name="➕ Add to Cart" val="99.7%" sub="p95 680ms · 1.1M" ok />
          <TxnStep name="🔐 Checkout" val="97.2%" sub="p95 2.8s · 340K" warn />
          <TxnStep name="💳 Payment" val="92.1%" sub="p95 4.4s · 298K" danger />
          <TxnStep name="✅ Confirm" val="99.4%" sub="p95 820ms · 275K" ok />
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card p-4">
          <div className="mb-4 flex items-center gap-2 text-[13px] font-bold text-slate-900 font-sans">
            <Activity size={14} className="text-brand-600" /> Failure Funnel — last 1h
          </div>
          <div className="space-y-3">
            <FunnelRow lbl="Sessions" pct="100%" cnt="4.22M" w="100%" />
            <FunnelRow lbl="Add-to-cart" pct="26%" cnt="1.10M" w="26%" />
            <FunnelRow lbl="Checkout" pct="8%" cnt="340K" w="8%" />
            <FunnelRow lbl="Payment init" pct="7%" cnt="298K" w="7%" warn />
            <FunnelRow lbl="Success" pct="6.5%" cnt="275K" w="6.5%" />
            <FunnelRow lbl="Drop @ Payment" pct="" cnt="+23K" w="2%" danger />
          </div>
        </div>
        <div className="card p-4">
          <div className="mb-4 flex items-center gap-2 text-[13px] font-bold text-slate-900 font-sans">
            <Activity size={14} className="text-brand-600" /> Business SLIs · MTD
          </div>
          <div className="space-y-2">
            <BizSli name="Orders placed" val="1.82M" sub="vs March 1.71M · target 1.85M" chg="▲ 6.2%" ok />
            <BizSli name="GMV processed" val="$48.2M" sub="vs March $44.6M" chg="▲ 8.1%" ok primary />
            <BizSli name="Payment success rate" val="98.6%" sub="target 99.5% · $82K at risk today" chg="▼ 0.4%" warn />
            <BizSli name="Cart-to-order conversion" val="25.0%" sub="target 24% · on track" chg="▲ 1.2%" ok />
          </div>
        </div>
      </div>
    </div>
  );
}

function TxnStep({ name, val, sub, ok, warn, danger }: any) {
  let color = "text-slate-900";
  let border = "border-slate-200";
  let bg = "bg-white";
  if (ok) color = "text-emerald-600";
  if (warn) color = "text-amber-600";
  if (danger) { color = "text-rose-600"; border = "border-rose-500"; bg = "bg-rose-50/50"; }

  return (
    <div className={`rounded-lg border ${border} ${bg} p-3 shadow-sm`}>
      <div className="text-[11px] font-bold text-slate-900 font-sans">{name}</div>
      <div className={`mt-1 text-[20px] font-extrabold font-sans ${color}`}>{val}</div>
      <div className="mt-1 text-[9px] text-slate-500 font-sans">{sub}</div>
    </div>
  );
}

function FunnelRow({ lbl, pct, cnt, w, warn, danger }: any) {
  let bg = "bg-brand-500";
  if (warn) bg = "bg-amber-500";
  if (danger) bg = "bg-rose-500";

  return (
    <div className="grid grid-cols-[100px_1fr_60px] items-center gap-3">
      <div className={`text-[11px] font-bold font-sans ${danger ? 'text-rose-600' : 'text-slate-700'}`}>{lbl}</div>
      <div className="h-4 w-full rounded bg-slate-100 overflow-hidden relative">
        <div className={`h-full ${bg} flex items-center pl-2 text-[9px] font-bold text-white`} style={{ width: w }}>{pct}</div>
      </div>
      <div className={`text-right text-[11px] font-bold font-sans ${danger ? 'text-rose-600' : 'text-slate-900'}`}>{cnt}</div>
    </div>
  );
}

function BizSli({ name, val, sub, chg, ok, warn, primary }: any) {
  let chgColor = "text-slate-500";
  if (ok) chgColor = "text-emerald-600";
  if (warn) chgColor = "text-amber-600";

  return (
    <div className="rounded-lg border border-slate-200 p-3 shadow-sm flex justify-between items-center">
      <div>
        <div className="flex items-center gap-2">
          <div className="text-[11.5px] font-bold text-slate-900 font-sans">{name}</div>
          <div className={`text-[9.5px] font-bold font-sans ${chgColor}`}>{chg}</div>
        </div>
        <div className="text-[9.5px] text-slate-500 font-sans mt-0.5">{sub}</div>
      </div>
      <div className={`text-[16px] font-extrabold font-sans ${primary ? 'text-brand-600' : warn ? 'text-amber-600' : 'text-slate-900'}`}>
        {val}
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
//  Agent Tab (Mocked for visual demonstration)
// ────────────────────────────────────────────────────────────────────────────
function AgentTab() {
  const { data: cost } = useSWR<CostBreakdown>("/api/cost/llm-tokens", api.costBreakdown);
  const { data: people } = useSWR<PeopleAggregate[]>("/api/people/aggregates", api.peopleAggregates);

  const totalTokens = cost?.total_tokens || 0;
  const totalUsd = cost?.estimated_usd || 0;
  const agentResolutions = people?.reduce((acc, p) => acc + p.agent_resolutions, 0) || 0;
  const totalResolutions = people?.reduce((acc, p) => acc + p.total_resolutions, 0) || 0;
  const autofixRate = totalResolutions > 0 ? (agentResolutions / totalResolutions) * 100 : 0;

  return (
    <div className="flex flex-col gap-4 animate-fade-in">
      <div className="flex items-center gap-4 rounded-xl border border-brand-200 p-4 shadow-sm" style={{ background: 'linear-gradient(90deg, rgba(168, 85, 247, 0.05), rgba(1, 202, 184, 0.08))' }}>
        <div className="flex h-10 w-10 items-center justify-center rounded-lg text-white" style={{ background: 'linear-gradient(135deg, #01CAB8, #5929d0)' }}>
          <Bot size={20} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-bold text-slate-900 font-sans">Agent Health — LLM, RCA pipeline, HIL & data plane</div>
          <div className="text-[10.5px] text-slate-500 font-sans">Observability for the SRE Agent itself · scope: all products</div>
        </div>
        <div className="flex gap-6 text-right">
          <div><div className="text-[16px] font-extrabold text-emerald-600 font-sans">99.9%</div><div className="text-[9px] font-bold uppercase tracking-wider text-slate-500 font-sans">Agent uptime</div></div>
          <div><div className="text-[16px] font-extrabold text-slate-900 font-sans">{totalTokens.toLocaleString()}</div><div className="text-[9px] font-bold uppercase tracking-wider text-slate-500 font-sans">Tokens Used</div></div>
          <div><div className="text-[16px] font-extrabold text-emerald-600 font-sans">${totalUsd.toFixed(2)}</div><div className="text-[9px] font-bold uppercase tracking-wider text-slate-500 font-sans">LLM Cost</div></div>
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <AgentTile title="LLM Token Usage" val={totalTokens.toLocaleString()} unit="total tok" sub={`Cost: $${totalUsd.toFixed(2)}`} primary />
        <AgentTile title="Auto-fix Rate" val={`${autofixRate.toFixed(1)}%`} unit="of resolved" sub={`${agentResolutions} agent / ${totalResolutions} total`} success />
        <AgentTile title="LLM Error Rate" val="0.0%" unit="fail + timeout" sub="Target ≤ 2% · On track" success />
        <AgentTile title="RCA Accuracy Rate" val="N/A" unit="root cause correct" sub="Requires human feedback" warn />
      </div>
    </div>
  );
}

function AgentTile({ title, val, unit, sub, primary, success, warn }: any) {
  let color = "text-slate-900";
  let border = "border-slate-200";
  if (primary) { color = "text-brand-600"; border = "border-brand-400 border-t-2"; }
  if (success) { color = "text-emerald-600"; border = "border-emerald-400 border-t-2"; }
  if (warn) { color = "text-amber-600"; border = "border-amber-400 border-t-2"; }

  return (
    <div className={`card p-4 ${border}`}>
      <div className="text-[11.5px] font-bold text-slate-900 font-sans">{title}</div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className={`text-[22px] font-extrabold font-sans ${color}`}>{val}</span>
        <span className="text-[10px] font-bold text-slate-500 font-sans">{unit}</span>
      </div>
      <div className="mt-3 text-[10px] text-slate-500 font-sans">{sub}</div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
//  Page
// ────────────────────────────────────────────────────────────────────────────
export default function CockpitPage() {
  const [activeTab, setActiveTab] = useState<TabId>("app");
  
  const { data: incidents } = useSWR<IncidentView[]>(
    "/incidents",
    api.listIncidents,
    { refreshInterval: 5000 },
  );
  const { data: latestEvents } = useSWR<EventView[]>(
    "/api/events?global",
    () => api.listEvents(undefined, 1),
    { refreshInterval: 5000 },
  );
  const { data: apps } = useSWR<AppView[]>(
    "/api/apps",
    api.listApps,
    { refreshInterval: 10000 },
  );
  const { data: slas } = useSWR<SLATracker[]>(
    "/api/sla",
    api.listSLA,
    { refreshInterval: 10000 },
  );

  const active =
    (incidents || []).filter((i) =>
      ACTIVE_STATUSES.has(i.status.toLowerCase()),
    ).length;
  const latestEventAt = latestEvents && latestEvents[0] ? latestEvents[0].occurred_at : null;

  return (
    <PageShell
      title="Operations Overview"
      sub={`Live monitoring · ${apps?.length || 0} services · 1 project`}
      right={
        <Link
          href="/chaos"
          className="inline-flex items-center gap-1.5 rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-[11px] font-semibold text-violet-700 hover:bg-violet-100"
        >
          <TestTube2 size={12} />
          Chaos Lab
        </Link>
      }
    >
      <HeroStrip
        active={active}
        incidents={incidents || []}
        lastEventAt={latestEventAt}
      />

      <LayerTabs activeTab={activeTab} onChange={setActiveTab} appsCount={apps?.length || 0} />

      {activeTab === "app" && <ApplicationTab incidents={incidents || []} apps={apps || []} slas={slas || []} />}
      {activeTab === "infra" && <InfrastructureTab />}
      {activeTab === "txn" && <TransactionalTab />}
      {activeTab === "agent" && <AgentTab />}

    </PageShell>
  );
}
