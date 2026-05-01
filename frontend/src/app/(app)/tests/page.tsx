import Link from "next/link";

/**
 * Placeholder /tests index — full implementation lands Day 7
 * per docs/research/2026-05-02-ux-redesign-architecture.md §2.3.
 */
export default function TestsPage() {
  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 items-center border-b border-slate-200 bg-white px-6">
        <h1 className="text-sm font-semibold text-zinc-950">Tests</h1>
      </header>
      <div className="px-6 py-8">
        <p className="text-sm text-slate-600">
          Mock test list is coming on Day 7. Until then, generate one from a
          leaf via{" "}
          <Link href="/library" className="text-indigo-600 hover:underline">
            the Library
          </Link>
          .
        </p>
      </div>
    </div>
  );
}
