"use client";

import { useMemo } from "react";
import useSWR from "swr";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { fetchJson, api, type IncidentView, type LessonView } from "@/lib/api";
import { PageShell } from "@/components/page-shell";

type WeeklyDigest = {
  period_start: string;
  period_end: string;
  new_incidents: number;
  resolved_incidents: number;
  agent_share_pct: number;
  avg_mttr_minutes: number;
  open_breached_slas: number;
  summary_markdown: string;
};

export default function ReportsPage() {
  const { data: incidents } = useSWR<IncidentView[]>("/incidents", api.listIncidents, {
    refreshInterval: 60000,
  });
  const { data: lessons } = useSWR<LessonView[]>("/api/lessons", () =>
    api.listLessons({ limit: 200 })
  );
  const { data: digest } = useSWR<WeeklyDigest>("/api/reports/weekly?days=7", () =>
    fetchJson<WeeklyDigest>("/api/reports/weekly?days=7")
  );

  const stats = useMemo(() => {
    const inc = incidents || [];
    const ls = lessons || [];

    const sevCounts = { P1: 0, P2: 0, P3: 0, P4: 0 };
    inc.forEach((i) => {
      if (i.severity && i.severity in sevCounts) {
        sevCounts[i.severity as keyof typeof sevCounts] += 1;
      }
    });

    const statusCounts: Record<string, number> = {};
    inc.forEach((i) => {
      statusCounts[i.status] = (statusCounts[i.status] || 0) + 1;
    });

    const byService: Record<string, number> = {};
    inc.forEach((i) => {
      byService[i.service] = (byService[i.service] || 0) + 1;
    });
    const topServices = Object.entries(byService)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);

    const agentResolutions = ls.filter((l) => l.resolver === "agent").length;
    const humanResolutions = ls.length - agentResolutions;
    const agentPct = ls.length ? Math.round((agentResolutions / ls.length) * 100) : 0;
    const avgMttr = ls.length
      ? Math.round(ls.reduce((s, l) => s + l.resolution_minutes, 0) / ls.length)
      : 0;

    return {
      total: inc.length,
      sevCounts,
      statusCounts,
      topServices,
      agentResolutions,
      humanResolutions,
      agentPct,
      avgMttr,
      lessonsCount: ls.length,
    };
  }, [incidents, lessons]);

  return (
    <PageShell title="Reports" sub="weekly digest + CSV export">
    <main className="space-y-6">
      <div className="flex items-baseline justify-between">
        <div>
          <h2 className="text-lg font-semibold">Reports</h2>
          <p className="text-xs text-slate-500">
            High-level operational summary. Weekly digest runs in-process; download below.
          </p>
        </div>
        <a
          href={`${process.env.NEXT_PUBLIC_API_URL || "/api/agent"}/api/reports/incidents.csv`}
          className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium hover:bg-indigo-500"
        >
          Download CSV
        </a>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Total incidents" value={stats.total} />
        <Stat label="Resolutions captured" value={stats.lessonsCount} accent="indigo" />
        <Stat label="Agent share" value={`${stats.agentPct}%`} accent="emerald" />
        <Stat label="Avg MTTR (min)" value={stats.avgMttr} accent="amber" />
      </div>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold">By severity</h3>
          <ul className="space-y-2 text-sm">
            {(["P1", "P2", "P3", "P4"] as const).map((sev) => {
              const c = stats.sevCounts[sev];
              const pct = stats.total ? (c / stats.total) * 100 : 0;
              return (
                <li key={sev}>
                  <div className="flex justify-between">
                    <span className="font-mono">{sev}</span>
                    <span className="text-slate-700">{c}</span>
                  </div>
                  <div className="mt-1 h-2 overflow-hidden rounded bg-slate-100">
                    <div className="h-full bg-indigo-500" style={{ width: `${pct}%` }} />
                  </div>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold">By status</h3>
          <ul className="space-y-1.5 text-sm">
            {Object.entries(stats.statusCounts).map(([status, count]) => (
              <li key={status} className="flex justify-between">
                <span className="text-slate-700">{status}</span>
                <span className="font-semibold">{count}</span>
              </li>
            ))}
            {Object.keys(stats.statusCounts).length === 0 && (
              <li className="text-slate-500">No incidents yet.</li>
            )}
          </ul>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold">Top services by incident count</h3>
        {stats.topServices.length === 0 ? (
          <div className="text-sm text-slate-500">No service data yet.</div>
        ) : (
          <ul className="space-y-2 text-sm">
            {stats.topServices.map(([svc, count]) => {
              const pct = stats.total ? (count / stats.total) * 100 : 0;
              return (
                <li key={svc}>
                  <div className="flex justify-between">
                    <span className="font-mono">{svc}</span>
                    <span className="text-slate-700">{count}</span>
                  </div>
                  <div className="mt-1 h-2 overflow-hidden rounded bg-slate-100">
                    <div className="h-full bg-amber-500" style={{ width: `${pct}%` }} />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {digest && (
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold">Weekly digest (last 7 days)</h3>
          <div className="prose prose-sm max-w-none text-slate-800">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {digest.summary_markdown}
            </ReactMarkdown>
          </div>
        </section>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500">
        <div className="font-semibold text-slate-800">Auto-dispatch (configure later)</div>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>Digest is generated every <code>weekly_digest_interval_seconds</code> (default 7 days)</li>
          <li>Wire <code>StatusNotificationPort</code> dispatch into the scheduler to post into Teams</li>
          <li>PDF export remains TODO</li>
        </ul>
      </section>
    </main>
    </PageShell>
  );
}
function Stat({
  label,
  value,
  accent = "slate",
}: {
  label: string;
  value: number | string;
  accent?: "slate" | "amber" | "emerald" | "indigo";
}) {
  const accentClass = {
    slate: "text-slate-800",
    amber: "text-amber-600",
    emerald: "text-emerald-700",
    indigo: "text-indigo-600",
  }[accent];
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${accentClass}`}>{value}</div>
    </div>
  );
}