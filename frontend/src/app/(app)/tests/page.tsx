"use client";

/**
 * /tests index — list past tests + [+ New test] modal.
 *
 * Per docs/research/2026-05-02-ux-redesign-architecture.md §2.3.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { z } from "zod";
import {
  ArrowRight,
  CheckCircle,
  Exam,
  MagnifyingGlass,
  Plus,
  Spinner,
  Warning,
  X,
} from "@phosphor-icons/react";

const TestSummarySchema = z.object({
  test_id: z.string(),
  node_id: z.string(),
  book_slug: z.string().nullable(),
  question_count: z.number(),
  generated_at: z.string(),
});
type TestSummary = z.infer<typeof TestSummarySchema>;

const LeafSchema = z.object({
  book_slug: z.string(),
  book_name: z.string(),
  node_id: z.string(),
  title: z.string(),
  path: z.string(),
});
type Leaf = z.infer<typeof LeafSchema>;

const PROXIED_TESTS_LIST = "/api/tests";

const TestsListSchema = z.array(TestSummarySchema);

export default function TestsIndex() {
  const router = useRouter();
  const [tests, setTests] = useState<TestSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);

  const loadTests = useCallback(async () => {
    try {
      const resp = await fetch(PROXIED_TESTS_LIST);
      if (!resp.ok) throw new Error(`status ${resp.status}`);
      const data = TestsListSchema.parse(await resp.json());
      setTests(data);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    loadTests();
  }, [loadTests]);

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-6">
        <h1 className="text-sm font-semibold text-zinc-950">Tests</h1>
        <button
          type="button"
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-1.5 rounded-md bg-indigo-500 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-indigo-600"
        >
          <Plus size={12} weight="bold" /> New test
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <Warning size={14} /> Failed to load tests: {error}
          </div>
        )}

        {tests.length === 0 ? (
          <EmptyState onNew={() => setShowModal(true)} />
        ) : (
          <ul className="space-y-2">
            {tests.map((t) => (
              <li
                key={t.test_id}
                className="group flex items-center gap-3 rounded-md border border-slate-200 bg-white px-4 py-3 transition hover:border-indigo-300"
              >
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-indigo-50 text-indigo-600">
                  <Exam size={14} weight="duotone" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-zinc-950">
                    {prettyNodeTitle(t.node_id)}
                  </p>
                  <p className="truncate text-[11px] text-slate-500">
                    {t.question_count} questions ·{" "}
                    {new Date(t.generated_at).toLocaleString()}
                    {t.book_slug ? ` · ${t.book_slug}` : ""}
                  </p>
                </div>
                <Link
                  href={`/tests/${t.test_id}`}
                  className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 hover:border-indigo-300 hover:text-zinc-950"
                >
                  Open
                </Link>
                <Link
                  href={`/tests/${t.test_id}/review`}
                  className="rounded-md bg-zinc-950 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800"
                >
                  Review
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      {showModal && (
        <NewTestModal
          onClose={() => setShowModal(false)}
          onCreated={(testId) => {
            setShowModal(false);
            router.push(`/tests/${testId}`);
          }}
        />
      )}
    </div>
  );
}

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="mx-auto flex h-full max-w-md flex-col items-center justify-center text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
        <Exam size={20} weight="duotone" />
      </div>
      <h2 className="mt-4 text-lg font-semibold text-zinc-950">
        No tests yet
      </h2>
      <p className="mt-1 text-sm text-slate-600">
        Generate your first mock test from any topic in the library.
      </p>
      <button
        type="button"
        onClick={onNew}
        className="mt-6 inline-flex items-center gap-1.5 rounded-md bg-indigo-500 px-4 py-2 text-sm font-medium text-white"
      >
        <Plus size={12} weight="bold" /> New test
      </button>
    </div>
  );
}

function NewTestModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (testId: string) => void;
}) {
  const [leaves, setLeaves] = useState<Leaf[]>([]);
  const [filter, setFilter] = useState("");
  const [pickedNodeId, setPickedNodeId] = useState<string | null>(null);
  const [pickedBookSlug, setPickedBookSlug] = useState<string | null>(null);
  const [count, setCount] = useState(10);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/library/leaves")
      .then((r) => r.json())
      .then((data) => setLeaves(z.array(LeafSchema).parse(data)))
      .catch(() => setLeaves([]));
  }, []);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return leaves.slice(0, 50);
    return leaves
      .filter(
        (l) =>
          l.title.toLowerCase().includes(q) ||
          l.path.toLowerCase().includes(q) ||
          l.book_name.toLowerCase().includes(q),
      )
      .slice(0, 50);
  }, [filter, leaves]);

  const submit = async () => {
    if (!pickedNodeId) {
      setError("Pick a topic from the list first.");
      return;
    }
    setError(null);
    setCreating(true);
    try {
      const resp = await fetch("/api/tests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          node_id: pickedNodeId,
          book_slug: pickedBookSlug,
          n: count,
        }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail ?? `failed (${resp.status})`);
      }
      const data = await resp.json();
      onCreated(data.test_id);
    } catch (e) {
      setError((e as Error).message);
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/30 backdrop-blur-sm">
      <div className="flex max-h-[80vh] w-[640px] flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-zinc-950">
            Generate a mock test
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-zinc-950">
            <X size={16} />
          </button>
        </header>

        <div className="border-b border-slate-100 px-5 py-3">
          <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-1.5">
            <MagnifyingGlass size={14} className="text-slate-400" />
            <input
              autoFocus
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Search topics… (e.g. Aravalli, Climate, Drainage)"
              className="flex-1 bg-transparent text-sm outline-none"
            />
          </div>
        </div>

        <ul className="flex-1 overflow-y-auto px-2 py-2">
          {filtered.length === 0 ? (
            <li className="px-4 py-6 text-center text-sm text-slate-400">
              {leaves.length === 0
                ? "Loading topics…"
                : "No topics match that search."}
            </li>
          ) : (
            filtered.map((leaf) => {
              const picked = pickedNodeId === leaf.node_id;
              return (
                <li key={leaf.node_id}>
                  <button
                    type="button"
                    onClick={() => {
                      setPickedNodeId(leaf.node_id);
                      setPickedBookSlug(leaf.book_slug);
                    }}
                    className={
                      "flex w-full items-start gap-3 rounded-md px-3 py-2 text-left text-sm transition " +
                      (picked
                        ? "bg-indigo-50 text-indigo-900 ring-1 ring-indigo-300"
                        : "hover:bg-slate-50 text-slate-800")
                    }
                  >
                    <CheckCircle
                      size={14}
                      className={
                        "mt-0.5 flex-shrink-0 " +
                        (picked ? "text-indigo-500" : "text-slate-200")
                      }
                      weight={picked ? "fill" : "regular"}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{leaf.title}</p>
                      <p className="truncate text-[11px] text-slate-500">
                        {leaf.book_name} · {leaf.path}
                      </p>
                    </div>
                  </button>
                </li>
              );
            })
          )}
        </ul>

        <footer className="border-t border-slate-200 bg-slate-50 px-5 py-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-500">Questions:</span>
              {[5, 10, 15].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setCount(n)}
                  className={
                    "rounded-md border px-2.5 py-1 font-medium transition " +
                    (count === n
                      ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                      : "border-slate-200 bg-white text-slate-600")
                  }
                >
                  {n}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={submit}
                disabled={!pickedNodeId || creating}
                className="inline-flex items-center gap-1.5 rounded-md bg-indigo-500 px-4 py-1.5 text-xs font-medium text-white disabled:opacity-40"
              >
                {creating && <Spinner size={12} className="animate-spin" />}
                {creating ? "Generating…" : "Generate"}
                {!creating && <ArrowRight size={12} />}
              </button>
            </div>
          </div>
          {error && (
            <p className="mt-2 flex items-center gap-1.5 text-xs text-red-600">
              <Warning size={12} /> {error}
            </p>
          )}
          <p className="mt-2 text-[11px] text-slate-500">
            Generation takes 30–60 seconds. We oversample candidates and keep
            only those that pass span verification + the LLM judge.
          </p>
        </footer>
      </div>
    </div>
  );
}

function prettyNodeTitle(nodeId: string): string {
  const last = nodeId.split("/").pop() ?? nodeId;
  return last.replace(/^\d+-/, "").replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
