"use client";

/**
 * Review page — submits the answers stored in sessionStorage to the
 * grading API and renders score + per-question correctness with
 * explanations and source paragraph IDs.
 */

import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import {
  CheckCircle,
  Spinner,
  XCircle,
  ArrowLeft,
} from "@phosphor-icons/react";

import {
  getMockTest,
  gradeMockTest,
  type Choice,
  type GradeResponse,
  type MockTest,
} from "@/lib/mock-test-api";

interface PageProps {
  params: Promise<{ testId: string }>;
}

const ANSWERS_KEY = (id: string) => `gemma-tutor-answers-${id}`;

export default function ReviewPage({ params }: PageProps) {
  const { testId } = use(params);
  const router = useRouter();

  const [test, setTest] = useState<MockTest | null>(null);
  const [grade, setGrade] = useState<GradeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const t = await getMockTest(testId);
        if (cancelled) return;
        setTest(t);
        const saved =
          typeof window !== "undefined"
            ? window.sessionStorage.getItem(ANSWERS_KEY(testId))
            : null;
        const answers = (saved ? JSON.parse(saved) : {}) as Record<string, Choice>;
        const g = await gradeMockTest(testId, answers);
        if (!cancelled) setGrade(g);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [testId]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <div className="rounded-lg border border-red-200 bg-red-50 p-6">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      </div>
    );
  }

  if (!test || !grade) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <Spinner size={28} className="animate-spin text-slate-400" />
      </div>
    );
  }

  const pct = Math.round((grade.score / Math.max(1, grade.total)) * 100);

  return (
    <main className="min-h-screen bg-slate-50 pb-16">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <button
            onClick={() => router.push("/explorer")}
            className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-zinc-950"
          >
            <ArrowLeft size={12} /> Back to Explorer
          </button>
          <span className="text-xs text-slate-500">Test review</span>
        </div>
      </header>

      <section className="mx-auto max-w-3xl px-6 pt-8">
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Your score
          </p>
          <p className="mt-2 text-5xl font-semibold tracking-tight text-zinc-950">
            {grade.score}
            <span className="text-3xl text-slate-400"> / {grade.total}</span>
          </p>
          <p className="mt-1 text-sm text-slate-600">{pct}% correct</p>
        </div>
      </section>

      <section className="mx-auto mt-8 max-w-3xl space-y-4 px-6">
        {test.questions.map((q, i) => {
          const detail = grade.details.find((d) => d.question_id === q.id);
          const isCorrect = detail?.is_correct ?? false;
          const userPick = detail?.user;
          return (
            <article
              key={q.id}
              className={
                "rounded-xl border p-5 " +
                (isCorrect
                  ? "border-emerald-200 bg-emerald-50/50"
                  : "border-rose-200 bg-rose-50/50")
              }
            >
              <header className="flex items-start gap-2">
                {isCorrect ? (
                  <CheckCircle size={16} className="mt-0.5 text-emerald-600" />
                ) : (
                  <XCircle size={16} className="mt-0.5 text-rose-600" />
                )}
                <div className="flex-1">
                  <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
                    Question {i + 1} · {q.difficulty}
                  </p>
                  <p className="mt-1 text-sm font-medium text-zinc-950">
                    {q.prompt}
                  </p>
                </div>
              </header>

              <div className="mt-3 space-y-1.5 pl-6">
                {(["A", "B", "C", "D"] as const).map((key) => {
                  const isPick = userPick === key;
                  const isAnswer = q.correct === key;
                  let cls = "border-slate-200 bg-white text-slate-700";
                  if (isAnswer) cls = "border-emerald-400 bg-emerald-100 text-emerald-900";
                  if (isPick && !isAnswer)
                    cls = "border-rose-400 bg-rose-100 text-rose-900";
                  return (
                    <div
                      key={key}
                      className={
                        "flex items-start gap-2 rounded-md border px-3 py-1.5 text-sm " +
                        cls
                      }
                    >
                      <span className="font-semibold">{key}.</span>
                      <span className="flex-1">{q.choices[key]}</span>
                      {isAnswer && <span className="text-[10px] font-semibold">CORRECT</span>}
                      {isPick && !isAnswer && (
                        <span className="text-[10px] font-semibold">YOUR PICK</span>
                      )}
                    </div>
                  );
                })}
              </div>

              {q.explanation && (
                <p className="mt-3 pl-6 text-xs leading-relaxed text-slate-600">
                  <span className="font-medium text-slate-700">Why: </span>
                  {q.explanation}
                </p>
              )}
              <p className="mt-1 pl-6 text-[10px] text-slate-400">
                Source paragraphs: {q.source_paragraph_ids.join(", ")}
              </p>
            </article>
          );
        })}
      </section>
    </main>
  );
}
