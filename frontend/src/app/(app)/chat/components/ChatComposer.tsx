"use client";

import { PaperPlaneRight, Stop } from "@phosphor-icons/react";

import type { Scope } from "../types";

const SCOPE_OPTIONS: readonly { value: Scope; label: string }[] = [
  { value: "all", label: "All subjects" },
  { value: "subject", label: "Current subject" },
  { value: "node", label: "Current selection" },
] as const;

/**
 * Bottom composer — textarea, send/stop button, scope picker.
 *
 * Scope label invariant (spec 2026-05-04 §6 brand-strip): never mention
 * publisher names. Pinned by Playwright J1 (e2e/sanity.spec.ts).
 */
export function ChatComposer({
  draft,
  onDraftChange,
  scope,
  onScopeChange,
  streaming,
  onSend,
  onStop,
}: {
  draft: string;
  onDraftChange: (s: string) => void;
  scope: Scope;
  onScopeChange: (s: Scope) => void;
  streaming: boolean;
  onSend: () => void;
  onStop: () => void;
}) {
  return (
    <div className="border-t border-slate-200 bg-white px-6 py-4">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-xl border border-slate-200 bg-white p-2 shadow-sm focus-within:border-indigo-400">
          <textarea
            value={draft}
            onChange={(e) => onDraftChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            rows={1}
            placeholder="Ask anything about Rajasthan geography…"
            className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm leading-relaxed text-zinc-950 outline-none placeholder:text-slate-400"
            disabled={streaming}
          />
          <button
            type="button"
            onClick={streaming ? onStop : onSend}
            disabled={!streaming && !draft.trim()}
            className="flex h-8 w-8 items-center justify-center rounded-md bg-indigo-500 text-white transition hover:bg-indigo-600 disabled:opacity-30"
            aria-label={streaming ? "Stop" : "Send"}
          >
            {streaming ? <Stop size={14} /> : <PaperPlaneRight size={14} />}
          </button>
        </div>
        <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
          <label className="inline-flex items-center gap-1.5">
            Scope:
            <select
              value={scope}
              onChange={(e) => onScopeChange(e.target.value as Scope)}
              className="bg-transparent text-zinc-700 focus:outline-none"
              disabled={streaming}
            >
              {SCOPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <span>Model: google/gemma-4-26b-a4b-it</span>
        </div>
      </div>
    </div>
  );
}
