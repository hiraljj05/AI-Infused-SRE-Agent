"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
  AlertTriangle,
  ArrowUpRight,
  Filter,
  RefreshCw,
  Search,
} from "lucide-react";
import { api, type IncidentView } from "@/lib/api";
import { SeverityBadge } from "@/components/severity-badge";
import { JiraStatusBadge } from "@/components/jira-status-badge";
import {
  ACTIVE_STATUSES,
  IncidentStatusBadge,
  INCIDENT_STATUS_TABS,
  type IncidentStatusTab,
} from "@/components/incident-status";
import { PageShell } from "@/components/page-shell";
import { IncidentVolumeChart } from "@/components/dashboard-charts";

function relTime(iso: string) {
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function IncidentsPage() {
  const [tab, setTab] = useState<IncidentStatusTab>("all");
  const [query, setQuery] = useState("");
  const { data, error, isLoading, mutate, isValidating } = useSWR<IncidentView[]>(
    "/incidents",
    api.listIncidents,
    { refreshInterval: 5000 },
  );

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: 0, active: 0 };
    (data || []).forEach((i) => {
      c.all += 1;
      const s = i.status.toLowerCase();
      c[s] = (c[s] || 0) + 1;
      if (ACTIVE_STATUSES.has(s)) c.active += 1;
    });
    return c;
  }, [data]);

  const filtered = useMemo(() => {
    let rows = data || [];
    if (tab !== "all") {
      if (tab === "active") {
        rows = rows.filter((i) => ACTIVE_STATUSES.has(i.status.toLowerCase()));
      } else {
        rows = rows.filter((i) => i.status.toLowerCase() === tab);
      }
    }
    const q = query.trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (i) =>
          i.id.toLowerCase().includes(q) ||
          i.service.toLowerCase().includes(q) ||
          i.initial_signal.toLowerCase().includes(q) ||
          (i.jira_ticket_key || "").toLowerCase().includes(q),
      );
    }
    return rows;
  }, [data, tab, query]);

  return (
    <PageShell
      title="Incidents"
      sub="Real-time incident inbox · auto-refreshing every 5 s"
      right={
        <button
          onClick={() => mutate()}
          className="btn-ghost"
          disabled={isValidating}
          title="Refresh"
        >
          <RefreshCw size={14} className={isValidating ? "animate-spin" : ""} />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      }
    >
      <div className="mb-5 h-[240px] card p-4">
        <IncidentVolumeChart incidents={data || []} />
      </div>

      {/* Tabs + search ------------------------------------------------ */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="tabs">
          {INCIDENT_STATUS_TABS.map((t) => {
            const n = counts[t.id] || 0;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`tab ${active ? "tab-active" : ""}`}
              >
                {t.label}
                <span
                  className={`ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                    active
                      ? "bg-brand-100 text-brand-700"
                      : "bg-slate-200/70 text-slate-600"
                  }`}
                >
                  {n}
                </span>
              </button>
            );
          })}
        </div>

        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search id, service, signal…"
            className="input pl-9 sm:w-72"
          />
        </div>
      </div>

      {/* List ------------------------------------------------------ */}
      <div className="space-y-3">
        {isLoading && (
          <div className="space-y-3">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="skeleton h-[88px] w-full rounded-lg" />
            ))}
          </div>
        )}

        {error && (
          <div className="card px-5 py-6 text-sm text-rose-600">
            Failed to load incidents.
          </div>
        )}

        {!isLoading && !error && filtered.length === 0 && (
          <div className="card flex flex-col items-center justify-center px-5 py-16 text-center">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
              <Filter size={20} className="text-slate-400" />
            </div>
            <div className="text-sm font-semibold text-slate-700 font-sans">
              No incidents match this filter
            </div>
            <div className="mt-1 text-[12px] text-slate-500 font-sans">
              Try a different status or clear your search.
            </div>
          </div>
        )}

        {!isLoading && !error && filtered.length > 0 && (
          <div className="grid gap-3">
            {filtered.map((inc) => (
              <Link
                key={inc.id}
                href={`/incidents/${inc.id}`}
                className={`inc-card ${inc.severity?.toLowerCase() || 'p3'} group block`}
              >
                <div className="flex flex-col items-center justify-center px-2">
                  <SeverityBadge severity={inc.severity} />
                  <div className="mt-1.5 text-[10px] text-slate-400 font-sans">{relTime(inc.detected_at)}</div>
                </div>
                
                <div className="grid grid-cols-[1fr_auto_auto] gap-4 items-center min-w-0">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <div className="text-mono text-[12.5px] font-bold text-slate-900 group-hover:text-brand-600 transition-colors">
                        {inc.id}
                      </div>
                      <div className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-600 font-sans">
                        {inc.service}
                      </div>
                      <IncidentStatusBadge status={inc.status} />
                    </div>
                    <div className="mt-1 truncate text-[12px] text-slate-600 font-sans">
                      {inc.initial_signal}
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-[10.5px] text-slate-500 font-sans">
                      <span className="font-semibold text-slate-700">Top RCA:</span>
                      <span className="truncate max-w-[400px]">
                        {inc.rca_hypotheses[0]?.description || "(pending)"}
                      </span>
                      {inc.rca_hypotheses[0]?.confidence != null && (
                        <span className="font-bold text-brand-600">
                          {(inc.rca_hypotheses[0].confidence * 100).toFixed(0)}% conf
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="hidden sm:block">
                    {inc.jira_ticket_key ? (
                      <div className="flex flex-col items-end gap-1">
                        <div className="text-mono text-[11px] font-bold text-slate-700">
                          {inc.jira_ticket_key}
                        </div>
                        <JiraStatusBadge
                          status={inc.jira_ticket_status}
                          updatedAt={inc.jira_ticket_status_updated_at}
                        />
                      </div>
                    ) : (
                      <span className="text-[11px] text-slate-400 font-sans">—</span>
                    )}
                  </div>

                  <div className="flex items-center justify-end pr-2 opacity-0 transition-opacity group-hover:opacity-100">
                    <ArrowUpRight size={18} className="text-brand-500" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Footer hint -------------------------------------------------- */}
      {!isLoading && !error && (
        <div className="mt-4 flex items-center gap-1.5 text-[11px] text-slate-500 font-sans">
          <AlertTriangle size={12} className="text-amber-500" />
          Showing {filtered.length} of {data?.length || 0} incidents · click any row to open the command center.
        </div>
      )}
    </PageShell>
  );
}