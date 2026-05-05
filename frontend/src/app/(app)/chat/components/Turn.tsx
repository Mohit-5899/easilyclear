"use client";

import { Spinner } from "@phosphor-icons/react";

import type { ChatTurn, Citation, ToolCallEvent } from "../types";

/**
 * One conversation turn — user OR assistant. Assistant turns render their
 * stack of tool-call pills above the answer body, with [N] citation markers
 * highlighted on hover (cross-linked from the right-rail CitationsRail).
 */
export function Turn({
  turn,
  hoveredCitation,
  onHoverCitation,
}: {
  turn: ChatTurn;
  hoveredCitation: number | null;
  onHoverCitation: (i: number | null) => void;
}) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl bg-indigo-500 px-4 py-2.5 text-sm text-white">
          {turn.text}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {turn.toolCalls.map((c) => (
        <ToolCallPill key={c.id} call={c} />
      ))}
      {turn.text && (
        <div className="rounded-2xl bg-slate-100 px-4 py-3 text-sm leading-relaxed text-zinc-900">
          <RenderTextWithCitations
            text={turn.text}
            citations={turn.citations}
            hoveredCitation={hoveredCitation}
            onHoverCitation={onHoverCitation}
          />
        </div>
      )}
    </div>
  );
}

function ToolCallPill({ call }: { call: ToolCallEvent }) {
  const completed = call.hitCount !== undefined;
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] text-slate-600">
      {completed ? (
        <span className="text-emerald-500">✓</span>
      ) : (
        <Spinner size={10} className="animate-spin text-indigo-500" />
      )}
      <span className="text-slate-500">
        {completed ? `Found ${call.hitCount} in` : "Searching"}
      </span>
      <span className="font-medium text-zinc-900">
        {call.scopeLabel ?? call.query}
      </span>
    </div>
  );
}

function RenderTextWithCitations({
  text,
  citations,
  hoveredCitation,
  onHoverCitation,
}: {
  text: string;
  citations: Citation[];
  hoveredCitation: number | null;
  onHoverCitation: (i: number | null) => void;
}) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const m = /^\[(\d+)\]$/.exec(part);
        if (!m) return <span key={i}>{part}</span>;
        const num = parseInt(m[1], 10);
        const c = citations.find((x) => x.index === num);
        const active = hoveredCitation === num;
        return (
          <span
            key={i}
            onMouseEnter={() => onHoverCitation(num)}
            onMouseLeave={() => onHoverCitation(null)}
            className={
              "mx-0.5 inline-block cursor-help rounded border px-1 text-[11px] transition " +
              (active
                ? "border-indigo-500 bg-indigo-100 text-indigo-800"
                : "border-indigo-300 bg-indigo-50 text-indigo-700")
            }
            title={c ? `${c.snippet} (page ${c.page})` : `Citation ${num}`}
          >
            [{num}]
          </span>
        );
      })}
    </>
  );
}
