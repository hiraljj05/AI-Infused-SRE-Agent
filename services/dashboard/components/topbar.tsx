"use client";

import { useEffect, useState } from "react";

export function Topbar({
  pageTitle,
  pageSub,
  right,
}: {
  pageTitle?: string;
  pageSub?: string;
  right?: React.ReactNode;
}) {
  const [now, setNow] = useState<string>("");

  useEffect(() => {
    function tick() {
      const n = new Date();
      const day = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][n.getDay()];
      const month = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
      ][n.getMonth()];
      const h = n.getHours() % 12 || 12;
      const ap = n.getHours() >= 12 ? "PM" : "AM";
      setNow(
        `${day}, ${String(n.getDate()).padStart(2, "0")} ${month} ${n.getFullYear()} · ${String(h).padStart(2, "0")}:${String(n.getMinutes()).padStart(2, "0")} ${ap}`
      );
    }
    tick();
    const id = setInterval(tick, 30000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="sticky top-0 z-30 flex h-[60px] flex-shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-6">




      <div className="flex flex-shrink-0 items-center gap-3">
        {right}
        <div className="flex items-center gap-1.5 rounded-full border border-emerald-200/50 bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-600">
          <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-emerald-500" />
          LIVE
        </div>
        <div className="hidden rounded-full bg-slate-100 px-3 py-1 text-[11px] font-medium text-slate-600 md:block">
          {now}
        </div>
      </div>
    </div>
  );
}
