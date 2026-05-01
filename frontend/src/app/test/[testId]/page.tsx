"use client";

/**
 * Full-screen mock test mode. Loads test by ID, walks the user through
 * each question, then routes to the review page on submit.
 */

import { useRouter } from "next/navigation";
import { use, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  Clock,
  Spinner,
} from "@phosphor-icons/react";

import {
  getMockTest,
  type Choice,
  type MockTest,
} from "@/lib/mock-test-api";

interface PageProps {
  params: Promise<{ testId: string }>;
}

const ANSWERS_KEY = (id: string) => `gemma-tutor-answers-${id}`;

export default function TestPage({ params }: PageProps) {
  const { testId } = use(params);
  const router = useRouter();

  const [test, setTest] = useState<MockTest | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, Choice>>({});
  const [currentIdx, setCurrentIdx] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  // Load + restore in-progress answers from sessionStorage
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const t = await getMockTest(testId);
        if (cancelled) return;
        setTest(t);
        if (typeof window !== "undefined") {
          const saved = window.sessionStorage.getItem(ANSWERS_KEY(testId));
          if (saved) {
            try {
              setAnswers(JSON.parse(saved));
            } catch {
              // ignore
            }
          }
        }
      } catch (e) {
        if (!cancelled) setLoadError((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [testId]);

  // Persist answers as the user picks them
  useEffect(() => {
    if (typeof window === "undefined") return;
    window.sessionStorage.setItem(ANSWERS_KEY(testId), JSON.stringify(answers));
  }, [answers, testId]);

  const total = test?.questions.length ?? 0;
  const current = test?.questions[currentIdx];
  const answeredCount = useMemo(
    () => Object.keys(answers).length,
    [answers],
  );
  const allAnswered = total > 0 && answeredCount === total;

  const submit = async () => {
    if (!test) return;
    setSubmitting(true);
    router.push(`/test/${testId}/review`);
  };

  if (loadError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <div className="max-w-md rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm font-medium text-red-700">Failed to load test</p>
          <p className="mt-1 text-xs text-red-600">{loadError}</p>
          <button
            onClick={() => router.push("/explorer")}
            className="mt-4 rounded-md bg-red-600 px-3 py-1.5 text-sm text-white"
          >
            Back to Explorer
          </button>
        </div>
      </div>
    );
  }

  if (!test || !current) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <Spinner size={28} className="animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-6 py-4">
          <button
            onClick={() => router.push("/explorer")}
            className="text-xs text-slate-500 hover:text-zinc-950"
          >
            ← Exit
          </button>
          <div className="flex items-center gap-4 text-xs text-slate-600">
            <span className="inline-flex items-center gap-1">
              <Clock size={12} />
              Question {currentIdx + 1} / {total}
            </span>
            <span className="inline-flex items-center gap-1">
              <CheckCircle size={12} />
              {answeredCount} answered
            </span>
          </div>
        </div>
        <div className="h-1 w-full bg-slate-100">
          <div
            className="h-full bg-indigo-500 transition-all"
            style={{ width: `${((currentIdx + 1) / total) * 100}%` }}
          />
        </div>
      </header>

      <article className="mx-auto max-w-3xl px-6 py-8">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
            {current.difficulty} · {current.bloom_level}
          </div>
          <h2 className="mt-2 text-lg font-semibold leading-relaxed text-zinc-950">
            {current.prompt}
          </h2>

          <div className="mt-6 space-y-2">
            {(["A", "B", "C", "D"] as const).map((key) => {
              const selected = answers[current.id] === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() =>
                    setAnswers((a) => ({ ...a, [current.id]: key }))
                  }
                  className={
                    "flex w-full items-start gap-3 rounded-lg border px-4 py-3 text-left text-sm transition " +
                    (selected
                      ? "border-indigo-500 bg-indigo-50 text-zinc-950 ring-1 ring-indigo-300"
                      : "border-slate-200 bg-white text-slate-800 hover:border-slate-300")
                  }
                >
                  <span
                    className={
                      "flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-[11px] font-semibold " +
                      (selected
                        ? "bg-indigo-500 text-white"
                        : "bg-slate-100 text-slate-700")
                    }
                  >
                    {key}
                  </span>
                  <span className="leading-relaxed">{current.choices[key]}</span>
                </button>
              );
            })}
          </div>
        </div>

        <nav className="mt-6 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setCurrentIdx((i) => Math.max(0, i - 1))}
            disabled={currentIdx === 0}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 disabled:opacity-40"
          >
            <ArrowLeft size={14} /> Previous
          </button>

          {currentIdx < total - 1 ? (
            <button
              type="button"
              onClick={() => setCurrentIdx((i) => Math.min(total - 1, i + 1))}
              className="inline-flex items-center gap-1.5 rounded-md bg-zinc-950 px-3 py-1.5 text-sm font-medium text-white"
            >
              Next <ArrowRight size={14} />
            </button>
          ) : (
            <button
              type="button"
              onClick={submit}
              disabled={!allAnswered || submitting}
              className="inline-flex items-center gap-1.5 rounded-md bg-indigo-500 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-600 disabled:opacity-40"
            >
              {submitting ? (
                <Spinner size={14} className="animate-spin" />
              ) : null}
              Submit test
            </button>
          )}
        </nav>

        {!allAnswered && currentIdx === total - 1 && (
          <p className="mt-3 text-center text-xs text-slate-500">
            Answer all {total} questions before submitting.
          </p>
        )}
      </article>
    </main>
  );
}
