import { readFile } from "fs/promises";
import { join, resolve } from "path";

import { notFound } from "next/navigation";

import { ExplorerClient } from "@/app/explorer/ExplorerClient";
import type { BookData, ManifestEntry } from "@/lib/types";
import { readSkillFolder } from "@/lib/skill-folder-reader";

interface PageProps {
  params: Promise<{ bookSlug: string }>;
}

export const metadata = {
  title: "Library — Gemma Tutor",
};

export default async function LibraryBookPage({ params }: PageProps) {
  const { bookSlug } = await params;

  const manifestPath = join(process.cwd(), "public", "data", "manifest.json");
  const raw = await readFile(manifestPath, "utf-8");
  const manifest: ManifestEntry[] = JSON.parse(raw);

  const entry = manifest.find((m) => m.slug === bookSlug);
  if (!entry || !entry.skill_folder) {
    notFound();
  }

  const repoRoot = resolve(process.cwd(), "..");
  let book: BookData;
  try {
    book = await readSkillFolder(resolve(repoRoot, entry.skill_folder));
  } catch {
    notFound();
  }

  // ExplorerClient already handles its own chrome — render it as the
  // entire content area inside the AppShell.
  return (
    <ExplorerClient
      manifest={[entry]}
      preloadedBooks={{ [bookSlug]: book }}
    />
  );
}
