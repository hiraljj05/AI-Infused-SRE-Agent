"use client";

import { useMemo } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, type AppView, type IncidentView, type LessonView, type ProjectView } from "@/lib/api";
import { SeverityBadge } from "@/components/severity-badge";
import { PageShell } from "@/components/page-shell";

const TIER_COLOR: Record<string, string> = {
  "tier-0": "text-red-600",
  "tier-1": "text-orange-700",
  "tier-2": "text-yellow-700",
  "tier-3": "text-blue-700",
};

export default function AppDetailPage() {
  const params = useParams<{ id: string }>();
  const appId = params.id;

  const { data: app, error: appErr, isLoading: appLoading } = useSWR<AppView>(
    appId ? `/api/apps/${appId}` : null,
    () => api.getApp(appId)
  );
  const { data: projects } = useSWR<ProjectView[]>("/api/projects", api.listProjects);
  const { data: allIncidents } = useSWR<IncidentView[]>("/incidents-all", () =>
    fetch(
      `${process.env.NEXT_PUBLIC_API_URL || "/api/agent"}/incidents`
    ).then((r) => r.json())
  );
  const { data: lessons } = useSWR<LessonView[]>(
    appId ? `/api/lessons?app=${appId}` : null,
    () => api.listLessons({ limit: 100 })
  );

  const project = useMemo(
    () => (projects || []).find((p) => app && p.id === app.project_id),
    [projects, app]
  );

  const appIncidents = useMemo(() => {
    if (!app || !allIncidents) return [];
    return allIncidents.filter((i) => i.service === app.name);
  }, [app, allIncidents]);

  const appLessons = useMemo(() => {
    if (!app || !lessons) return [];
    return lessons.filter((l) => l.app_id === app.id);
  }, [app, lessons]);

  if (appLoading)
    return (
      <PageShell title="App" sub="loading…">
        <div className="text-sm text-slate-500">Loading app...</div>
      </PageShell>
    );
  if (appErr || !app) {
    return (
      <PageShell title="App" sub="not found">
        <main className="space-y-4">
          <Link href="/apps" className="text-sm text-indigo-600 hover:text-indigo-700">
            ← Apps
          </Link>
          <div className="text-sm text-red-600">App not found.</div>
        </main>
      </PageShell>
    );
  }

  const grafanaUrl = app.grafana_dashboard_uid
    ? `http://localhost:3001/d/${app.grafana_dashboard_uid}`
    : null;

  const resolvedCount = appIncidents.filter((i) => i.status === "resolved").length;
  const activeCount = appIncidents.filter((i) => i.status !== "resolved" && i.status !== "closed").length;

  return (
    <PageShell title={app.name} sub={`${app.tier} · ${app.namespace}`}>
    <main className="space-y-6">
      <div>
        <Link href="/apps" className="text-xs text-indigo-600 hover:text-indigo-700">
          ← Apps
        </Link>
        <div className="mt-2 flex items-baseline gap-3">
          <h2 className="font-mono text-xl font-semibold">{app.name}</h2>
          <span className={`text-xs font-semibold ${TIER_COLOR[app.tier] || "text-slate-700"}`}>
            {app.tier}
          </span>
          {!app.enabled && (
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">
              disabled
            </span>
          )}
        </div>
        <p className="mt-1 text-xs text-slate-500">
          {project ? `${project.name} (${project.key})` : app.project_id} · namespace{" "}
          <span className="font-mono">{app.namespace}</span>
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Total incidents" value={appIncidents.length} />
        <Stat label="Active" value={activeCount} accent={activeCount > 0 ? "amber" : "slate"} />
        <Stat label="Resolved" value={resolvedCount} accent="emerald" />
        <Stat label="Lessons" value={appLessons.length} accent="indigo" />
      </div>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold">Owners</h3>
          {app.owners.length === 0 ? (
            <div className="text-sm text-slate-500">No owners assigned.</div>
          ) : (
            <ul className="space-y-2 text-sm">
              {app.owners.map((o, i) => (
                <li key={i} className="flex justify-between">
                  <span className="text-slate-700">{o.email}</span>
                  <span
                    className={
                      o.role === "primary"
                        ? "rounded bg-indigo-100 px-1.5 py-0.5 text-xs text-indigo-700"
                        : "rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500"
                    }
                  >
                    {o.role}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold">Integrations</h3>
          <ul className="space-y-2 text-sm">
            <li>
              <span className="text-slate-500">Runbook template:</span>{" "}
              <span className="font-mono text-xs">{app.runbook_template_id}</span>
            </li>
            <li>
              <span className="text-slate-500">Grafana:</span>{" "}
              {grafanaUrl ? (
                <a
                  href={grafanaUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-indigo-600 hover:text-indigo-700"
                >
                  Open dashboard ↗
                </a>
              ) : (
                <span className="text-slate-500">not provisioned</span>
              )}
            </li>
            {project?.jira_project_key && (
              <li>
                <span className="text-slate-500">Jira project:</span>{" "}
                <span className="font-mono text-xs">{project.jira_project_key}</span>
              </li>
            )}
            {project?.teams_channel_id && (
              <li>
                <span className="text-slate-500">Teams channel:</span>{" "}
                <span className="font-mono text-xs">{project.teams_channel_id}</span>
              </li>
            )}
            {project?.email_distribution && (
              <li>
                <span className="text-slate-500">Email DL:</span>{" "}
                <span className="font-mono text-xs">{project.email_distribution}</span>
              </li>
            )}
          </ul>
        </div>
      </section>

      <section>
        <h3 className="mb-2 text-sm font-semibold">Recent incidents</h3>
        {appIncidents.length === 0 ? (
          <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-700">
            No incidents recorded for this app. Healthy ✓
          </div>
        ) : (
          <ul className="space-y-2">
            {appIncidents.slice(0, 10).map((inc) => (
              <li
                key={inc.id}
                className="rounded border border-slate-200 bg-white p-3 text-sm"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={inc.severity} />
                    <Link
                      href={`/incidents/${inc.id}`}
                      className="font-mono text-xs hover:underline"
                    >
                      {inc.id}
                    </Link>
                  </div>
                  <span className="text-xs uppercase text-slate-500">{inc.status}</span>
                </div>
                <p className="mt-1 text-xs text-slate-500">{inc.initial_signal}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="mb-2 text-sm font-semibold">Lessons learnt for this app</h3>
        {appLessons.length === 0 ? (
          <div className="text-sm text-slate-500">
            No lessons captured yet — they appear here after incidents close.
          </div>
        ) : (
          <ul className="space-y-2">
            {appLessons.slice(0, 5).map((l) => (
              <li
                key={l.id}
                className="rounded border border-slate-200 bg-white p-3 text-sm"
              >
                <div className="flex items-center justify-between">
                  <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-xs text-indigo-600">
                    {l.issue_category}
                  </span>
                  <span className="text-xs text-slate-500">
                    by {l.resolver} · {l.resolution_minutes} min
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-700">
                  <span className="text-slate-500">Cause:</span> {l.root_cause}
                </p>
                <p className="mt-1 text-xs text-slate-700">
                  <span className="text-slate-500">Fix:</span> {l.fix_applied}
                </p>
              </li>
            ))}
          </ul>
        )}
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
  value: number;
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
