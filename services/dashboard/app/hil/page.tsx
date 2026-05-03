"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
  AlertOctagon,
  CheckCircle2,
  ChevronDown,
  RefreshCw,
  Shield,
  XCircle,
} from "lucide-react";
import { api, type OpenApprovalView, type IncidentView } from "@/lib/api";
import { PageShell } from "@/components/page-shell";
import { SeverityBadge } from "@/components/severity-badge";

const STATE_META: Record<string, { label: string; cls: string }> = {
  notified_primary:        { label: "Primary on-call",     cls: "bg-amber-50 text-amber-700 border-amber-200" },
  notified_secondary:      { label: "Secondary on-call",   cls: "bg-orange-50 text-orange-700 border-orange-200" },
  escalated_to_commander:  { label: "Incident commander",  cls: "bg-rose-50 text-rose-700 border-rose-200" },
};

function relTime(iso: string) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function HILQueuePage() {
  const { data, error, isLoading, mutate, isValidating } = useSWR<OpenApprovalView[]>(
    "/approvals",
    api.listOpenApprovals,
    { refreshInterval: 5000 },
  );
  const { data: escalated, mutate: mutateEsc } = useSWR<IncidentView[]>(
    "/incidents?status=escalated",
    api.listEscalatedIncidents,
    { refreshInterval: 5000 },
  );

  return (
    <PageShell
      title="HIL Queue"
      sub="Pending human-in-the-loop approvals · auto-refreshing"
      right={
        <button
          onClick={() => mutate()}
          className="btn-ghost"
          disabled={isValidating}
        >
          <RefreshCw size={14} className={isValidating ? "animate-spin" : ""} />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      }
    >
      {/* Top KPI strip ----------------------------------------------- */}
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <KPI
          label="Pending now"
          value={data?.length ?? 0}
          icon={<AlertOctagon size={16} />}
          accent="from-amber-500 to-orange-500"
        />
        <KPI
          label="Primary tier"
          value={
            data?.filter((a) => a.state === "notified_primary").length ?? 0
          }
          icon={<Shield size={16} />}
          accent="from-brand-500 to-cyan-500"
        />
        <KPI
          label="Escalated"
          value={escalated?.length ?? 0}
          icon={<AlertOctagon size={16} />}
          accent="from-rose-500 to-pink-500"
        />
      </div>

      {(escalated?.length ?? 0) > 0 && (
        <div className="mb-5">
          <div className="mb-2 text-[12px] font-bold uppercase tracking-wide text-rose-700 font-sans">
            Escalated incidents — needs human resolve
          </div>
          <div className="space-y-2">
            {(escalated || []).map((i) => (
              <EscalatedRow key={i.id} inc={i} onResolved={() => { mutateEsc(); mutate(); }} />
            ))}
          </div>
        </div>
      )}

      {isLoading && <div className="text-[12px] text-slate-500 font-sans">Loading…</div>}
      {error && (
        <div className="text-[12px] text-rose-600 font-sans">Failed to load approvals.</div>
      )}

      {!isLoading && (data?.length ?? 0) === 0 && (
        <div className="card flex flex-col items-center justify-center px-5 py-16 text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50">
            <CheckCircle2 size={20} className="text-emerald-500" />
          </div>
          <div className="text-[13px] font-bold text-slate-700 font-sans">
            All clear — no pending approvals
          </div>
          <div className="mt-1 text-[11px] text-slate-500 font-sans">
            New approval requests show up here in real time.
          </div>
        </div>
      )}

      <div className="space-y-3">
        {(data || []).map((a) => (
          <ApprovalCard key={a.incident_id} a={a} mutate={mutate} />
        ))}
      </div>
    </PageShell>
  );
}

function KPI({
  label,
  value,
  icon,
  accent,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  accent: string;
}) {
  return (
    <div className="card flex items-center justify-between px-4 py-3">
      <div>
        <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500 font-sans">{label}</div>
        <div className="mt-1 text-[24px] font-extrabold tracking-tight text-slate-900 font-sans">
          {value}
        </div>
      </div>
      <span
        className={`flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br text-white shadow-sm ${accent}`}
      >
        {icon}
      </span>
    </div>
  );
}

function EscalatedRow({
  inc,
  onResolved,
}: {
  inc: IncidentView;
  onResolved: () => void;
}) {
  const [busy, setBusy] = useState(false);
  async function handle() {
    if (!confirm(`Force-resolve ${inc.id} and restore ${inc.service} to baseline?`)) return;
    setBusy(true);
    try {
      const r = await api.forceResolveIncident(inc.id);
      alert(`Resolved. ${r.deployment_restore}`);
      onResolved();
    } catch (e) {
      console.error(e);
      alert("Force-resolve failed. Check console / agent logs.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="card flex items-center justify-between gap-3 px-4 py-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Link
            href={`/incidents/${inc.id}`}
            className="text-[12px] font-bold tracking-tight text-slate-900 hover:underline font-mono"
          >
            {inc.id}
          </Link>
          <SeverityBadge severity={inc.severity} />
          <span className="rounded border border-rose-200 bg-rose-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-rose-700">
            escalated
          </span>
        </div>
        <div className="mt-1 truncate text-[12px] text-slate-600 font-sans">
          <span className="font-mono text-[11px]">{inc.service}</span> ·{" "}
          {inc.initial_signal}
        </div>
      </div>
      <button
        onClick={handle}
        disabled={busy}
        className="shrink-0 rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-[12px] font-bold text-rose-700 hover:bg-rose-100 disabled:opacity-60 font-sans"
      >
        {busy ? "Resolving…" : "Force resolve + restore"}
      </button>
    </div>
  );
}

function ApprovalCard({
  a,
  mutate,
}: {
  a: OpenApprovalView;
  mutate: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const meta = STATE_META[a.state] || {
    label: a.state,
    cls: "bg-slate-100 text-slate-700 border-slate-200",
  };

  async function handle(decision: "approve" | "reject") {
    setSubmitting(true);
    try {
      await api.resolveApproval(a.approval_id, decision, "user");
      await mutate();
    } catch (err) {
      console.error(err);
      alert("Failed to submit approval.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card overflow-hidden">
      <div
        className="flex cursor-pointer items-start justify-between gap-4 border-b border-slate-100 bg-slate-50/50 px-5 py-3 transition-colors hover:bg-slate-50"
        onClick={() => setOpen((o) => !o)}
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Link
              href={`/incidents/${a.incident_id}`}
              className="text-mono text-[12.5px] font-bold text-brand-600 hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {a.incident_id}
            </Link>
            <SeverityBadge severity={a.incident_severity} />
            <span className={`rounded border px-1.5 py-0.5 text-[10px] font-bold font-sans ${meta.cls}`}>
              {meta.label}
            </span>
            <span className="text-[10px] text-slate-400 font-sans">
              {relTime(a.created_at)}
            </span>
          </div>
          <div className="mt-1 truncate text-[12px] font-bold text-slate-800 font-sans">
            {a.action_name}
          </div>
          <div className="mt-0.5 truncate text-[11.5px] text-slate-500 font-sans">
            {a.action_rationale}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              handle("approve");
            }}
            disabled={submitting}
            className="flex items-center gap-1 rounded bg-emerald-500 px-3 py-1.5 text-[11px] font-bold text-white shadow-sm transition-all hover:bg-emerald-600 disabled:opacity-50 font-sans"
          >
            <CheckCircle2 size={14} /> Approve
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              handle("reject");
            }}
            disabled={submitting}
            className="flex items-center gap-1 rounded border border-rose-200 bg-white px-3 py-1.5 text-[11px] font-bold text-rose-700 shadow-sm transition-all hover:bg-rose-50 disabled:opacity-50 font-sans"
          >
            <XCircle size={14} /> Reject
          </button>
          <ChevronDown
            size={16}
            className={`ml-2 text-slate-400 transition-transform ${
              open ? "rotate-180" : ""
            }`}
          />
        </div>
      </div>

      {open && (
        <div className="px-5 py-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <div className="mb-1 text-[11px] font-bold uppercase tracking-widest text-slate-500 font-sans">
                Action Details
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="text-mono text-[11px] font-bold text-slate-800">
                  {a.action_name}
                </div>
                <div className="mt-1 text-[11.5px] leading-relaxed text-slate-600 font-sans">
                  {a.action_rationale}
                </div>
                <div className="mt-2 flex items-center gap-2 text-[10px] font-bold font-sans">
                  <span className="text-slate-500">Blast radius:</span>
                  <span
                    className={`rounded px-1.5 py-0.5 ${
                      a.action_blast_radius === "high"
                        ? "bg-rose-100 text-rose-700"
                        : a.action_blast_radius === "medium"
                        ? "bg-amber-100 text-amber-700"
                        : "bg-emerald-100 text-emerald-700"
                    }`}
                  >
                    {a.action_blast_radius}
                  </span>
                </div>
              </div>
            </div>
            <div>
              <div className="mb-1 text-[11px] font-bold uppercase tracking-widest text-slate-500 font-sans">
                Incident Context
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-3">
                <div className="text-[12px] font-bold text-slate-900 font-sans">
                  {a.incident_service}
                </div>
                <div className="mt-1 text-[11.5px] text-slate-600 font-sans">
                  {a.incident_signal}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
