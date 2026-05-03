"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  Clock,
  Cpu,
  ExternalLink,
  Flame,
  HeartPulse,
  Loader2,
  MemoryStick,
  PowerOff,
  RotateCcw,
  Send,
  Sparkles,
  TestTube2,
  Zap,
} from "lucide-react";
import {
  api,
  type AppView,
  type EventView,
  type IncidentView,
} from "@/lib/api";

// ─── helpers ──────────────────────────────────────────────────────────────

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

// ─── push panel ───────────────────────────────────────────────────────────

const PRESETS: { label: string; signal: string; emoji: string }[] = [
  { label: "5xx errors", signal: "5xx error rate spike", emoji: "💥" },
  { label: "Latency", signal: "p99 latency above SLO", emoji: "🐢" },
  { label: "Conn pool", signal: "connection pool exhausted", emoji: "🔌" },
  { label: "OOM", signal: "OOMKilled crash loop", emoji: "🧠" },
  { label: "Deploy regression", signal: "deploy regression suspected", emoji: "📦" },
  { label: "Cert expiry", signal: "TLS certificate expiring soon", emoji: "🔒" },
  { label: "DB lock", signal: "database lock contention rising", emoji: "🔒" },
  { label: "Queue backup", signal: "kafka consumer lag growing", emoji: "📬" },
];

type PushPanelProps = {
  apps: AppView[];
  busy: boolean;
  onPush: (service: string, signal: string) => void;
};

function PushPanel({ apps, busy, onPush }: PushPanelProps) {
  const [service, setService] = useState("");
  const [signal, setSignal] = useState("connection pool exhausted");
  const [useFreshSvc, setUseFreshSvc] = useState(false);

  useEffect(() => {
    if (!service && apps.length > 0) setService(apps[0].name);
  }, [apps, service]);

  function submit() {
    const finalSvc = useFreshSvc ? `${service}-${Date.now().toString().slice(-6)}` : service;
    onPush(finalSvc, signal);
  }

  return (
    <div className="card p-5">
      <div className="mb-4 flex items-center gap-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-violet-100">
          <Flame size={16} className="text-violet-600" />
        </div>
        <div>
          <h3 className="text-sm font-bold text-slate-900">Inject incident</h3>
          <p className="mt-0.5 text-xs text-slate-500">
            Simulates an alert hitting <code className="font-mono">/signals</code>. Agent will
            run end-to-end: detect → triage → diagnose → fix.
          </p>
        </div>
      </div>

      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Target service</label>
          <div className="flex gap-2">
            <select
              className="input flex-1"
              value={service}
              onChange={(e) => setService(e.target.value)}
              disabled={busy}
            >
              {apps.length === 0 ? (
                <option value="">No apps registered — onboard one first</option>
              ) : (
                apps.map((a) => (
                  <option key={a.id} value={a.name}>
                    {a.name} ({a.tier})
                  </option>
                ))
              )}
            </select>
          </div>
          <label className="mt-2 flex items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={useFreshSvc}
              onChange={(e) => setUseFreshSvc(e.target.checked)}
              disabled={busy}
              className="h-3.5 w-3.5 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            <span>
              Append a random suffix (only if you want to test dedup — breaks logs/metrics/Jira
              lookup since the synthetic name has no Loki/Prometheus/DB match)
            </span>
          </label>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Initial signal</label>
          <input
            className="input"
            placeholder="e.g. 5xx errors trending"
            value={signal}
            onChange={(e) => setSignal(e.target.value)}
            disabled={busy}
          />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => setSignal(p.signal)}
                disabled={busy}
                className="flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600 transition-all hover:border-brand-300 hover:text-brand-600 disabled:opacity-50"
              >
                <span>{p.emoji}</span>
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={submit}
          disabled={busy || !service || !signal.trim()}
          className="btn-primary w-full justify-center"
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          {busy ? "Agent run in progress…" : "Push incident"}
        </button>
      </div>
    </div>
  );
}

// ─── result stream ────────────────────────────────────────────────────────

type ResultStreamProps = { incidentId: string | null; service: string | null };

function ResultStream({ incidentId, service }: ResultStreamProps) {
  // Poll latest incidents and find the one matching our pushed service (since /signals returns "pending").
  const { data: incidents } = useSWR<IncidentView[]>(
    service ? `chaos-incidents:${service}` : null,
    api.listIncidents,
    { refreshInterval: 3000 }
  );

  const matched =
    (incidents || []).find((i) => i.service === service) ||
    (incidentId && incidentId !== "pending"
      ? (incidents || []).find((i) => i.id === incidentId)
      : undefined);

  const realId = matched?.id;

  const { data: events } = useSWR<EventView[]>(
    realId ? `chaos-events:${realId}` : null,
    () => api.listEvents(realId, 60),
    { refreshInterval: 3000 }
  );

  const sorted = (events || []).slice().reverse();

  const toneClass: Record<string, string> = {
    info: "bg-white border-slate-200",
    ok: "bg-emerald-50 border-emerald-200",
    warn: "bg-amber-50 border-amber-200",
    danger: "bg-red-50 border-red-200",
  };

  const SEV_BG: Record<string, string> = {
    P1: "bg-red-50 text-red-700 border-red-200",
    P2: "bg-orange-50 text-orange-700 border-orange-200",
    P3: "bg-amber-50 text-amber-700 border-amber-200",
    P4: "bg-blue-50 text-blue-700 border-blue-200",
  };

  return (
    <div className="card flex h-full min-h-0 flex-col">
      <div className="flex flex-shrink-0 items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-brand">
            <Bot size={14} className="text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-900">Live agent run</div>
            <div className="text-xs text-slate-500">
              {service ? (
                <span>
                  service <span className="font-mono">{service}</span>
                  {realId && (
                    <>
                      {" · "}
                      <Link href={`/incidents/${realId}`} className="text-brand-600 hover:underline">
                        {realId}
                      </Link>
                    </>
                  )}
                </span>
              ) : (
                "Push an incident to see the agent work."
              )}
            </div>
          </div>
        </div>
        {realId && matched && (
          <div className="flex items-center gap-2">
            <span
              className={`badge border ${SEV_BG[matched.severity || "P4"]}`}
            >
              {matched.severity || "—"}
            </span>
            <span className="badge border border-slate-200 bg-slate-50 text-slate-600">
              {matched.status.replace("_", " ")}
            </span>
            <Link
              href={`/incidents/${realId}`}
              className="flex items-center gap-1 text-xs text-brand-600 hover:underline"
            >
              <ExternalLink size={11} />
              Command Center
            </Link>
          </div>
        )}
      </div>

      <div className="scrollbar-thin flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {!service && (
          <div className="flex h-full flex-col items-center justify-center text-center text-xs text-slate-400">
            <TestTube2 size={28} className="mb-3 opacity-30" />
            <p>Pick a target + signal on the left, then push.</p>
            <p className="mt-1 text-[11px] text-slate-300">
              Events will stream here as the agent works through detect → triage → diagnose →
              propose → execute → verify.
            </p>
          </div>
        )}
        {service && !realId && (
          <div className="flex h-full flex-col items-center justify-center text-center text-xs text-slate-500">
            <Loader2 size={20} className="mb-3 animate-spin text-brand-500" />
            <p>Waiting for the agent to ack the signal…</p>
            <p className="mt-1 text-[11px] text-slate-400">
              Usually <strong>5–10 seconds</strong>. The graph runs detection in the background.
            </p>
          </div>
        )}
        {realId && sorted.length === 0 && (
          <div className="flex h-full items-center justify-center text-xs text-slate-400">
            Incident captured but no events yet…
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

      {realId && (
        <div className="flex flex-shrink-0 items-center justify-between gap-2 border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
          <div className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
            polling every 3s
          </div>
          <Link
            href={`/incidents/${realId}`}
            className="flex items-center gap-1 font-medium text-brand-600 hover:underline"
          >
            Open Command Center <ArrowRight size={12} />
          </Link>
        </div>
      )}
    </div>
  );
}

// ─── workflow legend (helps demo viewers understand) ─────────────────────

function WorkflowLegend() {
  const stages = [
    { Icon: AlertCircle, label: "Detected", color: "text-rose-500", desc: "alert ingested" },
    { Icon: Sparkles, label: "Triaged", color: "text-sky-500", desc: "severity + blast radius" },
    { Icon: Bot, label: "Diagnosing", color: "text-violet-500", desc: "RCA from logs+metrics+kb" },
    { Icon: Clock, label: "Approval?", color: "text-amber-500", desc: "HIL gate if blast>low" },
    { Icon: Zap, label: "Executing", color: "text-violet-500", desc: "kubectl/script" },
    { Icon: CheckCircle2, label: "Verified", color: "text-emerald-500", desc: "metric back to baseline" },
  ];
  return (
    <div className="card p-4">
      <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
        What you'll see
      </div>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
        {stages.map((s) => (
          <div key={s.label} className="flex flex-col items-center text-center">
            <s.Icon size={18} className={`mb-1.5 ${s.color}`} />
            <div className="text-xs font-semibold text-slate-700">{s.label}</div>
            <div className="text-[10px] text-slate-400">{s.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── main page ────────────────────────────────────────────────────────────

export default function ChaosLab() {
  const { data: apps } = useSWR<AppView[]>("/api/apps", api.listApps);

  const [busy, setBusy] = useState(false);
  const [pushedSvc, setPushedSvc] = useState<string | null>(null);
  const [pushedId, setPushedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<{ at: number; service: string; signal: string }[]>([]);

  async function push(service: string, signal: string) {
    setBusy(true);
    setError(null);
    setPushedSvc(service);
    setPushedId(null);
    try {
      const r = await api.pushSignal({
        service,
        initial_signal: signal,
        signal_sources: ["manual:chaos-lab"],
      });
      setPushedId(r.incident_id);
      setHistory((h) => [{ at: Date.now(), service, signal }, ...h].slice(0, 8));
    } catch (e) {
      setError((e as Error).message);
      setPushedSvc(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex flex-shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-violet-100">
            <TestTube2 size={16} className="text-violet-600" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-900">Chaos Lab</h1>
            <p className="text-xs text-slate-500">
              Inject simulated incidents and watch the SRE Agent work end-to-end. For demos and
              testing only — not visible on the production cockpit.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <ResetIncidentsButton />
          <Link
            href="/"
            className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-all hover:bg-slate-50"
          >
            ← Back to Cockpit
          </Link>
        </div>
      </div>

      {/* Body */}
      <div className="scrollbar-thin flex-1 space-y-4 overflow-y-auto p-6">
        <WorkflowLegend />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[420px_1fr]">
          <div className="space-y-4">
            <RealK8sChaosPanel
              apps={apps || []}
              busy={busy}
              onChaos={(svc, signal, id) => {
                setPushedSvc(svc);
                setPushedId(id);
                setHistory((h) => [{ at: Date.now(), service: svc, signal }, ...h].slice(0, 8));
              }}
              onBusy={setBusy}
              onError={setError}
            />
            <PushPanel apps={apps || []} busy={busy} onPush={push} />
            {error && (
              <div className="card border-red-200 bg-red-50 p-3 text-xs text-red-700">
                {error}
              </div>
            )}
            <RecentPushes history={history} />
          </div>
          <div className="h-[640px]">
            <ResultStream incidentId={pushedId} service={pushedSvc} />
          </div>
        </div>
      </div>
    </div>
  );
}

function RealK8sChaosPanel({
  apps,
  busy,
  onChaos,
  onBusy,
  onError,
}: {
  apps: AppView[];
  busy: boolean;
  onChaos: (svc: string, signal: string, incidentId: string) => void;
  onBusy: (b: boolean) => void;
  onError: (e: string | null) => void;
}) {
  const [service, setService] = useState("");
  useEffect(() => {
    if (!service && apps.length > 0) setService(apps[0].name);
  }, [apps, service]);

  async function trigger(
    kind: "oom" | "cpu" | "scale_zero" | "restore",
    label: string
  ) {
    if (!service) return;
    onBusy(true);
    onError(null);
    try {
      let r: { incident_id?: string; patched?: string; applied?: string[] } = {};
      let signal = label;
      if (kind === "oom") r = await api.k8sChaosOOM(service, "8Mi");
      else if (kind === "cpu") r = await api.k8sChaosCPU(service, "10m");
      else if (kind === "scale_zero") r = await api.k8sChaosScaleZero(service);
      else if (kind === "restore") {
        await api.k8sChaosRestore(service);
        signal = `${service} restored to healthy defaults`;
      }
      onChaos(service, `[REAL K8s] ${signal}`, r.incident_id || "pending");
    } catch (e) {
      onError((e as Error).message);
    } finally {
      onBusy(false);
    }
  }

  return (
    <div className="card border-2 border-red-200 p-5">
      <div className="mb-4 flex items-center gap-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-red-100">
          <HeartPulse size={16} className="text-red-600" />
        </div>
        <div>
          <h3 className="text-sm font-bold text-slate-900">
            Real cluster chaos <span className="ml-1 rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-red-700">live AKS</span>
          </h3>
          <p className="mt-0.5 text-xs text-slate-500">
            Patches the actual Kubernetes deployment. Pods crash for real, agent
            sees real evidence (restart_count, exit_code 137), proposes a real
            <code className="mx-1 font-mono">kubectl patch</code> fix. On approve, it
            executes against the live cluster.
          </p>
        </div>
      </div>

      <div className="space-y-3">
        <select
          className="input"
          value={service}
          onChange={(e) => setService(e.target.value)}
          disabled={busy}
        >
          {apps.map((a) => (
            <option key={a.id} value={a.name}>
              {a.name} ({a.tier} · {a.namespace})
            </option>
          ))}
        </select>

        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            disabled={busy || !service}
            onClick={() => trigger("oom", "OOMKill via 32Mi memory limit")}
            className="flex items-center justify-center gap-1.5 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
          >
            <MemoryStick size={13} />
            OOM (8Mi)
          </button>
          <button
            type="button"
            disabled={busy || !service}
            onClick={() => trigger("cpu", "CPU throttle via 10m limit")}
            className="flex items-center justify-center gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-700 hover:bg-amber-100 disabled:opacity-50"
          >
            <Cpu size={13} />
            CPU throttle
          </button>
          <button
            type="button"
            disabled={busy || !service}
            onClick={() => trigger("scale_zero", "scaled to 0 replicas")}
            className="flex items-center justify-center gap-1.5 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
          >
            <PowerOff size={13} />
            Scale to 0
          </button>
          <button
            type="button"
            disabled={busy || !service}
            onClick={() => trigger("restore", "restore healthy defaults")}
            className="flex items-center justify-center gap-1.5 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
          >
            <CheckCircle2 size={13} />
            Restore
          </button>
        </div>
      </div>
    </div>
  );
}

function ResetIncidentsButton() {
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<string | null>(null);
  async function reset() {
    if (busy) return;
    setBusy(true);
    setLast(null);
    try {
      const r = await api.resolveAllIncidents();
      setLast(`${r.incidents_resolved} resolved`);
    } catch (e) {
      setLast(`err: ${(e as Error).message.slice(0, 40)}`);
    } finally {
      setBusy(false);
      setTimeout(() => setLast(null), 3500);
    }
  }
  return (
    <button
      onClick={reset}
      disabled={busy}
      title="Force-resolves every active incident so dedup doesn't block your next chaos push"
      className="flex items-center gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-700 transition-all hover:bg-amber-100 disabled:opacity-50"
    >
      {busy ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />}
      {last || "Reset incidents"}
    </button>
  );
}

function RecentPushes({ history }: { history: { at: number; service: string; signal: string }[] }) {
  if (history.length === 0) return null;
  return (
    <div className="card p-4">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Recent injections (this session)
      </div>
      <ul className="space-y-1.5 text-xs">
        {history.map((h, i) => (
          <li key={i} className="flex items-start gap-2 text-slate-600">
            <span className="text-slate-400">{new Date(h.at).toLocaleTimeString()}</span>
            <span className="font-mono text-slate-800">{h.service}</span>
            <span className="truncate text-slate-500">— {h.signal}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
