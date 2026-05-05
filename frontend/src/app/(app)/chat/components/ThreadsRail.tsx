"use client";

import { Plus, Trash } from "@phosphor-icons/react";

import type { ThreadIndex } from "@/lib/chat-store";

/**
 * Left-side rail listing recent chat threads. localStorage-backed; the
 * parent page hydrates threads via lib/chat-store on mount.
 */
export function ThreadsRail({
  threads,
  activeId,
  streaming,
  onNewThread,
  onOpen,
  onDelete,
}: {
  threads: ThreadIndex[];
  activeId: string | null;
  streaming: boolean;
  onNewThread: () => void;
  onOpen: (id: string) => void;
  onDelete: (id: string, ev: React.MouseEvent) => void;
}) {
  return (
    <aside className="hidden w-56 flex-shrink-0 border-r border-slate-200 bg-white md:flex md:flex-col">
      <div className="flex h-14 items-center justify-between border-b border-slate-200 px-3">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Threads
        </span>
        <button
          type="button"
          onClick={onNewThread}
          disabled={streaming}
          className="inline-flex items-center gap-1 rounded-md bg-zinc-950 px-2 py-1 text-[11px] font-medium text-white disabled:opacity-30"
        >
          <Plus size={10} weight="bold" /> New
        </button>
      </div>

      <ul className="flex-1 overflow-y-auto p-2">
        {threads.length === 0 ? (
          <li className="px-2 py-3 text-xs text-slate-400">
            Your conversations will appear here.
          </li>
        ) : (
          threads.map((th) => (
            <li key={th.id}>
              <button
                type="button"
                onClick={() => onOpen(th.id)}
                className={
                  "group flex w-full items-start justify-between gap-1 rounded-md px-2 py-1.5 text-left text-xs transition " +
                  (th.id === activeId
                    ? "bg-indigo-50 text-indigo-900"
                    : "text-slate-700 hover:bg-slate-100")
                }
              >
                <span className="line-clamp-2 flex-1 leading-snug">
                  {th.title}
                </span>
                <span
                  role="button"
                  tabIndex={0}
                  aria-label="Delete thread"
                  onClick={(ev) => onDelete(th.id, ev)}
                  onKeyDown={(ev) => {
                    if (ev.key === "Enter" || ev.key === " ") {
                      onDelete(th.id, ev as unknown as React.MouseEvent);
                    }
                  }}
                  className="invisible inline-flex h-4 w-4 cursor-pointer items-center justify-center rounded text-slate-400 hover:bg-slate-200 group-hover:visible"
                >
                  <Trash size={10} />
                </span>
              </button>
            </li>
          ))
        )}
      </ul>
    </aside>
  );
}
