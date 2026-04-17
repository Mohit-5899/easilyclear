"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CaretDown, TreeStructure, GraduationCap, Books } from "@phosphor-icons/react";
import type { ManifestEntry, TreeStats } from "@/lib/types";

interface BrandPillProps {
  books: ManifestEntry[];
  selectedSlug: string | null;
  currentBookName: string | null;
  currentScope: string | null;
  stats: TreeStats | null;
  onSelect: (slug: string) => void;
}

export function BrandPill({
  books,
  selectedSlug,
  currentBookName,
  currentScope,
  stats,
  onSelect,
}: BrandPillProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="pointer-events-auto absolute left-6 top-6 z-30">
      <div className="flex items-center gap-3 rounded-full border border-slate-200/60 bg-white/80 py-2 pl-3 pr-2 shadow-[0_20px_40px_-15px_rgba(0,0,0,0.08)] backdrop-blur-xl">
        {/* Brand mark */}
        <div className="flex items-center gap-2 pl-1 pr-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-500 text-white">
            <TreeStructure size={14} weight="bold" />
          </div>
          <div className="flex flex-col leading-none">
            <span className="text-[11px] font-semibold tracking-tight text-zinc-950">
              Tree Explorer
            </span>
            <span className="text-[9px] text-slate-400 tracking-wide uppercase">
              Gemma Tutor
            </span>
          </div>
        </div>

        <div className="h-6 w-px bg-slate-200" />

        {/* Book selector */}
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 rounded-full px-3 py-1.5 text-left transition-colors hover:bg-slate-100/70 active:scale-[0.98]"
        >
          <Books size={14} className="flex-shrink-0 text-slate-500" />
          <span className="max-w-[200px] truncate text-xs font-medium text-zinc-950">
            {currentBookName ?? "Select a book"}
          </span>
          <CaretDown
            size={10}
            weight="bold"
            className={`flex-shrink-0 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
          />
        </button>

        {/* Stats chips */}
        {stats && currentScope && (
          <>
            <div className="h-6 w-px bg-slate-200" />
            <div className="flex items-center gap-1.5 pr-1">
              <StatChip label="nodes" value={stats.totalNodes} />
              <StatChip label="depth" value={stats.maxDepth} />
              <StatChip
                label="pages"
                value={`${stats.pageRange[0]}–${stats.pageRange[1]}`}
              />
              <ScopePill scope={currentScope} />
            </div>
          </>
        )}
      </div>

      {/* Book dropdown */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ type: "spring", stiffness: 400, damping: 28 }}
            className="absolute left-0 top-full mt-2 w-[380px] overflow-hidden rounded-2xl border border-slate-200/60 bg-white/95 p-2 shadow-[0_30px_60px_-15px_rgba(0,0,0,0.15)] backdrop-blur-xl"
          >
            <div className="px-2 py-1.5">
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                Ingested Books
              </p>
            </div>
            <div className="space-y-0.5">
              {books.map((book) => {
                const isActive = book.slug === selectedSlug;
                return (
                  <button
                    key={book.slug}
                    onClick={() => {
                      onSelect(book.slug);
                      setOpen(false);
                    }}
                    className={`flex w-full items-start gap-2 rounded-lg px-2.5 py-2 text-left transition-colors ${
                      isActive ? "bg-emerald-50" : "hover:bg-slate-50"
                    }`}
                  >
                    <GraduationCap
                      size={14}
                      className={`mt-0.5 flex-shrink-0 ${isActive ? "text-emerald-600" : "text-slate-400"}`}
                    />
                    <div className="min-w-0 flex-1">
                      <p
                        className={`truncate text-xs font-medium ${
                          isActive ? "text-emerald-900" : "text-zinc-950"
                        }`}
                      >
                        {book.name}
                      </p>
                      <div className="mt-1 flex gap-1.5">
                        <ScopePill scope={book.scope} />
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function StatChip({ label, value }: { label: string; value: number | string }) {
  return (
    <span className="flex items-baseline gap-1 rounded-full bg-slate-100 px-2 py-0.5">
      <span className="font-mono text-[10px] font-semibold text-zinc-950">
        {value}
      </span>
      <span className="text-[9px] uppercase tracking-wider text-slate-400">
        {label}
      </span>
    </span>
  );
}

function ScopePill({ scope }: { scope: string }) {
  const isRajasthan = scope === "rajasthan";
  return (
    <span
      className={`inline-flex rounded-full px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wider ${
        isRajasthan
          ? "bg-emerald-100 text-emerald-700"
          : "bg-slate-200 text-slate-600"
      }`}
    >
      {scope}
    </span>
  );
}
