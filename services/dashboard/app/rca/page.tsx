"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
  ArrowUpRight,
  Brain,
  FileSearch,
  RefreshCw,
  Search,
} from "lucide-react";
import { api, type IncidentView } from "@/lib/api";
import { PageShell } from "@/components/page-shell";
import { SeverityBadge } from "@/components/severity-badge";
import { IncidentStatusBadge } from "@/components/incident-status";
import { RCAConfidenceChart } from "@/components/dashboard-charts";

function confidenceBar(c: number) {
  const pct = Math.min(100, Math.max(0, Math.round(c * 100)));
  let color = "bg-emerald-500";
  if (pct < 70) color = "bg-amber-500";
  if (pct < 50) color = "bg-rose-500";
  return { pct, color };
}

export default function RCAConsolePage() {
  const { data, error, isLoading, mutate, isValidating } = useSWR<IncidentView[]>(
    "/incidents",
    api.listIncidents,
    { refreshInterval: 10000 },
  );
  const [query, setQuery] = useState("");

  const withRca = useMemo(
    () => (data || []).filter((i) => i.rca_hypotheses.length > 0),
    [data],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return withRca;
    return withRca.filter(
      (i) =>
        i.id.toLowerCase().includes(q) ||
        i.service.toLowerCase().includes(q) ||
        i.rca_hypotheses[0]?.description.toLowerCase().includes(q),
    );
  }, [withRca, query]);

  const avgConfidence = useMemo(() => {
    if (withRca.length === 0) return 0;
    const sum = withRca.reduce(
      (s, i) => s + (i.rca_hypotheses[0]?.confidence || 0),
      0,
    );
    return sum / withRca.length;
  }, [withRca]);

  return (
    <PageShell
      title="RCA Console"
      sub="Root-cause hypotheses across every active investigation"
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
      {/* KPI strip & Chart --------------------------------------------------- */}
      <div className="mb-4 grid gap-4 lg:grid-cols-[1fr,300px]">
        <div className="grid gap-3 md:grid-cols-1">
          <div className="card flex items-center justify-between px-4 py-3">
            <div>
              <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500 font-sans">With hypotheses</div>
              <div className="mt-1 text-[24px] font-extrabold tracking-tight text-slate-900 font-sans">
                {withRca.length}
              </div>
            </div>
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 shadow-sm">
              <Brain size={16} />
            </span>
          </div>
          <div className="card flex items-center justify-between px-4 py-3">
            <div>
              <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500 font-sans">Average confidence</div>
              <div className="mt-1 text-[24px] font-extrabold tracking-tight text-slate-900 font-sans">
                {(avgConfidence * 100).toFixed(0)}%
              </div>
            </div>
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 shadow-sm">
              <FileSearch size={16} />
            </span>
          </div>
          <div className="card flex items-center justify-between px-4 py-3">
            <div>
              <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500 font-sans">Auto-remediated</div>
              <div className="mt-1 text-[24px] font-extrabold tracking-tight text-slate-900 font-sans">
                {withRca.filter(i => i.status === 'resolved').length}
              </div>
            </div>
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-50 text-sky-600 shadow-sm">
              <RefreshCw size={16} />
            </span>
          </div>
        </div>
        <RCAConfidenceChart incidents={withRca} />
      </div>

      {/* Controls -------------------------------------------------- */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search RCA, service, ID…"
            className="input pl-9 sm:w-80"
          />
        </div>
      </div>

      {/* List ------------------------------------------------------ */}
      {isLoading && <div className="text-[12px] text-slate-500 font-sans">Loading…</div>}
      {error && <div className="text-[12px] text-rose-600 font-sans">Failed to load.</div>}

      {!isLoading && !error && filtered.length === 0 && (
        <div className="card flex flex-col items-center justify-center px-5 py-16 text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
            <Brain size={20} className="text-slate-400" />
          </div>
          <div className="text-[13px] font-bold text-slate-700 font-sans">
            No RCA hypotheses yet
          </div>
          <div className="mt-1 text-[11px] text-slate-500 font-sans">
            The agent generates root cause hypotheses automatically when incidents are triaged.
          </div>
        </div>
      )}

      {!isLoading && !error && filtered.length > 0 && (
        <div className="grid gap-3">
          {filtered.map((inc) => {
            const top = inc.rca_hypotheses[0];
            const others = inc.rca_hypotheses.slice(1);
            const { pct, color } = confidenceBar(top.confidence);

            return (
              <div key={inc.id} className="card overflow-hidden">
                <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-3 bg-slate-50/50">
                  <div className="flex items-center gap-3">
                    <Link
                      href={`/incidents/${inc.id}`}
                      className="text-mono text-[12.5px] font-bold text-brand-600 hover:underline"
                    >
                      {inc.id}
                    </Link>
                    <SeverityBadge severity={inc.severity} />
                    <IncidentStatusBadge status={inc.status} />
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-600 font-sans">
                      {inc.service}
                    </span>
                  </div>
                  <Link
                    href={`/incidents/${inc.id}`}
                    className="inline-flex items-center gap-1 text-[11.5px] font-bold text-brand-600 hover:underline font-sans"
                  >
                    Open <ArrowUpRight size={12} />
                  </Link>
                </div>

                <div className="px-5 py-4">
                  <div className="text-[12.5px] leading-relaxed text-slate-800 font-sans">
                    {top.description}
                  </div>

                  <div className="mt-3 flex items-center gap-3">
                    <div className="flex-1">
                      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={`h-full ${color}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                    <div className="text-[11.5px] font-bold text-slate-600 font-sans">
                      {pct}% · {top.confidence_label}
                    </div>
                  </div>

                  {top.supporting_evidence.length > 0 && (
                    <ul className="mt-3 list-disc space-y-1 pl-5 text-[12px] text-slate-600 font-sans">
                      {top.supporting_evidence.slice(0, 3).map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  )}

                  {top.referenced_runbook_ids.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {top.referenced_runbook_ids.map((r) => (
                        <span
                          key={r}
                          className="text-mono rounded-md bg-brand-50 px-1.5 py-0.5 text-[11px] font-bold text-brand-700 ring-1 ring-brand-200"
                        >
                          {r}
                        </span>
                      ))}
                    </div>
                  )}

                  {others.length > 0 && (
                    <details className="group mt-3">
                      <summary className="cursor-pointer list-none text-[11px] font-bold text-slate-500 hover:text-slate-700 font-sans">
                        + {others.length} alternate hypothes
                        {others.length === 1 ? "is" : "es"}
                      </summary>
                      <div className="mt-2 space-y-1.5 border-l-2 border-slate-200 pl-3">
                        {others.map((h, i) => (
                          <div key={i} className="text-[12px] text-slate-600 font-sans">
                            <span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-500">
                              {(h.confidence * 100).toFixed(0)}%
                            </span>
                            {h.description}
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}