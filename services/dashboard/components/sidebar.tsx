"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Boxes,
  ClipboardList,
  Compass,
  DollarSign,
  FileSearch,
  GaugeCircle,
  Lightbulb,
  ListChecks,
  ScrollText,
  Sparkles,
  TestTube2,
  Ticket,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";

type NavItem = {
  to: string;
  label: string;
  Icon: typeof Zap;
  hint?: string;
};
type NavSection = { title: string; items: NavItem[] };

const NAV: NavSection[] = [
  {
    title: "Operations",
    items: [
      { to: "/", label: "Overview", Icon: Activity },
      { to: "/incidents", label: "Incidents", Icon: AlertTriangle },
      { to: "/tickets", label: "Jira Tickets", Icon: Ticket },
      { to: "/logs", label: "Logs", Icon: ScrollText },
      { to: "/apps", label: "Apps", Icon: Boxes },
    ],
  },
  {
    title: "Analysis",
    items: [
      { to: "/rca", label: "RCA Console", Icon: FileSearch },
      { to: "/postmortems", label: "Postmortems", Icon: ClipboardList },
      { to: "/knowledge", label: "Knowledge", Icon: Lightbulb },
      { to: "/architect", label: "Architect", Icon: Compass },
    ],
  },
  {
    title: "Governance",
    items: [
      { to: "/hil", label: "HIL Queue", Icon: ListChecks },
      { to: "/audit", label: "Audit Trail", Icon: GaugeCircle },
      { to: "/people", label: "People", Icon: Users },
      { to: "/reports", label: "Reports", Icon: BarChart3 },
      { to: "/cost", label: "Cost", Icon: DollarSign },
    ],
  },
  {
    title: "Lab",
    items: [
      { to: "/chaos", label: "Chaos Lab", Icon: TestTube2 },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-[220px] flex-shrink-0 flex-col overflow-hidden border-r border-slate-200 bg-white">
      {/* Brand ---------------------------------------------------------- */}
      <div className="flex items-center gap-3 border-b border-slate-200 px-4 py-3.5">
        <div
          className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg text-white"
          style={{
            background: "linear-gradient(135deg, #5929d0, #CF008B)",
          }}
        >
          <span className="font-bold text-sm">C</span>
        </div>
        <div className="min-w-0">
          <h1 className="truncate text-[12.5px] font-bold leading-tight text-slate-900 font-sans">
            CentificAI
          </h1>
          <p className="text-[10px] text-slate-500 font-sans mt-0.5">SRE Agent</p>
        </div>
      </div>

      {/* Nav ----------------------------------------------------------- */}
      <nav className="scrollbar-thin flex-1 space-y-4 overflow-y-auto px-3 py-4">
        {NAV.map((sec) => (
          <div key={sec.title}>
            <div className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-[1.2px] text-slate-400 font-sans">
              {sec.title}
            </div>
            {sec.items.map(({ to, label, Icon }) => {
              const active =
                pathname === to ||
                (to !== "/" && pathname?.startsWith(to));
              return (
                <Link
                  key={to}
                  href={to}
                  className={`group relative flex items-center gap-3 rounded-lg px-3 py-2 text-[12.5px] transition-all duration-150 font-sans ${
                    active
                      ? "bg-brand-50 font-semibold text-brand-600"
                      : "text-slate-500 font-medium hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  {active && (
                    <span
                      aria-hidden
                      className="absolute -left-[3px] top-1/2 h-5 w-1 -translate-y-1/2 rounded-full"
                      style={{ background: "var(--grad-brand)" }}
                    />
                  )}
                  <Icon
                    size={16}
                    className={`flex-shrink-0 ${
                      active
                        ? "text-brand-600"
                        : "text-slate-400 group-hover:text-slate-600"
                    }`}
                  />
                  <span className="flex-1">{label}</span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer mini KPIs --------------------------------------------- */}
      <div className="border-t border-slate-200 px-4 py-3">
        <div className="flex items-center justify-between text-[11px] text-slate-500">
          <span className="flex items-center gap-1.5">
            <TrendingUp size={12} className="text-emerald-500" />
            <span className="font-mono">v0.9.0</span>
          </span>
          <span className="font-mono">AG-SRE-0426</span>
        </div>
      </div>
    </aside>
  );
}
