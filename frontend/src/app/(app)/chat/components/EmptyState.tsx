"use client";

import { ChatCircle } from "@phosphor-icons/react";

const EXAMPLES = [
  "Why is Aravalli called the planning region of Rajasthan?",
  "What is Mawath rainfall?",
  "Which districts have arid climate per Koppen?",
  "Name the highest peak of Aravalli with its district.",
] as const;

/**
 * /chat empty state — 4 starter prompts for the demo. Pinned by the
 * Playwright J1 journey (frontend/e2e/sanity.spec.ts).
 */
export function EmptyState({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="mx-auto flex h-full max-w-2xl items-center justify-center">
      <div className="text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
          <ChatCircle size={20} weight="duotone" />
        </div>
        <h2 className="mt-4 text-lg font-semibold text-zinc-950">Ask anything</h2>
        <p className="mt-1 text-sm text-slate-600">
          Gemma will search the canonical sources and cite every claim.
        </p>
        <div className="mt-6 grid gap-2 text-left">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => onPick(ex)}
              className="rounded-md border border-slate-200 bg-white px-4 py-2.5 text-left text-sm text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50/30"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
