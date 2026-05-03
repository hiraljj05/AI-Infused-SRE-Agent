"use client";

import useSWR from "swr";
import { api, type LogsResponse } from "@/lib/api";

const LEVEL_CLASS: Record<string, string> = {
  DEBUG: "text-slate-500",
  INFO: "text-slate-700",
  WARN: "text-amber-600",
  ERROR: "text-red-600",
  FATAL: "text-red-600 font-semibold",
};

export type LogViewerProps = {
  service?: string;
  logql?: string;
  minutes?: number;
  level?: string;
  limit?: number;
  refreshMs?: number;
  emptyMessage?: string;
  height?: string; // tailwind class e.g. "h-80"
};

export function LogViewer({
  service,
  logql,
  minutes = 15,
  level = "DEBUG",
  limit = 200,
  refreshMs = 5000,
  emptyMessage = "No log lines in this window.",
  height = "h-96",
}: LogViewerProps) {
  const key = `/api/logs?service=${service || ""}&logql=${logql || ""}&minutes=${minutes}&level=${level}&limit=${limit}`;
  const { data, error, isLoading } = useSWR<LogsResponse>(
    key,
    () => api.queryLogs({ service, logql, minutes, level, limit }),
    { refreshInterval: refreshMs }
  );

  return (
    <div className={`overflow-y-auto rounded-lg border border-slate-200 bg-slate-100 ${height}`}>
      {isLoading && <div className="p-3 text-xs text-slate-500">Loading logs...</div>}
      {error && (
        <div className="p-3 text-xs text-red-600">Failed to load logs: {String(error.message)}</div>
      )}
      {!isLoading && !error && data && data.lines.length === 0 && (
        <div className="p-3 text-xs text-slate-500">{emptyMessage}</div>
      )}
      {data && data.lines.length > 0 && (
        <table className="w-full font-mono text-xs">
          <tbody>
            {data.lines.map((ln, i) => {
              const t = new Date(ln.timestamp);
              const ts = `${t.getHours().toString().padStart(2, "0")}:${t
                .getMinutes()
                .toString()
                .padStart(2, "0")}:${t.getSeconds().toString().padStart(2, "0")}`;
              return (
                <tr key={i} className="border-b border-slate-200/40 hover:bg-white">
                  <td className="whitespace-nowrap px-2 py-1 text-slate-500">{ts}</td>
                  <td className="px-2 py-1">
                    <span className={LEVEL_CLASS[ln.level] || "text-slate-700"}>
                      {ln.level.padEnd(5, " ")}
                    </span>
                  </td>
                  <td className="px-2 py-1 text-slate-500">{ln.source}</td>
                  <td className="break-all px-2 py-1 text-slate-800">{ln.message}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
