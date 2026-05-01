"use client";

/**
 * /ingest — admin page for uploading a PDF and watching the V2 pipeline
 * stream stage events in real time.
 *
 * Per spec docs/superpowers/specs/2026-05-04-admin-upload.md.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  CheckCircle,
  CloudArrowUp,
  Spinner,
  Warning,
  XCircle,
} from "@phosphor-icons/react";
import { z } from "zod";

const STAGE_LABELS: Record<string, string> = {
  extract: "1. Extract paragraphs (PyMuPDF + OCR)",
  pre_structure: "2. Pre-structure draft chapters",
  decompose: "4. Decompose (Gemma Proposer + Critic)",
  validate: "5. Validate coverage",
  refine_titles: "6. Refine leaf titles",
  fill: "7. Fill content (verbatim source)",
  emit: "8. Emit skill folder",
};

const BrandingOptionSchema = z.object({
  key: z.string(),
  pattern_count: z.number(),
});

type StageState = "pending" | "running" | "complete" | "error";

interface StageRow {
  key: string;
  label: string;
  state: StageState;
  detail?: string;
}

interface PipelineResult {
  skill_folder: string;
  total_nodes: number;
  total_leaves: number;
  coverage: number;
  elapsed_seconds: number;
}

export default function IngestPage() {
  const [file, setFile] = useState<File | null>(null);
  const [bookSlug, setBookSlug] = useState("");
  const [bookName, setBookName] = useState("");
  const [subject, setSubject] = useState("geography");
  const [scope, setScope] = useState("rajasthan");
  const [examCoverage, setExamCoverage] = useState("ras_pre");
  const [publisher, setPublisher] = useState("");
  const [branding, setBranding] = useState<string>("");
  const [brandingOptions, setBrandingOptions] = useState<string[]>([]);

  const [phase, setPhase] = useState<"idle" | "uploading" | "running" | "complete" | "failed">(
    "idle",
  );
  const [stages, setStages] = useState<StageRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const dragRef = useRef<HTMLLabelElement | null>(null);

  useEffect(() => {
    fetch("/api/ingest/branding-options")
      .then((r) => r.json())
      .then((data) => {
        const parsed = z.array(BrandingOptionSchema).parse(data);
        setBrandingOptions(parsed.map((o) => o.key));
      })
      .catch(() => {
        // Branding options are optional — the UI degrades gracefully.
      });
  }, []);

  const initStages = () => {
    setStages(
      Object.entries(STAGE_LABELS).map(([key, label]) => ({
        key,
        label,
        state: key === "extract" ? "running" : "pending",
      })),
    );
  };

  const updateStage = (key: string, state: StageState, detail?: string) => {
    setStages((prev) =>
      prev.map((s) => (s.key === key ? { ...s, state, detail } : s)),
    );
  };

  const submit = async () => {
    if (!file || !bookSlug || !bookName) {
      setError("Pick a PDF and fill book slug + name first.");
      return;
    }
    setError(null);
    setResult(null);
    setPhase("uploading");
    initStages();

    const fd = new FormData();
    fd.append("file", file);
    fd.append("subject", subject);
    fd.append("book_slug", bookSlug);
    fd.append("book_name", bookName);
    fd.append("scope", scope);
    fd.append("exam_coverage", examCoverage);
    fd.append("publisher", publisher || "unknown");
    if (branding) fd.append("branding", branding);

    try {
      const resp = await fetch("/api/ingest", { method: "POST", body: fd });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail ?? `upload failed: ${resp.status}`);
      }
      const { job_id } = await resp.json();
      setJobId(job_id);
      setPhase("running");
      streamEvents(job_id);
    } catch (e) {
      setPhase("failed");
      setError((e as Error).message);
    }
  };

  const streamEvents = async (id: string) => {
    try {
      const resp = await fetch(`/api/ingest/${id}/events`);
      if (!resp.ok || !resp.body) {
        throw new Error(`stream failed: ${resp.status}`);
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const frame = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          if (!frame.startsWith("data: ")) continue;
          const payload = frame.slice(6).trim();
          if (!payload || payload === "[DONE]") continue;
          handleEvent(JSON.parse(payload));
        }
      }
    } catch (e) {
      setPhase("failed");
      setError((e as Error).message);
    }
  };

  const handleEvent = (ev: Record<string, unknown>) => {
    const eventName = String(ev.event ?? "");
    if (eventName === "stage_start" && ev.stage) {
      updateStage(String(ev.stage), "running");
    } else if (eventName === "stage_progress" && ev.stage) {
      updateStage(String(ev.stage), "running", String(ev.message ?? ""));
    } else if (eventName === "stage_complete" && ev.stage) {
      updateStage(String(ev.stage), "complete");
    } else if (eventName === "stage_error") {
      setPhase("failed");
      setError(String(ev.error ?? "pipeline error"));
    } else if (eventName === "pipeline_complete") {
      // Mark all stages complete.
      setStages((prev) => prev.map((s) => ({ ...s, state: "complete" })));
      setPhase("complete");
      setResult({
        skill_folder: String(ev.skill_folder),
        total_nodes: Number(ev.total_nodes),
        total_leaves: Number(ev.total_leaves),
        coverage: Number(ev.coverage),
        elapsed_seconds: Number(ev.elapsed_seconds),
      });
    }
  };

  const onDrop = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  };

  const onDragOver = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
  };

  const isRunning = phase === "running" || phase === "uploading";

  return (
    <main className="min-h-screen bg-slate-50 pb-16">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <Link href="/explorer" className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-zinc-950">
            <ArrowLeft size={12} /> Explorer
          </Link>
          <span className="text-xs text-slate-500">Admin · Ingest</span>
        </div>
      </header>

      <section className="mx-auto max-w-3xl px-6 pt-8">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-950">
          Ingest a textbook PDF
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Run the V2 pipeline (extract → OCR → decompose → validate → refine →
          fill → emit) end-to-end in the browser. Expect ~5–10 minutes per
          200-page book.
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          <label
            ref={dragRef}
            onDrop={onDrop}
            onDragOver={onDragOver}
            className="col-span-2 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-white px-6 py-10 text-center hover:border-indigo-400 hover:bg-indigo-50/30"
          >
            <CloudArrowUp size={28} className="text-slate-400" />
            <p className="mt-3 text-sm font-medium text-zinc-950">
              {file ? file.name : "Drop a PDF or .txt here, or click to browse"}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : "Up to 50 MB"}
            </p>
            <input
              type="file"
              accept=".pdf,.txt"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>

          <Field label="Book slug" hint="snake_case, used as folder name">
            <input
              value={bookSlug}
              onChange={(e) => setBookSlug(e.target.value)}
              placeholder="rbse_class11_geography"
              className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
            />
          </Field>

          <Field label="Book name" hint="human-readable">
            <input
              value={bookName}
              onChange={(e) => setBookName(e.target.value)}
              placeholder="RBSE Class 11 Geography"
              className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
            />
          </Field>

          <Field label="Subject">
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
            />
          </Field>

          <Field label="Scope">
            <select
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
            >
              <option value="rajasthan">rajasthan</option>
              <option value="pan_india">pan_india</option>
              <option value="world">world</option>
            </select>
          </Field>

          <Field label="Exam coverage" hint="comma-separated codes">
            <input
              value={examCoverage}
              onChange={(e) => setExamCoverage(e.target.value)}
              placeholder="ras_pre,patwari"
              className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
            />
          </Field>

          <Field label="Publisher">
            <input
              value={publisher}
              onChange={(e) => setPublisher(e.target.value)}
              placeholder="NCERT / RBSE / Springboard Academy"
              className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
            />
          </Field>

          <Field label="Branding bundle" hint="optional regex pack for known coaching sources">
            <select
              value={branding}
              onChange={(e) => setBranding(e.target.value)}
              className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
            >
              <option value="">(none)</option>
              {brandingOptions.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <button
          type="button"
          onClick={submit}
          disabled={isRunning}
          className="mt-6 inline-flex items-center gap-2 rounded-md bg-indigo-500 px-5 py-2 text-sm font-medium text-white transition hover:bg-indigo-600 disabled:opacity-50"
        >
          {isRunning ? (
            <Spinner size={14} className="animate-spin" />
          ) : null}
          {phase === "uploading"
            ? "Uploading…"
            : phase === "running"
              ? "Running pipeline…"
              : "Start ingestion"}
        </button>

        {error && (
          <div className="mt-4 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <Warning size={14} className="mt-0.5" />
            <span>{error}</span>
          </div>
        )}
      </section>

      {stages.length > 0 && (
        <section className="mx-auto mt-10 max-w-3xl px-6">
          <h2 className="text-sm font-semibold text-zinc-950">Pipeline stages</h2>
          <ol className="mt-3 space-y-2">
            {stages.map((s) => (
              <li
                key={s.key}
                className="flex items-center gap-3 rounded-md border border-slate-200 bg-white px-4 py-2.5 text-sm"
              >
                <StageIcon state={s.state} />
                <span className="flex-1 text-slate-800">{s.label}</span>
                {s.detail && (
                  <span className="text-xs text-slate-500">{s.detail}</span>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}

      {result && (
        <section className="mx-auto mt-10 max-w-3xl px-6">
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5">
            <h3 className="text-sm font-semibold text-emerald-900">
              Ingestion complete
            </h3>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-emerald-900">
              <dt className="text-emerald-700">skill folder</dt>
              <dd className="font-mono">{result.skill_folder}</dd>
              <dt className="text-emerald-700">nodes / leaves</dt>
              <dd>
                {result.total_nodes} / {result.total_leaves}
              </dd>
              <dt className="text-emerald-700">coverage</dt>
              <dd>{(result.coverage * 100).toFixed(1)}%</dd>
              <dt className="text-emerald-700">elapsed</dt>
              <dd>{result.elapsed_seconds.toFixed(1)}s</dd>
            </dl>
            <Link
              href="/explorer"
              className="mt-4 inline-block rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white"
            >
              View in Explorer
            </Link>
          </div>
        </section>
      )}

      {jobId && (
        <p className="mx-auto mt-3 max-w-3xl px-6 text-[10px] text-slate-400">
          job: <span className="font-mono">{jobId}</span>
        </p>
      )}
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
      <span className="text-xs font-medium text-slate-700">{label}</span>
      {hint && <span className="ml-1 text-xs text-slate-400">· {hint}</span>}
      <div className="mt-1">{children}</div>
    </label>
  );
}

function StageIcon({ state }: { state: StageState }) {
  if (state === "complete") return <CheckCircle size={16} className="text-emerald-500" />;
  if (state === "running") return <Spinner size={16} className="animate-spin text-indigo-500" />;
  if (state === "error") return <XCircle size={16} className="text-rose-500" />;
  return <span className="h-3.5 w-3.5 rounded-full border border-slate-300" />;
}
