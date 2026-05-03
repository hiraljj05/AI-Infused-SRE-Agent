"use client";

import useSWR from "swr";
import Link from "next/link";
import { useMemo, useState } from "react";
import { api, type AppView, type ProjectView } from "@/lib/api";
import { PageShell } from "@/components/page-shell";
import { Boxes, Search } from "lucide-react";

const TIER_COLOR: Record<string, string> = {
  "tier-0": "bg-rose-100 text-rose-700 border-rose-200",
  "tier-1": "bg-amber-100 text-amber-700 border-amber-200",
  "tier-2": "bg-emerald-100 text-emerald-700 border-emerald-200",
  "tier-3": "bg-slate-100 text-slate-700 border-slate-200",
};

export default function AppsPage() {
  const { data: apps, error: appsErr, isLoading } = useSWR<AppView[]>(
    "/api/apps",
    api.listApps,
    { refreshInterval: 30000 }
  );
  const { data: projects } = useSWR<ProjectView[]>("/api/projects", api.listProjects);

  const [search, setSearch] = useState("");
  const [tierFilter, setTierFilter] = useState<string>("all");
  const [projectFilter, setProjectFilter] = useState<string>("all");

  const projectMap = useMemo(() => {
    const m = new Map<string, ProjectView>();
    (projects || []).forEach((p) => m.set(p.id, p));
    return m;
  }, [projects]);

  const filtered = useMemo(() => {
    return (apps || []).filter((a) => {
      if (tierFilter !== "all" && a.tier !== tierFilter) return false;
      if (projectFilter !== "all" && a.project_id !== projectFilter) return false;
      if (search && !a.name.toLowerCase().includes(search.toLowerCase()) && !a.namespace.toLowerCase().includes(search.toLowerCase())) {
        return false;
      }
      return true;
    });
  }, [apps, tierFilter, projectFilter, search]);

  return (
    <PageShell
      title="Applications"
      sub={apps ? `Managing ${filtered.length} of ${apps.length} applications` : "Loading apps..."}
      right={
        <Link
          href="/apps/new"
          className="btn-primary"
        >
          + Onboard app
        </Link>
      }
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="select"
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
          >
            <option value="all">All tiers</option>
            <option value="tier-0">Tier 0 (Critical)</option>
            <option value="tier-1">Tier 1 (High)</option>
            <option value="tier-2">Tier 2 (Medium)</option>
            <option value="tier-3">Tier 3 (Low)</option>
          </select>
          <select
            className="select"
            value={projectFilter}
            onChange={(e) => setProjectFilter(e.target.value)}
          >
            <option value="all">All projects</option>
            {(projects || []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.key})
              </option>
            ))}
          </select>
        </div>
        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search apps, namespace…"
            className="input pl-9 sm:w-80"
          />
        </div>
      </div>

      {isLoading && <div className="text-[12px] text-slate-500 font-sans">Loading…</div>}
      {appsErr && <div className="text-[12px] text-rose-600 font-sans">Failed to load applications.</div>}

      {!isLoading && !appsErr && filtered.length === 0 && (
        <div className="card flex flex-col items-center justify-center px-5 py-16 text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
            <Boxes size={20} className="text-slate-400" />
          </div>
          <div className="text-[13px] font-bold text-slate-700 font-sans">
            No applications match this filter
          </div>
          <div className="mt-1 text-[11px] text-slate-500 font-sans">
            Try a different tier or clear your search.
          </div>
          {(apps || []).length === 0 && (
            <Link href="/apps/new" className="mt-4 text-[12px] font-bold text-brand-600 hover:underline font-sans">
              Onboard your first app →
            </Link>
          )}
        </div>
      )}

      {!isLoading && !appsErr && filtered.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((app) => {
            const p = projectMap.get(app.project_id);
            return (
              <div
                key={app.id}
                className="card flex flex-col p-4 transition-all hover:-translate-y-px hover:shadow-md"
              >
                <div className="mb-3 flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-[14px] font-bold text-slate-900 font-sans">
                      {app.name}
                    </div>
                    <div className="truncate text-[11px] text-slate-500 font-sans">
                      {app.namespace}
                    </div>
                  </div>
                  <span
                    className={`rounded border px-1.5 py-0.5 text-[10px] font-bold font-sans ${
                      TIER_COLOR[app.tier] || "bg-slate-100 text-slate-700 border-slate-200"
                    }`}
                  >
                    {app.tier}
                  </span>
                </div>

                <div className="mt-auto space-y-2 border-t border-slate-100 pt-3">
                  <div className="flex items-center justify-between text-[11px] font-sans">
                    <span className="text-slate-500">Project</span>
                    <span className="font-bold text-slate-700">
                      {p ? `${p.name} (${p.key})` : app.project_id}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px] font-sans">
                    <span className="text-slate-500">On-call Primary</span>
                    <span className="truncate font-bold text-slate-700 max-w-[120px]">
                      {app.owners?.find(o => o.role === 'primary')?.email || "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px] font-sans">
                    <span className="text-slate-500">On-call Secondary</span>
                    <span className="truncate font-bold text-slate-700 max-w-[120px]">
                      {app.owners?.find(o => o.role === 'secondary')?.email || "—"}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}