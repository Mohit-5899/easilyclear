"use client";

import { BookmarkSimple } from "@phosphor-icons/react";

import type { Citation } from "../types";

/**
 * Right-side rail of source citation cards. Cross-linked with the [N]
 * markers in assistant turn bodies via the hovered-citation index.
 *
 * Brand-strip rule (spec 2026-05-04): cards show only `[N] page X` and
 * snippet text — never publisher names. Internal frontmatter keeps the
 * publisher info; this layer never reads it.
 */
export function CitationsRail({
  citations,
  hoveredCitation,
  onHover,
}: {
  citations: Citation[];
  hoveredCitation: number | null;
  onHover: (i: number | null) => void;
}) {
  return (
    <aside className="hidden w-72 flex-shrink-0 border-l border-slate-200 bg-white lg:flex lg:flex-col">
      <header className="flex h-14 items-center border-b border-slate-200 px-4">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Sources
        </h2>
      </header>
      <div className="flex-1 overflow-y-auto p-3">
        {citations.length === 0 ? (
          <p className="text-xs text-slate-400">
            Citations appear here as the agent retrieves source paragraphs.
          </p>
        ) : (
          <ul className="space-y-2">
            {citations.map((c) => (
              <li
                key={`${c.index}-${c.node_id}-${c.paragraph_id}`}
                onMouseEnter={() => onHover(c.index)}
                onMouseLeave={() => onHover(null)}
                className={
                  "rounded-md border bg-white p-3 text-xs transition " +
                  (hoveredCitation === c.index
                    ? "border-indigo-400 bg-indigo-50/40"
                    : "border-slate-200 hover:border-slate-300")
                }
              >
                <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wider text-slate-400">
                  <span>
                    [{c.index}] page {c.page}
                  </span>
                  <BookmarkSimple size={10} />
                </div>
                <p className="mt-1.5 line-clamp-4 leading-relaxed text-slate-700">
                  {c.snippet}
                </p>
                <p className="mt-2 truncate font-mono text-[10px] text-slate-400">
                  {shortNodeId(c.node_id)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}

function shortNodeId(id: string): string {
  const parts = id.split("/");
  return parts.slice(-2).join("/");
}
