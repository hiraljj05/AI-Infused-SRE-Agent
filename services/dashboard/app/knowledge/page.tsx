"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { api, type LessonView } from "@/lib/api";
import { PageShell } from "@/components/page-shell";

const CATEGORIES = [
  "all",
  "connection_pool",
  "oom",
  "latency",
  "deploy_regression",
  "network",
  "upstream_dependency",
  "db_lock",
  "queue_backup",
  "config_error",
  "cert_expiry",
  "crash_loop",
  "other",
];

const RESOLVERS = ["all", "agent", "human"];

export default function KnowledgePage() {
  const [category, setCategory] = useState("all");
  const [resolver, setResolver] = useState("all");
  const [search, setSearch] = useState("");

  const { data: lessons, isLoading, error } = useSWR<LessonView[]>(
    `/api/lessons?category=${category}&resolver=${resolver}`,
    () => api.listLessons({
      category: category === "all" ? undefined : category,
      resolver: resolver === "all" ? undefined : resolver,
      limit: 200,
    })
  );

  const filtered = useMemo(() => {
    if (!search) return lessons || [];
    const s = search.toLowerCase();
    return (lessons || []).filter(
      (l) =>
        l.root_cause?.toLowerCase().includes(s) ||
        l.fix_applied?.toLowerCase().includes(s) ||
        (l.tags || []).some((t) => t.toLowerCase().includes(s))
    );
  }, [lessons, search]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    (lessons || []).forEach((l) => {
      c[l.issue_category] = (c[l.issue_category] || 0) + 1;
    });
    return c;
  }, [lessons]);

  return (
    <PageShell title="Knowledge Base" sub="Lessons learnt from past incidents & postmortems">
      <div className="flex flex-col gap-4 animate-fade-in">
        <div className="card p-4">
          <div className="flex flex-wrap gap-3">
            <input
              className="input flex-1 min-w-[180px]"
              placeholder="Search root cause, fix, or tag..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select
              className="select w-[180px]"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c === "all" ? "All Categories" : c}
                  {c !== "all" && counts[c] ? ` (${counts[c]})` : ""}
                </option>
              ))}
            </select>
            <select
              className="select w-[160px]"
              value={resolver}
              onChange={(e) => setResolver(e.target.value)}
            >
              {RESOLVERS.map((r) => (
                <option key={r} value={r}>
                  {r === "all" ? "All Resolvers" : r === "agent" ? "🤖 Agent" : "👤 Human"}
                </option>
              ))}
            </select>
          </div>
        </div>

        {isLoading && <div className="text-center text-[12px] text-slate-500 py-8 font-sans">Loading lessons...</div>}
        {error && <div className="text-center text-[12px] text-rose-500 py-8 font-sans">Failed to load lessons.</div>}

        {!isLoading && !error && filtered.length === 0 && (
          <div className="card flex flex-col items-center justify-center py-12 text-center text-[12px] text-slate-500 font-sans">
            No lessons match your filters.
          </div>
        )}

        {!isLoading && !error && filtered.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((l) => (
              <div key={l.id} className="card p-4 flex flex-col hover:shadow-md transition-shadow">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <span className="rounded bg-brand-50 px-2 py-0.5 text-[10px] font-bold text-brand-700 font-sans">
                    {l.issue_category}
                  </span>
                  <span className="text-[10px] text-slate-500 font-sans">
                    {l.resolver === "agent" ? "🤖 agent" : `👤 ${l.resolver}`}
                  </span>
                  <span className="text-[10px] text-slate-500 font-sans">· {l.resolution_minutes}m</span>
                  {l.human_verified && (
                    <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[9px] font-bold text-emerald-700 font-sans ml-auto">
                      Verified
                    </span>
                  )}
                </div>
                
                <div className="flex-1 space-y-3">
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-sans mb-1">Root Cause</div>
                    <p className="text-[12px] text-slate-800 font-sans line-clamp-3">{l.root_cause}</p>
                  </div>
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-sans mb-1">Fix Applied</div>
                    <p className="text-[12px] text-slate-800 font-sans line-clamp-3">{l.fix_applied}</p>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                  <div className="flex flex-wrap gap-1.5">
                    {(l.tags || []).slice(0, 3).map((t, i) => (
                      <span key={i} className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-medium text-slate-600 font-sans">
                        #{t}
                      </span>
                    ))}
                  </div>
                  <Link
                    href={`/incidents/${l.incident_id}`}
                    className="text-[11px] font-semibold text-brand-600 hover:underline font-sans flex-shrink-0"
                  >
                    {l.incident_id} →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </PageShell>
  );
}
