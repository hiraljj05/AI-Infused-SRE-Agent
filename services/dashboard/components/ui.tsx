"use client";

import { type ReactNode } from "react";

export function Card({
  title,
  icon,
  rightSlot,
  children,
  className = "",
  bodyClassName = "",
}: {
  title?: ReactNode;
  icon?: ReactNode;
  rightSlot?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <div
      className={`flex min-h-0 flex-col rounded-[10px] border border-[var(--n7)] bg-white px-3.5 py-3 shadow-[var(--shadow-sm)] ${className}`}
    >
      {(title || rightSlot) && (
        <div className="mb-2.5 flex flex-shrink-0 items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-[12px] font-bold text-[var(--n1)]">
            {icon && (
              <span className="flex h-5 w-5 items-center justify-center rounded-md bg-[var(--primary-light)] text-[11px]">
                {icon}
              </span>
            )}
            {title}
          </div>
          {rightSlot}
        </div>
      )}
      <div className={`flex min-h-0 flex-1 flex-col ${bodyClassName}`}>{children}</div>
    </div>
  );
}

export type KpiAccent =
  | "primary"
  | "success"
  | "warning"
  | "danger"
  | "cyan"
  | "pink"
  | "neutral";

const ACCENT_BAR: Record<KpiAccent, string> = {
  primary: "bg-[var(--primary)]",
  success: "bg-[var(--success)]",
  warning: "bg-[var(--warning)]",
  danger: "bg-[var(--error)]",
  cyan: "bg-[var(--cyan)]",
  pink: "bg-[var(--pink)]",
  neutral: "bg-[var(--n5)]",
};

const ACCENT_TEXT: Record<KpiAccent, string> = {
  primary: "text-[var(--primary)]",
  success: "text-[var(--success)]",
  warning: "text-[var(--warning)]",
  danger: "text-[var(--error)]",
  cyan: "text-[#0E8A7F]",
  pink: "text-[var(--pink)]",
  neutral: "text-[var(--n0)]",
};

export function Kpi({
  label,
  value,
  accent = "primary",
  delta,
  deltaDir,
  hint,
}: {
  label: string;
  value: ReactNode;
  accent?: KpiAccent;
  delta?: string;
  deltaDir?: "up" | "down";
  hint?: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-[10px] border border-[var(--n7)] bg-white px-3 py-2.5">
      <div className={`absolute inset-x-0 top-0 h-0.5 ${ACCENT_BAR[accent]}`} />
      <div className="mb-1 text-[9.5px] font-semibold uppercase tracking-wide text-[var(--n4)]">
        {label}
      </div>
      <div className={`text-[22px] font-extrabold leading-none ${ACCENT_TEXT[accent]}`}>
        {value}
      </div>
      {delta && (
        <div
          className={`mt-1 text-[10px] font-semibold ${
            deltaDir === "down" ? "text-[var(--error)]" : "text-[var(--success)]"
          }`}
        >
          {deltaDir === "down" ? "▲" : "▼"} {delta}
        </div>
      )}
      {hint && <div className="mt-0.5 text-[9px] text-[var(--n5)]">{hint}</div>}
    </div>
  );
}

export function Hero({
  variant,
  icon,
  title,
  sub,
  stats,
}: {
  variant: "lead" | "exec";
  icon: string;
  title: string;
  sub: string;
  stats: { value: string; label: string; tone?: "ok" | "danger" | "neutral" }[];
}) {
  const bg =
    variant === "exec"
      ? "linear-gradient(135deg,#0E2E89 0%,#5929d0 50%,#CF008B 100%)"
      : "linear-gradient(90deg,#A855F7 0%,#6B8EF0 50%,#01CAB8 100%)";

  return (
    <div
      className="mb-2.5 flex flex-shrink-0 items-center justify-between gap-3.5 rounded-xl px-4 py-2.5 text-white"
      style={{ background: bg }}
    >
      <div className="flex min-w-0 items-center gap-2.5">
        <div className="flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-[10px] border border-white/30 bg-white/20 text-base">
          {icon}
        </div>
        <div className="min-w-0">
          <div className="text-[12.5px] font-bold text-white">{title}</div>
          <div className="mt-px text-[10.5px] text-white/80">{sub}</div>
        </div>
      </div>
      <div className="flex flex-shrink-0 gap-5">
        {stats.map((s, i) => (
          <div key={i} className="text-center">
            <div
              className={`text-[16px] font-extrabold leading-none ${
                s.tone === "danger"
                  ? "text-[#FCA5A5]"
                  : s.tone === "ok"
                  ? "text-[#86EFAC]"
                  : "text-white"
              }`}
            >
              {s.value}
            </div>
            <div className="mt-0.5 text-[9px] uppercase tracking-wider text-white/75">
              {s.label}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function LayerTab({
  active,
  icon,
  name,
  sub,
  mini,
  iconBg,
  onClick,
}: {
  active: boolean;
  icon: string;
  name: string;
  sub: string;
  mini?: { label: string; value: string }[];
  iconBg: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex flex-1 items-center gap-2 rounded-md p-1.5 text-left transition ${
        active
          ? "bg-gradient-to-br from-[var(--primary-light)] to-[var(--cyan-light)]"
          : "hover:bg-[var(--n8)]"
      }`}
    >
      <div
        className="flex h-[30px] w-[30px] flex-shrink-0 items-center justify-center rounded-md text-[14px] text-white"
        style={{ background: iconBg }}
      >
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <div
          className={`text-[11.5px] font-bold leading-tight ${
            active ? "text-[var(--primary)]" : "text-[var(--n1)]"
          }`}
        >
          {name}
        </div>
        <div className="mt-0.5 text-[9.5px] text-[var(--n4)]">{sub}</div>
      </div>
      {mini && (
        <div className="flex flex-shrink-0 gap-1.5 text-[9.5px] font-semibold text-[var(--n4)]">
          {mini.map((m, i) => (
            <span key={i}>
              {m.label} <b className="text-[var(--n1)]">{m.value}</b>
            </span>
          ))}
        </div>
      )}
    </button>
  );
}

export function PageHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-3">
      <h2 className="text-[15px] font-bold text-[var(--n0)]">{title}</h2>
      {sub && <p className="mt-0.5 text-[11px] text-[var(--n4)]">{sub}</p>}
    </div>
  );
}
