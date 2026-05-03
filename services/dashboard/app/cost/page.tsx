"use client";

import useSWR from "swr";
import { api, type CostBreakdown } from "@/lib/api";
import { PageShell } from "@/components/page-shell";

export default function CostPage() {
  const { data, isLoading, error } = useSWR<CostBreakdown>(
    "/api/cost/llm-tokens",
    api.costBreakdown,
    { refreshInterval: 30000 }
  );

  const maxDay = Math.max(...((data?.by_day || []).map((d) => d.tokens)), 1);
  const maxModel = Math.max(...((data?.by_model || []).map((m) => m.tokens)), 1);

  return (
    <PageShell title="Cost" sub="LLM token usage">
    <main className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Cost — LLM Token Usage</h2>
        <p className="text-xs text-slate-500">
          Aggregated from Prometheus counters. USD figures are rough estimates from blended
          per-model rates — use OpenRouter dashboard for billing.
        </p>
      </div>

      {isLoading && <div className="text-sm text-slate-500">Loading...</div>}
      {error && <div className="text-sm text-red-600">Failed to load cost data</div>}

      {data && (
        <>
          {data.notes && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-700">
              {data.notes}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Total tokens" value={fmt(data.total_tokens)} />
            <Stat label="Prompt tokens" value={fmt(data.prompt_tokens)} accent="indigo" />
            <Stat label="Completion tokens" value={fmt(data.completion_tokens)} accent="amber" />
            <Stat label="Estimated USD" value={`$${data.estimated_usd.toFixed(4)}`} accent="emerald" />
          </div>

          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold">By model</h3>
            {data.by_model.length === 0 ? (
              <div className="text-sm text-slate-500">No token usage recorded yet.</div>
            ) : (
              <ul className="space-y-2 text-sm">
                {data.by_model.map((m) => (
                  <li key={m.model}>
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs">{m.model}</span>
                      <span className="text-slate-700">
                        {fmt(m.tokens)} tokens · ${m.usd.toFixed(4)}
                      </span>
                    </div>
                    <div className="mt-1 h-2 overflow-hidden rounded bg-slate-100">
                      <div
                        className="h-full bg-indigo-500"
                        style={{ width: `${(m.tokens / maxModel) * 100}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold">Last 7 days</h3>
            {data.by_day.length === 0 ? (
              <div className="text-sm text-slate-500">No daily breakdown available.</div>
            ) : (
              <div className="flex h-40 items-end gap-2">
                {data.by_day.map((d) => (
                  <div key={d.day} className="flex flex-1 flex-col items-center gap-1">
                    <div
                      className="w-full rounded-t bg-indigo-500/60"
                      style={{ height: `${(d.tokens / maxDay) * 100}%` }}
                      title={`${fmt(d.tokens)} tokens`}
                    />
                    <div className="text-xs text-slate-500">{d.day.slice(5)}</div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <p className="text-xs text-slate-500">Data source: {data.source}</p>
        </>
      )}
    </main>
    </PageShell>
  );
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toString();
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