"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
  ArrowUpRight,
  CheckCircle2,
  ClipboardList,
  ExternalLink,
  RefreshCw,
  Search,
  Sparkles,
  Target,
  TimerReset,
} from "lucide-react";
import { api, type PostmortemView } from "@/lib/api";
import { PageShell } from "@/components/page-shell";
import { SeverityBadge } from "@/components/severity-badge";
import { MTTRChart } from "@/components/dashboard-charts";

function fmtDate(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}
function durationMin(start?: string | null, end?: string | null) {
  if (!start || !end) return "—";
  const m = Math.round(
    (new Date(end).getTime() - new Date(start).getTime()) / 60000,
  );
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

export default function PostmortemsPage() {
  const { data, error, isLoading, mutate, isValidating } = useSWR<
    PostmortemView[]
  >("/postmortems", api.listPostmortems, { refreshInterval: 15000 });
  const [query, setQuery] = useState("");

  const postmortems = useMemo(
    () =>
      (data || []).slice().sort(
        (a, b) =>
          new Date(b.drafted_at).getTime() - new Date(a.drafted_at).getTime(),
      ),
    [data],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return postmortems;
    return postmortems.filter(
      (p) =>
        p.id.toLowerCase().includes(q) ||
        p.incident_id.toLowerCase().includes(q) ||
        (p.service || "").toLowerCase().includes(q) ||
        p.title.toLowerCase().includes(q) ||
        (p.initial_signal || "").toLowerCase().includes(q) ||
        p.root_cause.toLowerCase().includes(q),
    );
  }, [postmortems, query]);

  const publishedCount = postmortems.filter((p) => p.is_published).length;
  const totalActions = postmortems.reduce(
    (s, p) => s + p.corrective_actions.length,
    0,
  );

  return (
    <PageShell
      title="Postmortems"
      sub="Auto-generated postmortems for every resolved incident"
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
      {/* KPI row & Chart */}
      <div className="mb-4 grid gap-4 lg:grid-cols-[1fr,300px]">
        <div className="grid gap-3 md:grid-cols-1">
          <KPI
            label="Drafted"
            value={postmortems.length}
            Icon={ClipboardList}
            tone="brand"
          />
          <KPI
            label="Published"
            value={publishedCount}
            Icon={CheckCircle2}
            tone="emerald"
          />
          <KPI
            label="Follow-up Actions"
            value={totalActions}
            Icon={Target}
            tone="amber"
          />
        </div>
        <MTTRChart postmortems={data || []} />
      </div>

      {/* Controls */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search title, service, root cause…"
            className="input pl-9 sm:w-80"
          />
        </div>
      </div>

      {isLoading && <div className="text-[12px] text-slate-500 font-sans">Loading…</div>}
      {error && <div className="text-[12px] text-rose-600 font-sans">Failed to load.</div>}

      {!isLoading && !error && filtered.length === 0 && (
        <div className="card flex flex-col items-center justify-center px-5 py-16 text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
            <ClipboardList size={20} className="text-slate-400" />
          </div>
          <div className="text-[13px] font-bold text-slate-700 font-sans">
            No postmortems found
          </div>
          <div className="mt-1 text-[11px] text-slate-500 font-sans">
            The agent generates a postmortem automatically when an incident is
            resolved.
          </div>
        </div>
      )}

      {/* List */}
      {!isLoading && !error && filtered.length > 0 && (
        <div className="grid gap-4">
          {filtered.map((pm) => (
            <div key={pm.id} className="card overflow-hidden">
              {/* Header */}
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 bg-slate-50/50 px-5 py-3">
                <div className="flex items-center gap-3">
                  <Link
                    href={`/incidents/${pm.incident_id}`}
                    className="text-mono text-[12.5px] font-bold text-brand-600 hover:underline"
                  >
                    {pm.incident_id}
                  </Link>
                  {pm.severity && <SeverityBadge severity={pm.severity} />}
                  {pm.service && (
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-600 font-sans">
                      {pm.service}
                    </span>
                  )}
                  {pm.is_published ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-700 font-sans">
                      <CheckCircle2 size={10} /> Published
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700 font-sans">
                      <Sparkles size={10} /> Draft
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-[11px] font-bold text-slate-500 font-sans">
                  <span>
                    <TimerReset size={12} className="mr-1 inline" />
                    MTTR: {durationMin(pm.detected_at, pm.resolved_at)}
                  </span>
                  <span>{fmtDate(pm.drafted_at)}</span>
                </div>
              </div>

              {/* Body */}
              <div className="px-5 py-4">
                <h3 className="text-[14px] font-bold text-slate-900 font-sans">
                  {pm.title}
                </h3>
                {pm.initial_signal && (
                  <p className="mt-1 text-[12px] text-slate-500 font-sans">
                    <span className="font-bold text-slate-700">Trigger:</span>{" "}
                    {pm.initial_signal}
                  </p>
                )}

                <div className="mt-3 text-[12.5px] leading-relaxed text-slate-800 font-sans">
                  <span className="font-bold text-slate-900">Root Cause:</span>{" "}
                  {pm.root_cause}
                </div>
                <div className="mt-2 text-[12.5px] leading-relaxed text-slate-800 font-sans">
                  <span className="font-bold text-slate-900">Impact:</span>{" "}
                  {pm.impact}
                </div>

                {/* Actions */}
                {pm.corrective_actions.length > 0 && (
                  <div className="mt-4">
                    <div className="mb-2 text-[11px] font-bold uppercase tracking-widest text-slate-500 font-sans">
                      Follow-up Actions
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                      {pm.corrective_actions.map((act, i) => (
                        <div
                          key={i}
                          className="flex flex-col gap-1 rounded-lg border border-slate-200 bg-white p-2.5 shadow-sm"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="text-[11.5px] font-bold text-slate-800 font-sans">
                              {act.description}
                            </div>
                          </div>
                          <div className="flex items-center justify-between text-[10px] text-slate-500 font-sans">
                            <span className="font-bold text-slate-600">
                              {act.owner || "Unassigned"}
                            </span>
                            {act.jira_ticket ? (
                              <a
                                href={`https://tyagipriyansh07.atlassian.net/browse/${act.jira_ticket}`}
                                target="_blank"
                                rel="noreferrer"
                                className="text-mono font-bold text-brand-600 hover:underline flex items-center gap-1"
                              >
                                {act.jira_ticket}
                                <ExternalLink size={10} />
                              </a>
                            ) : (
                              <span className="text-slate-400">No ticket</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
}

function KPI({
  label,
  value,
  Icon,
  tone,
}: {
  label: string;
  value: number;
  Icon: any;
  tone: "brand" | "emerald" | "amber";
}) {
  const colors = {
    brand: "bg-brand-50 text-brand-600",
    emerald: "bg-emerald-50 text-emerald-600",
    amber: "bg-amber-50 text-amber-600",
  };
  return (
    <div className="card flex items-center justify-between px-4 py-3">
      <div>
        <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500 font-sans">{label}</div>
        <div className="mt-1 text-[24px] font-extrabold tracking-tight text-slate-900 font-sans">
          {value}
        </div>
      </div>
      <span
        className={`flex h-9 w-9 items-center justify-center rounded-lg shadow-sm ${colors[tone]}`}
      >
        <Icon size={16} />
      </span>
    </div>
  );
}