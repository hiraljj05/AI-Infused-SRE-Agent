"use client";

import { type ReactNode } from "react";
import { Topbar } from "@/components/topbar";

export function PageShell({
  title,
  sub,
  right,
  children,
  bare = false,
}: {
  title: string;
  sub?: string;
  right?: ReactNode;
  children: ReactNode;
  bare?: boolean;
}) {
  return (
    <>
      <Topbar pageTitle={title} pageSub={sub} right={right} />
      <div
        className={
          bare
            ? "flex-1 overflow-y-auto"
            : "flex-1 overflow-y-auto px-6 py-6"
        }
      >
        {children}
      </div>
    </>
  );
}
