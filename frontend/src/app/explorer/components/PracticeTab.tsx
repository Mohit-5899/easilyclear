"use client";

/**
 * PracticeTab — generates a mock test from the selected skill node and
 * navigates the user to the full-screen test mode at /test/[id].
 *
 * Per spec docs/superpowers/specs/2026-05-03-mock-test.md.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Exam, Spinner, Warning } from "@phosphor-icons/react";

import { createMockTest } from "@/lib/mock-test-api";

interface PracticeTabProps {
  nodeId: string;
  nodeName: string;
  bookSlug: string;
}

export function PracticeTab({ nodeId, nodeName, bookSlug }: PracticeTabProps) {
  const router = useRouter();
  const [count, setCount] = useState(10);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const test = await createMockTest({
        node_id: nodeId,
        book_slug: bookSlug,
        n: count,
      });
      router.push(`/test/${test.test_id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="px-6 py-5">
      <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-wider text-slate-400">
        <Exam size={11} />
        Practice
      </div>

      <h3 className="mt-2 text-base font-semibold text-zinc-950">
        Generate a mock test
      </h3>
      <p className="mt-1 text-sm text-slate-600">
        Questions are grounded in <span className="font-medium">{nodeName}</span>
        &apos;s source paragraphs. Every correct answer is a verbatim span from
        the textbook.
      </p>

      <label className="mt-5 block text-xs font-medium text-slate-700">
        Number of questions
      </label>
      <div className="mt-2 flex items-center gap-2">
        {[5, 10, 15].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => setCount(n)}
            disabled={generating}
            className={
              "rounded-md border px-3 py-1.5 text-sm font-medium transition " +
              (count === n
                ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                : "border-slate-200 bg-white text-slate-700 hover:border-slate-300")
            }
          >
            {n}
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={generate}
        disabled={generating}
        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-md bg-indigo-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-600 disabled:opacity-50"
      >
        {generating ? (
          <>
            <Spinner size={14} className="animate-spin" />
            Generating {count} questions…
          </>
        ) : (
          <>Start generating</>
        )}
      </button>

      <p className="mt-3 text-xs text-slate-500">
        Generation can take 30–60 seconds. The Gemma 4 26B model writes 13
        candidates and our verifier keeps only the {count} that pass span +
        single-correct checks.
      </p>

      {error && (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <Warning size={14} className="mt-0.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
