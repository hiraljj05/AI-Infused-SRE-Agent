"use client";

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  ScatterChart,
  Scatter,
  ZAxis,
} from "recharts";
import { IncidentView, PostmortemView } from "@/lib/api";

const COLORS = ["#A855F7", "#01CAB8", "#f59e0b", "#f43f5e", "#6B8EF0"];

export function IncidentVolumeChart({ incidents }: { incidents: IncidentView[] }) {
  const data = useMemo(() => {
    const counts: Record<string, number> = {};
    const now = new Date();
    for (let i = 6; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      counts[d.toLocaleDateString("en-US", { month: "short", day: "numeric" })] = 0;
    }

    incidents.forEach((i) => {
      const d = new Date(i.detected_at).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      });
      if (counts[d] !== undefined) {
        counts[d]++;
      }
    });

    return Object.entries(counts).map(([date, count]) => ({ date, count }));
  }, [incidents]);

  return (
    <div className="card flex h-full flex-col p-4">
      <div className="mb-4 text-sm font-semibold text-slate-900">Incident Volume (Last 7 Days)</div>
      <div className="flex-1 min-h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
            <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#64748b" }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#64748b" }} allowDecimals={false} />
            <Tooltip
              cursor={{ fill: "#f8fafc" }}
              contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
            />
            <Bar dataKey="count" fill="#A855F7" radius={[4, 4, 0, 0]} maxBarSize={40} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function IncidentStatusPie({ incidents }: { incidents: IncidentView[] }) {
  const data = useMemo(() => {
    const counts: Record<string, number> = {};
    incidents.forEach((i) => {
      const s = i.status.replace("_", " ");
      counts[s] = (counts[s] || 0) + 1;
    });
    return Object.entries(counts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [incidents]);

  return (
    <div className="card flex h-full flex-col p-4">
      <div className="mb-4 text-sm font-semibold text-slate-900">Status Distribution</div>
      <div className="flex-1 min-h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={80}
              paddingAngle={2}
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex flex-wrap justify-center gap-3">
        {data.map((d, i) => (
          <div key={d.name} className="flex items-center gap-1.5 text-[11px] text-slate-600">
            <div className="h-2 w-2 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
            <span className="capitalize">{d.name}</span> ({d.value})
          </div>
        ))}
      </div>
    </div>
  );
}

export function TicketStatusChart({ tickets }: { tickets: IncidentView[] }) {
  const data = useMemo(() => {
    const counts: Record<string, number> = {
      "To Do": 0,
      "In Progress": 0,
      "Review": 0,
      "Done": 0,
    };
    tickets.forEach((t) => {
      const s = (t.jira_ticket_status || "").toLowerCase();
      if (["done", "resolved", "closed"].includes(s)) counts["Done"]++;
      else if (["in progress", "in-progress", "executing"].includes(s)) counts["In Progress"]++;
      else if (["in review", "review", "blocked"].includes(s)) counts["Review"]++;
      else counts["To Do"]++;
    });
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [tickets]);

  return (
    <div className="card flex h-[260px] flex-col p-4">
      <div className="mb-4 text-sm font-semibold text-slate-900">Jira Ticket Status</div>
      <div className="flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
            <XAxis type="number" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#64748b" }} allowDecimals={false} />
            <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#64748b" }} width={80} />
            <Tooltip
              cursor={{ fill: "#f8fafc" }}
              contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
            />
            <Bar dataKey="value" fill="#01CAB8" radius={[0, 4, 4, 0]} barSize={24} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function MTTRChart({ postmortems }: { postmortems: PostmortemView[] }) {
  const data = useMemo(() => {
    return [...postmortems]
      .reverse() // Oldest first
      .filter((p) => p.detected_at && p.resolved_at)
      .map((p) => {
        const mttr = Math.round(
          (new Date(p.resolved_at!).getTime() - new Date(p.detected_at!).getTime()) / 60000
        );
        return {
          id: p.id.split("-")[1],
          mttr,
          date: new Date(p.drafted_at).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
        };
      });
  }, [postmortems]);

  return (
    <div className="card flex h-[260px] flex-col p-4">
      <div className="mb-4 text-sm font-semibold text-slate-900">MTTR Trend (Minutes)</div>
      <div className="flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
            <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#64748b" }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#64748b" }} />
            <Tooltip
              contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
            />
            <Line type="monotone" dataKey="mttr" stroke="#6B8EF0" strokeWidth={3} dot={{ r: 4, fill: "#6B8EF0", strokeWidth: 2, stroke: "#fff" }} activeDot={{ r: 6 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function RCAConfidenceChart({ incidents }: { incidents: IncidentView[] }) {
  const data = useMemo(() => {
    return incidents
      .filter((i) => i.rca_hypotheses.length > 0)
      .map((i) => ({
        id: i.id.split("-")[1],
        confidence: Math.round(i.rca_hypotheses[0].confidence * 100),
        service: i.service,
      }));
  }, [incidents]);

  return (
    <div className="card flex h-[260px] flex-col p-4">
      <div className="mb-4 text-sm font-semibold text-slate-900">RCA Confidence Scores</div>
      <div className="flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
            <XAxis dataKey="id" name="Incident" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#64748b" }} />
            <YAxis dataKey="confidence" name="Confidence %" domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#64748b" }} />
            <ZAxis dataKey="service" name="Service" />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
            />
            <Scatter data={data} fill="#f59e0b" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function GrafanaLogsChart({ lines }: { lines: { timestamp: string; level: string }[] }) {
  const data = useMemo(() => {
    if (!lines || lines.length === 0) return [];
    
    // Group by minute
    const counts: Record<string, { time: string; error: number; warn: number; info: number }> = {};
    
    lines.forEach((ln) => {
      const d = new Date(ln.timestamp);
      // Format as HH:MM
      const time = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
      
      if (!counts[time]) {
        counts[time] = { time, error: 0, warn: 0, info: 0 };
      }
      
      const lvl = ln.level.toUpperCase();
      if (lvl === "ERROR" || lvl === "FATAL") counts[time].error++;
      else if (lvl === "WARN") counts[time].warn++;
      else counts[time].info++;
    });
    
    return Object.values(counts).sort((a, b) => a.time.localeCompare(b.time));
  }, [lines]);

  if (data.length === 0) {
    return (
      <div className="flex h-[180px] items-center justify-center text-xs text-slate-400">
        No log data available for chart.
      </div>
    );
  }

  return (
    <div className="h-[180px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
          <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: "#64748b" }} />
          <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: "#64748b" }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)", fontSize: "12px" }}
            cursor={{ fill: "#f8fafc" }}
          />
          <Bar dataKey="error" stackId="a" fill="#ef4444" name="Error/Fatal" />
          <Bar dataKey="warn" stackId="a" fill="#f59e0b" name="Warning" />
          <Bar dataKey="info" stackId="a" fill="#01CAB8" name="Info/Debug" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
