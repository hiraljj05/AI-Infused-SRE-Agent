"use client";

import useSWR from "swr";
import { api, type PeopleAggregate } from "@/lib/api";
import { PageShell } from "@/components/page-shell";

export default function PeoplePage() {
  const { data, isLoading, error } = useSWR<PeopleAggregate[]>(
    "/api/people/aggregates",
    api.peopleAggregates,
    { refreshInterval: 60000 }
  );

  const totalAgent = (data || [])
    .filter((p) => p.resolver === "agent")
    .reduce((s, p) => s + p.total_resolutions, 0);
  const totalHuman = (data || [])
    .filter((p) => p.resolver !== "agent")
    .reduce((s, p) => s + p.total_resolutions, 0);
  const grandTotal = totalAgent + totalHuman;
  const agentPct = grandTotal ? Math.round((totalAgent / grandTotal) * 100) : 0;

  return (
    <PageShell title="People & Agent Effectiveness" sub="Aggregated from lessons-learnt corpus. Shows who resolved which incidents.">
      <div className="flex flex-col gap-4 animate-fade-in">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Total resolutions" value={grandTotal} />
          <Stat label="Agent" value={totalAgent} accent="emerald" />
          <Stat label="Human" value={totalHuman} accent="amber" />
          <Stat label="Agent share" value={`${agentPct}%`} accent="brand" />
        </div>

        {isLoading && <div className="text-[12px] text-slate-500 font-sans">Loading...</div>}
        {error && <div className="text-[12px] text-rose-600 font-sans">Failed to load people aggregates</div>}

        {!isLoading && !error && (data || []).length === 0 && (
          <div className="card flex flex-col items-center justify-center px-5 py-16 text-center">
            <div className="text-[13px] font-bold text-slate-700 font-sans">
              No resolutions captured yet.
            </div>
            <div className="mt-1 text-[11px] text-slate-500 font-sans">
              Metrics will appear here once incidents are resolved and lessons are extracted.
            </div>
          </div>
        )}

        {!isLoading && !error && (data || []).length > 0 && (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/80 text-left text-[11px] uppercase tracking-wider text-slate-500 font-sans">
                    <th className="px-5 py-2.5 font-bold">Resolver</th>
                    <th className="px-2 py-2.5 font-bold text-right">Resolutions</th>
                    <th className="px-2 py-2.5 font-bold text-right">Avg time (min)</th>
                    <th className="px-5 py-2.5 font-bold">Top categories</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(data || []).map((p) => (
                    <tr key={p.resolver} className="border-b border-slate-100 last:border-0 hover:bg-brand-50/30">
                      <td className="px-5 py-3">
                        {p.resolver === "agent" ? (
                          <span className="flex items-center gap-2 font-bold text-brand-600 font-sans">🤖 Agent</span>
                        ) : (
                          <span className="flex items-center gap-2 font-bold text-slate-700 font-sans">👤 {p.resolver}</span>
                        )}
                      </td>
                      <td className="px-2 py-3 text-right font-extrabold text-slate-900 font-sans">{p.total_resolutions}</td>
                      <td className="px-2 py-3 text-right text-slate-600 font-sans">{p.avg_resolution_minutes}</td>
                      <td className="px-5 py-3">
                        <div className="flex flex-wrap gap-1.5">
                          {p.top_categories.map((c, i) => (
                            <span
                              key={i}
                              className="rounded bg-brand-50 px-1.5 py-0.5 text-[10px] font-bold text-brand-700 font-sans border border-brand-100"
                            >
                              {c.category} ({c.count})
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
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
  accent?: "slate" | "amber" | "emerald" | "brand";
}) {
  const accentClass = {
    slate: "text-slate-800",
    amber: "text-amber-600",
    emerald: "text-emerald-600",
    brand: "text-brand-600",
  }[accent];
  return (
    <div className="card p-4">
      <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500 font-sans">{label}</div>
      <div className={`mt-1 text-[24px] font-extrabold leading-none font-sans ${accentClass}`}>{value}</div>
    </div>
  );
}