import clsx from "clsx";

const STATUS_CLASS: Record<string, string> = {
  "to do": "bg-slate-100 text-slate-700 border-slate-300",
  "open": "bg-slate-100 text-slate-700 border-slate-300",
  "backlog": "bg-slate-100 text-slate-700 border-slate-300",
  "in progress": "bg-blue-100 text-blue-700 border-blue-300",
  "in review": "bg-purple-100 text-purple-700 border-purple-300",
  "blocked": "bg-rose-100 text-rose-700 border-rose-300",
  "done": "bg-emerald-100 text-emerald-700 border-emerald-300",
  "resolved": "bg-emerald-100 text-emerald-700 border-emerald-300",
  "closed": "bg-emerald-100 text-emerald-700 border-emerald-300",
  "cancelled": "bg-zinc-200 text-zinc-700 border-zinc-300",
  "won't do": "bg-zinc-200 text-zinc-700 border-zinc-300",
};

export function JiraStatusBadge({
  status,
  updatedAt,
  className,
}: {
  status: string | null;
  updatedAt?: string | null;
  className?: string;
}) {
  if (!status) return null;
  const cls = STATUS_CLASS[status.toLowerCase()] || "bg-slate-100 text-slate-700 border-slate-300";
  const tooltip = updatedAt ? `Refreshed ${new Date(updatedAt).toLocaleString()}` : "Live from Jira";
  return (
    <span
      title={tooltip}
      className={clsx(
        "inline-block rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        cls,
        className,
      )}
    >
      {status}
    </span>
  );
}
