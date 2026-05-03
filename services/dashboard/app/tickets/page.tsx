"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
  ExternalLink,
  RefreshCw,
  Search,
  Ticket as TicketIcon,
} from "lucide-react";
import { api, type IncidentView } from "@/lib/api";
import { PageShell } from "@/components/page-shell";
import { SeverityBadge } from "@/components/severity-badge";
import { TicketStatusChart } from "@/components/dashboard-charts";

/** Map any Jira status string to one of our 4 board columns. */
function bucketize(status: string | null): "todo" | "in_progress" | "review" | "done" {
  const s = (status || "").toLowerCase();
  if (["done", "resolved", "closed"].includes(s)) return "done";
  if (["in progress", "in-progress", "executing"].includes(s)) return "in_progress";
  if (["in review", "review", "blocked"].includes(s)) return "review";
  return "todo";
}

const COLUMNS = [
  {
    id: "todo" as const,
    label: "To do",
    accent: "bg-slate-100 text-slate-700",
    bar: "bg-slate-400",
  },
  {
    id: "in_progress" as const,
    label: "In progress",
    accent: "bg-brand-100 text-brand-700",
    bar: "bg-brand-500",
  },
  {
    id: "review" as const,
    label: "Review / Blocked",
    accent: "bg-amber-100 text-amber-700",
    bar: "bg-amber-500",
  },
  {
    id: "done" as const,
    label: "Done",
    accent: "bg-emerald-100 text-emerald-700",
    bar: "bg-emerald-500",
  },
];

type View = "board" | "table";

export default function TicketsPage() {
  const { data, isLoading, error, mutate, isValidating } = useSWR<IncidentView[]>(
    "/incidents",
    api.listIncidents,
    { refreshInterval: 10000 },
  );

  const tickets = useMemo(
    () => (data || []).filter((i) => !!i.jira_ticket_key),
    [data],
  );

  const [view, setView] = useState<View>("board");
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return tickets;
    return tickets.filter(
      (t) =>
        t.jira_ticket_key?.toLowerCase().includes(q) ||
        t.service.toLowerCase().includes(q) ||
        t.initial_signal.toLowerCase().includes(q),
    );
  }, [tickets, query]);

  const grouped = useMemo(() => {
    const g: Record<string, IncidentView[]> = {
      todo: [],
      in_progress: [],
      review: [],
      done: [],
    };
    filtered.forEach((t) => g[bucketize(t.jira_ticket_status)].push(t));
    return g;
  }, [filtered]);

  return (
    <PageShell
      title="Jira Tickets"
      sub="Live status board · synced from Jira every 30 s"
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
        <TicketStatusChart tickets={data || []} />
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="tabs">
          <button
            onClick={() => setView("board")}
            className={`tab ${view === "board" ? "tab-active" : ""}`}
          >
            Board
          </button>
          <button
            onClick={() => setView("table")}
            className={`tab ${view === "table" ? "tab-active" : ""}`}
          >
            Table
          </button>
        </div>

        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search tickets, service…"
            className="input pl-9 sm:w-72"
          />
        </div>
      </div>

      {isLoading && (
        <div className="grid grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-96 w-full rounded-xl" />
          ))}
        </div>
      )}

      {error && (
        <div className="card px-5 py-6 text-sm text-rose-600">
          Failed to load tickets.
        </div>
      )}

      {!isLoading && !error && view === "board" && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {COLUMNS.map((col) => {
            const list = grouped[col.id];
            return (
              <div
                key={col.id}
                className="flex flex-col rounded-xl border border-slate-200 bg-slate-50/50 p-2.5 shadow-sm"
              >
                <div className="mb-3 flex items-center justify-between px-1">
                  <div className="flex items-center gap-2">
                    <div className={`h-2.5 w-2.5 rounded-full ${col.bar}`} />
                    <span className="text-[12px] font-bold uppercase tracking-widest text-slate-700 font-sans">
                      {col.label}
                    </span>
                  </div>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${col.accent} font-sans`}>
                    {list.length}
                  </span>
                </div>

                <div className="scrollbar-thin flex-1 space-y-2 overflow-y-auto pr-1">
                  {list.length === 0 && (
                    <div className="py-6 text-center text-[12px] text-slate-400 font-sans">
                      Empty
                    </div>
                  )}
                  {list.map((t) => (
                    <div
                      key={t.id}
                      className="group relative flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-3 shadow-sm transition-all hover:-translate-y-px hover:shadow-md cursor-pointer"
                    >
                      <div className="flex items-start justify-between gap-2">
                        {t.jira_ticket_url ? (
                          <a
                            href={t.jira_ticket_url}
                            target="_blank"
                            rel="noreferrer"
                            className="font-mono text-[12px] font-bold text-brand-600 hover:underline flex items-center gap-1"
                          >
                            {t.jira_ticket_key}
                            <ExternalLink size={10} />
                          </a>
                        ) : (
                          <span className="font-mono text-[12px] font-bold text-slate-800">
                            {t.jira_ticket_key}
                          </span>
                        )}
                        <SeverityBadge severity={t.severity} />
                      </div>

                      <div className="text-[12px] leading-snug text-slate-700 font-sans line-clamp-2">
                        {t.initial_signal}
                      </div>

                      <div className="mt-1 flex items-center justify-between">
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-600 font-sans">
                          {t.service}
                        </span>
                        <Link
                          href={`/incidents/${t.id}`}
                          className="text-[10px] font-semibold text-brand-600 opacity-0 transition-opacity group-hover:opacity-100 font-sans"
                        >
                          View Incident →
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Table view ----------------------------------------------- */}
      {!isLoading && filtered.length > 0 && view === "table" && (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/80 text-left text-[11px] uppercase tracking-wider text-slate-500 font-sans">
                  <th className="px-5 py-2.5 font-bold">Key</th>
                  <th className="px-2 py-2.5 font-bold">Status</th>
                  <th className="px-2 py-2.5 font-bold">Incident</th>
                  <th className="px-2 py-2.5 font-bold">Service</th>
                  <th className="px-2 py-2.5 font-bold">Sev</th>
                  <th className="px-2 py-2.5 font-bold">Updated</th>
                  <th className="px-5 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((t) => (
                  <tr
                    key={t.id}
                    className="border-b border-slate-100 last:border-0 hover:bg-brand-50/30"
                  >
                    <td className="px-5 py-3">
                      {t.jira_ticket_url ? (
                        <a
                          className="text-mono text-[12px] font-bold text-brand-600 hover:underline"
                          href={t.jira_ticket_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {t.jira_ticket_key}
                        </a>
                      ) : (
                        <span className="text-mono text-[12px] font-bold text-slate-800">
                          {t.jira_ticket_key}
                        </span>
                      )}
                    </td>
                    <td className="px-2 py-3">
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-slate-600 font-sans">
                        {t.jira_ticket_status || "Unknown"}
                      </span>
                    </td>
                    <td className="px-2 py-3">
                      <Link
                        href={`/incidents/${t.id}`}
                        className="text-mono text-[12px] font-bold text-slate-600 hover:text-brand-600 hover:underline"
                      >
                        {t.id}
                      </Link>
                    </td>
                    <td className="px-2 py-3 font-bold text-slate-900 font-sans">
                      {t.service}
                    </td>
                    <td className="px-2 py-3">
                      <SeverityBadge severity={t.severity} />
                    </td>
                    <td className="px-2 py-3 text-[11px] text-slate-500 font-sans">
                      {t.jira_ticket_status_updated_at
                        ? new Date(t.jira_ticket_status_updated_at).toLocaleString()
                        : "—"}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <Link
                        href={`/incidents/${t.id}`}
                        className="text-[11px] font-bold text-brand-600 hover:underline font-sans"
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </PageShell>
  );
}
