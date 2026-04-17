"use client";

import { CaretDown } from "@phosphor-icons/react";
import type { ManifestEntry } from "@/lib/types";

interface BookSelectorProps {
  books: ManifestEntry[];
  selectedSlug: string | null;
  onSelect: (slug: string) => void;
}

export function BookSelector({ books, selectedSlug, onSelect }: BookSelectorProps) {
  return (
    <div className="relative">
      <select
        value={selectedSlug ?? ""}
        onChange={(e) => onSelect(e.target.value)}
        className="w-full appearance-none rounded-xl border border-slate-200/50 bg-white px-4 py-3 pr-10 font-sans text-sm font-medium text-zinc-950 shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)] transition-colors hover:border-slate-300 focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-400/20"
      >
        <option value="" disabled>
          Select a book to explore
        </option>
        {books.map((book) => (
          <option key={book.slug} value={book.slug}>
            {book.name}
          </option>
        ))}
      </select>
      <CaretDown
        size={16}
        weight="bold"
        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
      />
    </div>
  );
}
