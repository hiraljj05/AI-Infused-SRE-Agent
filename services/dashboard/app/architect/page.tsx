"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Cloud,
  Compass,
  Download,
  FileText,
  Layers,
  Loader2,
  Sparkles,
  Wand2,
} from "lucide-react";
import { api, type AdvisorRequest, type AdvisorResponse } from "@/lib/api";
import { PageShell } from "@/components/page-shell";

const COMPLIANCE_OPTIONS = ["HIPAA", "PCI-DSS", "SOC2", "GDPR", "ISO27001", "FedRAMP"];

const CLOUDS: { id: AdvisorRequest["cloud"]; label: string }[] = [
  { id: "azure", label: "Azure" },
  { id: "aws", label: "AWS" },
  { id: "gcp", label: "GCP" },
  { id: "on-prem", label: "On-prem" },
  { id: "multi", label: "Multi-cloud" },
];

const WORKLOADS: { id: AdvisorRequest["workload_type"]; label: string }[] = [
  { id: "web", label: "Web app" },
  { id: "api", label: "REST/GraphQL API" },
  { id: "batch", label: "Batch jobs" },
  { id: "ml", label: "ML inference" },
  { id: "data-pipeline", label: "Data pipeline" },
  { id: "iot", label: "IoT ingest" },
  { id: "other", label: "Other" },
];

const SCALES: { id: AdvisorRequest["scale"]; label: string; sub: string }[] = [
  { id: "startup", label: "Startup", sub: "~10s of users" },
  { id: "growth", label: "Growth", sub: "~1k users" },
  { id: "enterprise", label: "Enterprise", sub: "100k+ users" },
];

export default function ArchitectPage() {
  const [cloud, setCloud] = useState<AdvisorRequest["cloud"]>("azure");
  const [workload, setWorkload] =
    useState<AdvisorRequest["workload_type"]>("web");
  const [scale, setScale] = useState<AdvisorRequest["scale"]>("startup");
  const [compliance, setCompliance] = useState<string[]>([]);
  const [latency, setLatency] = useState(200);
  const [extra, setExtra] = useState("");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AdvisorResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function toggleCompliance(c: string) {
    setCompliance((p) => (p.includes(c) ? p.filter((x) => x !== c) : [...p, c]));
  }

  async function submit() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.advise({
        cloud,
        workload_type: workload,
        scale,
        compliance,
        latency_target_ms: latency,
        extra_context: extra,
      });
      setResult(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function downloadMarkdown() {
    if (!result) return;
    const blob = new Blob([result.recommendation_markdown], {
      type: "text/markdown",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `architect-${cloud}-${workload}-${scale}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <PageShell
      title="Advisor"
      sub="Production-ready stack & SRE-readiness blueprints"
    >
      {/* Hero strip ------------------------------------------------- */}
      <div
        className="mb-5 flex flex-wrap items-center justify-between gap-4 rounded-2xl px-6 py-5 text-slate-900 section-desc"
        style={{ background: "var(--gradient-banner)" }}
      >
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900/10 backdrop-blur">
            <Compass size={20} />
          </div>
          <div>
            <div className="text-[15px] font-bold leading-tight font-sans">
              Tell me about a new project
            </div>
            <div className="mt-0.5 max-w-2xl text-[12.5px] text-slate-700 font-sans">
              I&apos;ll design a stack, pick services and produce an
              SRE-readiness checklist tailored to your scale, compliance and
              latency targets.
            </div>
          </div>
        </div>
        <div className="hidden items-center gap-1.5 rounded-full bg-slate-900/10 px-3 py-1 text-[11px] font-semibold text-slate-800 lg:flex font-sans">
          <Sparkles size={12} />
          Powered by your knowledge base
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[420px,1fr]">
        {/* ---------- Inputs ------------------------------------- */}
        <section className="card space-y-5 p-5">
          <Field label="Cloud" icon={<Cloud size={13} />}>
            <SegmentedRow
              value={cloud}
              onChange={(v) => setCloud(v as AdvisorRequest["cloud"])}
              options={CLOUDS}
            />
          </Field>

          <Field label="Workload type" icon={<Layers size={13} />}>
            <select
              className="select"
              value={workload}
              onChange={(e) =>
                setWorkload(e.target.value as AdvisorRequest["workload_type"])
              }
            >
              {WORKLOADS.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.label}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Scale">
            <div className="grid grid-cols-3 gap-2">
              {SCALES.map((s) => {
                const active = scale === s.id;
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setScale(s.id)}
                    className={`rounded-lg border px-2 py-2 text-left transition ${
                      active
                        ? "border-indigo-500 bg-indigo-50 text-indigo-700 shadow-sm"
                        : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                    }`}
                  >
                    <div className="text-[12.5px] font-semibold">{s.label}</div>
                    <div className="text-[10.5px] text-slate-500">{s.sub}</div>
                  </button>
                );
              })}
            </div>
          </Field>

          <Field label="Compliance">
            <div className="flex flex-wrap gap-1.5">
              {COMPLIANCE_OPTIONS.map((c) => {
                const on = compliance.includes(c);
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => toggleCompliance(c)}
                    className={`rounded-full px-2.5 py-1 text-[11.5px] font-semibold transition ring-1 ${
                      on
                        ? "bg-indigo-600 text-white ring-indigo-600"
                        : "bg-white text-slate-600 ring-slate-200 hover:ring-slate-300"
                    }`}
                  >
                    {c}
                  </button>
                );
              })}
            </div>
          </Field>

          <Field label={`Latency target (p99): ${latency} ms`}>
            <input
              type="range"
              min={50}
              max={2000}
              step={50}
              value={latency}
              onChange={(e) => setLatency(Number(e.target.value))}
              className="w-full accent-indigo-600"
            />
            <div className="mt-1 flex justify-between text-[10px] text-slate-400">
              <span>50 ms</span>
              <span>1 s</span>
              <span>2 s</span>
            </div>
          </Field>

          <Field label="Extra context (optional)">
            <textarea
              className="input"
              rows={3}
              placeholder="e.g. B2B invoicing SaaS, PII data, scaling 50→500 customers"
              value={extra}
              onChange={(e) => setExtra(e.target.value)}
            />
          </Field>

          <button
            className="btn-primary w-full"
            onClick={submit}
            disabled={loading}
          >
            {loading ? (
              <>
                <Loader2 size={14} className="animate-spin" /> Designing…
              </>
            ) : (
              <>
                <Wand2 size={14} />
                Generate blueprint
              </>
            )}
          </button>

          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[12px] text-rose-700">
              {error}
            </div>
          )}
        </section>

        {/* ---------- Result ------------------------------------- */}
        <section className="card flex min-h-[480px] flex-col overflow-hidden">
          {/* Result header */}
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
            <div className="flex items-center gap-2">
              <FileText size={14} className="text-indigo-500" />
              <span className="text-[13px] font-semibold text-slate-800">
                Blueprint
              </span>
              {result && (
                <span className="text-[11px] text-slate-500">
                  · model{" "}
                  <span className="text-mono">
                    {result.model.split("/").pop()}
                  </span>{" "}
                  · cited {result.cited_docs.length}
                </span>
              )}
            </div>
            {result && (
              <button onClick={downloadMarkdown} className="btn-ghost">
                <Download size={13} />
                <span className="hidden sm:inline">Markdown</span>
              </button>
            )}
          </div>

          {/* Body */}
          <div className="scrollbar-thin flex-1 overflow-y-auto px-6 py-5">
            {!result && !loading && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <div
                  className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl text-white"
                  style={{ background: "var(--grad-brand)" }}
                >
                  <Compass size={22} />
                </div>
                <div className="text-[14px] font-semibold text-slate-700">
                  Ready when you are
                </div>
                <div className="mt-1 max-w-sm text-[12px] text-slate-500">
                  Pick a cloud, scale and constraints. Architect will return a
                  reference architecture, recommended services and an
                  SRE-readiness checklist.
                </div>
              </div>
            )}

            {loading && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <Loader2 size={22} className="mb-3 animate-spin text-indigo-500" />
                <div className="text-[13px] font-semibold text-slate-700">
                  Designing your stack…
                </div>
                <div className="mt-1 text-[12px] text-slate-500">
                  This usually takes 10–30 seconds.
                </div>
              </div>
            )}

            {result && (
              <div className="markdown-body prose prose-sm max-w-none text-slate-800">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {result.recommendation_markdown}
                </ReactMarkdown>

                {result.cited_docs.length > 0 && (
                  <div className="mt-6 border-t border-slate-200 pt-3">
                    <div className="section-h mb-1.5">Cited documents</div>
                    <div className="flex flex-wrap gap-1.5">
                      {result.cited_docs.map((id) => (
                        <span
                          key={id}
                          className="text-mono rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-700"
                        >
                          {id}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      </div>
    </PageShell>
  );
}

function Field({
  label,
  icon,
  children,
}: {
  label: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-1.5 flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-wider text-slate-500">
        {icon}
        {label}
      </div>
      {children}
    </label>
  );
}

function SegmentedRow<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { id: T; label: string }[];
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => {
        const active = o.id === value;
        return (
          <button
            key={o.id}
            type="button"
            onClick={() => onChange(o.id)}
            className={`rounded-lg px-3 py-1.5 text-[12px] font-semibold transition ring-1 ${
              active
                ? "bg-indigo-600 text-white ring-indigo-600 shadow-sm"
                : "bg-white text-slate-600 ring-slate-200 hover:ring-slate-300"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
