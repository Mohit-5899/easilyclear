import { readFile } from "fs/promises";
import { join, resolve } from "path";

import Link from "next/link";
import { ArrowRight, BookOpen, CloudArrowUp } from "@phosphor-icons/react/dist/ssr";

import type { ManifestEntry } from "@/lib/types";
import { readSkillFolder } from "@/lib/skill-folder-reader";

export const metadata = {
  title: "Library — Gemma Tutor",
  description: "Browse ingested textbook skill trees",
};

interface BookCard {
  slug: string;
  name: string;
  scope: string;
  totalNodes: number;
  totalLeaves: number;
  available: boolean;
}

async function buildBookCards(): Promise<BookCard[]> {
  const manifestPath = join(process.cwd(), "public", "data", "manifest.json");
  const raw = await readFile(manifestPath, "utf-8").catch(() => "[]");
  const manifest: ManifestEntry[] = JSON.parse(raw);
  const repoRoot = resolve(process.cwd(), "..");

  const cards: BookCard[] = [];
  for (const entry of manifest) {
    if (!entry.skill_folder) continue;
    try {
      const book = await readSkillFolder(resolve(repoRoot, entry.skill_folder));
      const stats = countTree(book.structure);
      cards.push({
        slug: entry.slug,
        name: entry.name ?? entry.slug,
        scope: entry.scope ?? "—",
        totalNodes: stats.total,
        totalLeaves: stats.leaves,
        available: true,
      });
    } catch {
      cards.push({
        slug: entry.slug,
        name: entry.name ?? entry.slug,
        scope: entry.scope ?? "—",
        totalNodes: 0,
        totalLeaves: 0,
        available: false,
      });
    }
  }
  return cards;
}

interface CountableNode {
  nodes?: CountableNode[];
}

function countTree(roots: CountableNode[]): { total: number; leaves: number } {
  let total = 0;
  let leaves = 0;
  for (const r of roots) {
    const sub = countSubtree(r);
    total += sub.total;
    leaves += sub.leaves;
  }
  return { total, leaves };
}

function countSubtree(node: CountableNode): { total: number; leaves: number } {
  const children = node.nodes ?? [];
  if (children.length === 0) return { total: 1, leaves: 1 };
  let total = 1;
  let leaves = 0;
  for (const c of children) {
    const sub = countSubtree(c);
    total += sub.total;
    leaves += sub.leaves;
  }
  return { total, leaves };
}

export default async function LibraryIndex() {
  const cards = await buildBookCards();
  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-6">
        <h1 className="text-sm font-semibold text-zinc-950">Library</h1>
        <Link
          href="/admin/ingest?admin=1"
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 hover:border-indigo-300 hover:text-zinc-950"
        >
          <CloudArrowUp size={12} /> Ingest a source
        </Link>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {cards.length === 0 ? (
          <p className="text-sm text-slate-500">
            No sources ingested yet. Try the Admin → Ingest page.
          </p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {cards.map((c) => (
              <li key={c.slug}>
                <Link
                  href={`/library/${c.slug}`}
                  className={
                    "group block rounded-xl border bg-white p-5 transition " +
                    (c.available
                      ? "border-slate-200 hover:border-indigo-300 hover:shadow-sm"
                      : "border-dashed border-slate-200 opacity-60")
                  }
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                      <BookOpen size={18} weight="duotone" />
                    </div>
                    <ArrowRight
                      size={14}
                      className="mt-2 text-slate-400 transition group-hover:translate-x-0.5 group-hover:text-indigo-500"
                    />
                  </div>
                  <h2 className="mt-4 text-sm font-semibold leading-snug text-zinc-950">
                    {c.name}
                  </h2>
                  <p className="mt-1 text-[11px] uppercase tracking-wider text-slate-400">
                    {c.scope}
                  </p>
                  {c.available ? (
                    <p className="mt-3 text-xs text-slate-500">
                      {c.totalNodes} nodes · {c.totalLeaves} leaves
                    </p>
                  ) : (
                    <p className="mt-3 text-xs text-amber-600">
                      Manifest entry — no on-disk skill folder
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
