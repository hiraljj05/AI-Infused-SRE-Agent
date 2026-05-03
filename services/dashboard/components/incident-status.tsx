import clsx from "clsx";

const STATUS_STYLES: Record<string, { label: string; cls: string; dot: string }> = {
  detected:          { label: "Detected",           cls: "bg-sky-50 text-sky-700 ring-sky-200",         dot: "bg-sky-500" },
  triaged:           { label: "Triaged",            cls: "bg-indigo-50 text-indigo-700 ring-indigo-200", dot: "bg-indigo-500" },
  diagnosing:        { label: "Diagnosing",         cls: "bg-violet-50 text-violet-700 ring-violet-200", dot: "bg-violet-500" },
  awaiting_approval: { label: "Awaiting approval",  cls: "bg-amber-50 text-amber-700 ring-amber-200",   dot: "bg-amber-500" },
  executing:         { label: "Executing",          cls: "bg-blue-50 text-blue-700 ring-blue-200",      dot: "bg-blue-500" },
  verifying:         { label: "Verifying",          cls: "bg-cyan-50 text-cyan-700 ring-cyan-200",      dot: "bg-cyan-500" },
  resolved:          { label: "Resolved",           cls: "bg-emerald-50 text-emerald-700 ring-emerald-200", dot: "bg-emerald-500" },
  escalated:         { label: "Escalated",          cls: "bg-orange-50 text-orange-700 ring-orange-200", dot: "bg-orange-500" },
  failed:            { label: "Failed",             cls: "bg-rose-50 text-rose-700 ring-rose-200",      dot: "bg-rose-500" },
};

export function IncidentStatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const key = status.toLowerCase();
  const meta =
    STATUS_STYLES[key] || {
      label: status,
      cls: "bg-slate-100 text-slate-700 ring-slate-200",
      dot: "bg-slate-500",
    };
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ring-1",
        meta.cls,
        className,
      )}
    >
      <span className={clsx("h-1.5 w-1.5 rounded-full", meta.dot)} />
      {meta.label}
    </span>
  );
}

export const ACTIVE_STATUSES = new Set([
  "detected",
  "triaged",
  "diagnosing",
  "awaiting_approval",
  "executing",
  "verifying",
]);

export const INCIDENT_STATUS_TABS = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "awaiting_approval", label: "Awaiting Approval" },
  { id: "executing", label: "Executing" },
  { id: "verifying", label: "Verifying" },
  { id: "resolved", label: "Resolved" },
  { id: "escalated", label: "Escalated" },
  { id: "failed", label: "Failed" },
] as const;

export type IncidentStatusTab = (typeof INCIDENT_STATUS_TABS)[number]["id"];
