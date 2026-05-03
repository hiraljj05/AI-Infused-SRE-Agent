"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PageShell } from "@/components/page-shell";

type Project = {
  id: string;
  key: string;
  name: string;
};

type OwnerInput = { email: string; role: "primary" | "secondary" };

type OnboardResult = {
  app: { id: string; name: string; project_id: string; grafana_dashboard_uid: string | null };
  grafana_dashboard_uid: string | null;
  runbook_doc_id: string | null;
  warnings: string[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/agent";

export default function OnboardAppWizard() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OnboardResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // form state
  const [projectId, setProjectId] = useState("");
  const [name, setName] = useState("");
  const [namespace, setNamespace] = useState("demo-store");
  const [tier, setTier] = useState<"tier-0" | "tier-1" | "tier-2" | "tier-3">("tier-1");
  const [runbookTemplate, setRunbookTemplate] = useState("default-web-service");
  const [owners, setOwners] = useState<OwnerInput[]>([{ email: "", role: "primary" }]);

  useEffect(() => {
    fetch(`${API_BASE}/api/projects`)
      .then((r) => r.json())
      .then(setProjects)
      .catch(() => setProjects([]));
  }, []);

  function setOwner(i: number, patch: Partial<OwnerInput>) {
    setOwners((prev) => prev.map((o, idx) => (idx === i ? { ...o, ...patch } : o)));
  }

  function addOwner() {
    setOwners((prev) => [...prev, { email: "", role: "secondary" }]);
  }

  function removeOwner(i: number) {
    setOwners((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function submit() {
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const validOwners = owners.filter((o) => o.email.trim().length > 0);
      const r = await fetch(`${API_BASE}/api/apps/onboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          name,
          namespace,
          tier,
          runbook_template_id: runbookTemplate,
          owners: validOwners,
        }),
      });
      if (!r.ok) {
        const text = await r.text();
        throw new Error(`${r.status}: ${text}`);
      }
      const data: OnboardResult = await r.json();
      setResult(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    return (
    <PageShell title="Onboard App" sub="30-second wizard">
    <main className="mx-auto max-w-2xl space-y-6">
        <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-6">
          <div className="mb-2 text-2xl">✓</div>
          <h1 className="mb-2 text-lg font-semibold text-emerald-700">App registered</h1>
          <p className="text-sm text-slate-700">
            <span className="font-mono">{result.app.name}</span> is now under SRE Agent supervision.
          </p>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
          <div className="mb-3 font-semibold">What was set up</div>
          <ul className="space-y-2 text-slate-700">
            <li>
              <span className="text-slate-500">App ID:</span>{" "}
              <span className="font-mono text-xs">{result.app.id}</span>
            </li>
            {result.grafana_dashboard_uid && (
              <li>
                <span className="text-slate-500">Grafana dashboard:</span>{" "}
                <a
                  href={`http://localhost:3001/d/${result.grafana_dashboard_uid}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-indigo-600 underline hover:text-indigo-700"
                >
                  Open dashboard ↗
                </a>
              </li>
            )}
            {result.runbook_doc_id && (
              <li>
                <span className="text-slate-500">Runbook stub:</span>{" "}
                <span className="font-mono text-xs">{result.runbook_doc_id}</span>{" "}
                <span className="text-slate-500">(indexed in knowledge base)</span>
              </li>
            )}
          </ul>
          {result.warnings.length > 0 && (
            <div className="mt-4 rounded border border-amber-300 bg-amber-50 p-3 text-amber-600">
              <div className="mb-1 font-semibold">Warnings</div>
              <ul className="list-disc pl-5 text-xs">
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="flex gap-3">
          <button
            className="rounded bg-slate-100 px-4 py-2 text-sm hover:bg-slate-700"
            onClick={() => {
              setResult(null);
              setName("");
              setOwners([{ email: "", role: "primary" }]);
            }}
          >
            Onboard another
          </button>
          <button
            className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500"
            onClick={() => router.push("/")}
          >
            Back to dashboard
          </button>
        </div>
      </main>
    </PageShell>
  );
}
  return (
    <main className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Add Application</h1>
        <p className="mt-1 text-sm text-slate-500">
          Register an application with the SRE Agent. Takes ~30 seconds.
        </p>
      </div>

      <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-5">
        <Field label="Project" hint="Which team/project owns this app?">
          <select
            className="w-full rounded border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-500"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          >
            <option value="">Select a project</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.key})
              </option>
            ))}
          </select>
          {projects.length === 0 && (
            <p className="mt-1 text-xs text-amber-600">
              No projects yet. Create one via the API: POST /api/projects
            </p>
          )}
        </Field>

        <Field label="App name" hint="DNS-label format: lowercase, digits, hyphens">
          <input
            className="w-full rounded border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-500"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="payments-api"
          />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Namespace">
            <input
              className="w-full rounded border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-500"
              value={namespace}
              onChange={(e) => setNamespace(e.target.value)}
            />
          </Field>
          <Field label="Service tier">
            <select
              className="w-full rounded border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-500"
              value={tier}
              onChange={(e) => setTier(e.target.value as typeof tier)}
            >
              <option value="tier-0">tier-0 (most critical)</option>
              <option value="tier-1">tier-1</option>
              <option value="tier-2">tier-2</option>
              <option value="tier-3">tier-3 (least critical)</option>
            </select>
          </Field>
        </div>

        <Field label="Runbook template">
          <select
            className="w-full rounded border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-500"
            value={runbookTemplate}
            onChange={(e) => setRunbookTemplate(e.target.value)}
          >
            <option value="default-web-service">default-web-service</option>
            <option value="background-worker">background-worker</option>
            <option value="database">database</option>
            <option value="ml-inference">ml-inference</option>
          </select>
        </Field>

        <div>
          <div className="mb-2 text-sm font-medium">Owners</div>
          {owners.map((o, i) => (
            <div key={i} className="mb-2 flex gap-2">
              <input
                className="flex-1 rounded border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-500"
                placeholder="user@example.com"
                value={o.email}
                onChange={(e) => setOwner(i, { email: e.target.value })}
              />
              <select
                className="w-32 rounded border border-slate-200 bg-white px-2 py-2 text-sm"
                value={o.role}
                onChange={(e) => setOwner(i, { role: e.target.value as OwnerInput["role"] })}
              >
                <option value="primary">primary</option>
                <option value="secondary">secondary</option>
              </select>
              {owners.length > 1 && (
                <button
                  className="rounded border border-slate-200 px-2 text-slate-500 hover:bg-slate-100"
                  onClick={() => removeOwner(i)}
                >
                  ×
                </button>
              )}
            </div>
          ))}
          <button
            className="mt-1 text-xs text-indigo-400 hover:text-indigo-600"
            onClick={addOwner}
          >
            + Add owner
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-red-300 bg-red-100 p-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <div className="flex justify-end gap-3">
        <button
          className="rounded bg-slate-100 px-4 py-2 text-sm hover:bg-slate-700"
          onClick={() => router.push("/")}
        >
          Cancel
        </button>
        <button
          className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50"
          onClick={submit}
          disabled={loading || !projectId || !name.trim()}
        >
          {loading ? "Onboarding..." : "Register app"}
        </button>
      </div>
    </main>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-1 text-sm font-medium">{label}</div>
      {children}
      {hint && <div className="mt-0.5 text-xs text-slate-500">{hint}</div>}
    </label>
  );
}