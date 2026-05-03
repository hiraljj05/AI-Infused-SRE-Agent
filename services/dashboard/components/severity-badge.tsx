import clsx from "clsx";
import type { Severity } from "@/lib/api";

const SEV_CLASS: Record<string, string> = {
  P1: "bg-red-100 text-red-600 border-red-300",
  P2: "bg-orange-100 text-orange-700 border-orange-300",
  P3: "bg-yellow-100 text-yellow-700 border-yellow-300",
  P4: "bg-blue-100 text-blue-700 border-blue-300",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  const key = severity || "P4";
  return (
    <span
      className={clsx(
        "inline-block rounded border px-2 py-0.5 text-xs font-semibold",
        SEV_CLASS[key] || "bg-slate-600/20 text-slate-700 border-slate-300"
      )}
    >
      {severity || "pending"}
    </span>
  );
}
