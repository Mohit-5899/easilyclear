"use client";

import { ArrowLeft, ArrowRight } from "@phosphor-icons/react";
import type { TreeNode } from "@/lib/types";

interface SiblingNavProps {
  siblings: TreeNode[];
  currentId: string;
  onNavigate: (id: string) => void;
}

export function SiblingNav({ siblings, currentId, onNavigate }: SiblingNavProps) {
  const currentIndex = siblings.findIndex((s) => s.node_id === currentId);
  if (currentIndex === -1 || siblings.length <= 1) return null;

  const prev = currentIndex > 0 ? siblings[currentIndex - 1] : null;
  const next = currentIndex < siblings.length - 1 ? siblings[currentIndex + 1] : null;

  return (
    <div className="flex items-stretch gap-3 pt-4 border-t border-slate-100">
      <button
        onClick={() => prev && onNavigate(prev.node_id)}
        disabled={!prev}
        className="flex-1 flex items-center gap-2 rounded-xl border border-slate-100 px-4 py-3 text-left transition-colors hover:bg-slate-50 active:-translate-y-[1px] disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent"
      >
        <ArrowLeft size={14} className="flex-shrink-0 text-slate-400" />
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wider text-slate-400">Previous</p>
          <p className="text-sm text-zinc-950 truncate">
            {prev?.title ?? "\u2014"}
          </p>
        </div>
      </button>

      <button
        onClick={() => next && onNavigate(next.node_id)}
        disabled={!next}
        className="flex-1 flex items-center justify-end gap-2 rounded-xl border border-slate-100 px-4 py-3 text-right transition-colors hover:bg-slate-50 active:-translate-y-[1px] disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent"
      >
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wider text-slate-400">Next</p>
          <p className="text-sm text-zinc-950 truncate">
            {next?.title ?? "\u2014"}
          </p>
        </div>
        <ArrowRight size={14} className="flex-shrink-0 text-slate-400" />
      </button>
    </div>
  );
}
