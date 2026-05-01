import Link from "next/link";

/**
 * Placeholder /library index — multi-book picker lands Day 2 once
 * /explorer is renamed. For now, deep-link straight into the existing
 * /explorer view.
 */
export default function LibraryIndex() {
  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 items-center border-b border-slate-200 bg-white px-6">
        <h1 className="text-sm font-semibold text-zinc-950">Library</h1>
      </header>
      <div className="px-6 py-8">
        <p className="mb-4 text-sm text-slate-600">
          Browse ingested books and their skill trees. The full multi-book
          picker arrives Day 2 of the redesign sprint.
        </p>
        <Link
          href="/explorer"
          className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-zinc-900 hover:border-indigo-300 hover:bg-indigo-50/40"
        >
          Open the explorer canvas →
        </Link>
      </div>
    </div>
  );
}
