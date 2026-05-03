"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { GaugeCircle, RefreshCw, Search } from "lucide-react";
import { api, type EventView } from "@/lib/api";
import { PageShell } from "@/components/page-shell";

const TYPE_STYLES: Record<string, { cls: string; emoji: string }> = {
  IncidentDetected:        { cls: "bg-rose-50 text-rose-700 border-rose-200",         emoji: "🚨" },
  IncidentTriaged:         { cls: "bg-amber-50 text-amber-700 border-amber-200",      emoji: "⚖️" },
  EvidenceGathered:        { cls: "bg-sky-50 text-sky-700 border-sky-200",            emoji: "🔬" },
  RootCauseHypothesized:   { cls: "bg-violet-50 text-violet-700 border-violet-200",   emoji: "🧠" },
  ActionProposed:          { cls: "bg-blue-50 text-blue-700 border-blue-200",         emoji: "🔧" },
  ApprovalRequested:       { cls: "bg-amber-50 text-amber-700 border-amber-200",      emoji: "✋" },
  ApprovalGranted:         { cls: "bg-emerald-50 text-emerald-700 border-emerald-200", emoji: "✅" },
  ApprovalRejected:        { cls: "bg-rose-50 text-rose-700 border-rose-200",         emoji: "❌" },
  ApprovalEscalated:       { cls: "bg-orange-50 text-orange-700 border-orange-200",   emoji: "📣" },
  ApprovalTimedOut:        { cls: "bg-orange-50 text-orange-700 border-orange-200",   emoji: "⏰" },
  ActionExecuted:          { cls: "bg-blue-50 text-blue-700 border-blue-200",         emoji: "⚙️" },
  ActionVerified:          { cls: "bg-emerald-50 text-emerald-700 border-emerald-200", emoji: "🔍" },
  IncidentResolved:        { cls: "bg-emerald-50 text-emerald-700 border-emerald-200", emoji: "✅" },
  IncidentEscalated:       { cls: "bg-orange-50 text-orange-700 border-orange-200",   emoji: "🚨" },
  PostmortemGenerated:     { cls: "bg-brand-50 text-brand-700 border-brand-200",   emoji: "📝" },
  LessonExtracted:         { cls: "bg-violet-50 text-violet-700 border-violet-200",   emoji: "💡" },
};

function fmt(iso: string) {
  return new Date(iso).toLocaleString();
}

export default function AuditTrailPage() {
  const { data, error, isLoading, mutate, isValidating } = useSWR<EventView[]>(
    "audit-events",
    () => api.listEvents(undefined, 200),
    { refreshInterval: 5000 },
  );

  const [type, setType] = useState<string>("all");
  const [query, setQuery] = useState("");

  const types = useMemo(() => {
    const set = new Set<string>();
    (data || []).forEach((e) => set.add(e.event_type));
    return ["all", ...Array.from(set).sort()];
  }, [data]);

  const filtered = useMemo(() => {
    let rows = data || [];
    if (type !== "all") rows = rows.filter((e) => e.event_type === type);
    const q = query.trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (e) =>
          e.incident_id.toLowerCase().includes(q) ||
          e.event_type.toLowerCase().includes(q) ||
          e.caused_by.toLowerCase().includes(q) ||
          JSON.stringify(e.payload).toLowerCase().includes(q),
      );
    }
    return rows;
  }, [data, type, query]);

  return (
    <PageShell
      title="Audit Trail"
      sub="Every event the agent emits — across all incidents"
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
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="select"
          >
            {types.map((t) => (
              <option key={t} value={t}>
                {t === "all" ? "All event types" : t}
              </option>
            ))}
          </select>
          <span className="text-[11px] text-slate-500 font-sans">
            {filtered.length} of {data?.length || 0}
          </span>
        </div>
        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search payload, ID, actor…"
            className="input pl-9 sm:w-80"
          />
        </div>
      </div>

      {isLoading && <div className="text-[12px] text-slate-500 font-sans">Loading…</div>}
      {error && (
        <div className="text-[12px] text-rose-600 font-sans">Failed to load events.</div>
      )}

      {!isLoading && !error && filtered.length === 0 && (
        <div className="card flex flex-col items-center justify-center px-5 py-16 text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
            <GaugeCircle size={20} className="text-slate-400" />
          </div>
          <div className="text-[13px] font-bold text-slate-700 font-sans">
            No events match this filter
          </div>
          <div className="mt-1 text-[11px] text-slate-500 font-sans">
            Try a different type or clear your search.
          </div>
        </div>
      )}

      {!isLoading && !error && filtered.length > 0 && (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/80 text-left text-[11px] uppercase tracking-wider text-slate-500 font-sans">
                  <th className="px-5 py-2.5 font-bold">Time</th>
                  <th className="px-2 py-2.5 font-bold">Incident</th>
                  <th className="px-2 py-2.5 font-bold">Event Type</th>
                  <th className="px-2 py-2.5 font-bold">Actor</th>
                  <th className="px-5 py-2.5 font-bold">Payload</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((e) => {
                  const meta = TYPE_STYLES[e.event_type] || {
                    cls: "bg-slate-50 text-slate-700 border-slate-200",
                    emoji: "·",
                  };
                  return (
                    <tr
                      key={e.event_id}
                      className="group border-b border-slate-100 last:border-0 hover:bg-brand-50/30"
                    >
                      <td className="whitespace-nowrap px-5 py-3 align-top text-[11px] text-slate-500 font-sans">
                        {fmt(e.occurred_at)}
                      </td>
                      <td className="whitespace-nowrap px-2 py-3 align-top">
                        <Link
                          href={`/incidents/${e.incident_id}`}
                          className="text-mono text-[12px] font-bold text-brand-600 hover:underline"
                        >
                          {e.incident_id}
                        </Link>
                      </td>
                      <td className="whitespace-nowrap px-2 py-3 align-top">
                        <span
                          className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[10px] font-bold font-sans ${meta.cls}`}
                        >
                          <span>{meta.emoji}</span>
                          {e.event_type}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-2 py-3 align-top text-[11.5px] font-bold text-slate-700 font-sans">
                        {e.caused_by}
                      </td>
                      <td className="px-5 py-3 align-top">
                        <div className="max-w-[400px] overflow-hidden rounded-md bg-slate-50 p-2 text-mono text-[10px] text-slate-600 border border-slate-100">
                          {JSON.stringify(e.payload)}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </PageShell>
  );
}