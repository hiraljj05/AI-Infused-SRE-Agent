"use client";

import { useState } from "react";
import { LogViewer } from "@/components/log-viewer";
import { PageShell } from "@/components/page-shell";

// Services we actually run + ship logs for from Promtail.
// Postgres is Azure-managed (logs in Azure Monitor, not Loki). Redis is unused.
const SERVICES = [
  "agent",
  "dashboard",
  "chaos-ui",
  "food-orders",
  "portfolio-web",
  "prometheus",
  "grafana",
  "loki",
  "promtail",
  "qdrant",
];

const LEVELS = ["DEBUG", "INFO", "WARN", "ERROR"];

export default function LogsPage() {
  const [service, setService] = useState<string>("agent");
  const [minutes, setMinutes] = useState(15);
  const [level, setLevel] = useState("DEBUG");
  const [logql, setLogql] = useState("");

  return (
    <PageShell title="Logs" sub="Live container logs streamed from Loki via Promtail">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-3 card p-4">
          <select
            className="select w-[160px]"
            value={service}
            onChange={(e) => setService(e.target.value)}
            disabled={!!logql}
          >
            {SERVICES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>

          <select
            className="select w-[140px]"
            value={minutes}
            onChange={(e) => setMinutes(Number(e.target.value))}
          >
            <option value={5}>last 5 min</option>
            <option value={15}>last 15 min</option>
            <option value={60}>last 1 h</option>
            <option value={360}>last 6 h</option>
            <option value={1440}>last 24 h</option>
          </select>

          <select
            className="select w-[140px]"
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            disabled={!!logql}
          >
            {LEVELS.map((l) => (
              <option key={l} value={l}>
                level ≥ {l}
              </option>
            ))}
          </select>

          <input
            className="input flex-1 min-w-[260px] font-mono text-[12px]"
            placeholder='LogQL (overrides selectors): {app="agent"} |= "error"'
            value={logql}
            onChange={(e) => setLogql(e.target.value)}
          />
        </div>

        <div className="card overflow-hidden">
          <LogViewer
            service={logql ? undefined : service}
            logql={logql || undefined}
            minutes={minutes}
            level={level}
            limit={500}
            height="h-[70vh]"
          />
        </div>
      </div>
    </PageShell>
  );
}