import { readFile } from "fs/promises";
import { join, resolve } from "path";
import type { BookData, ManifestEntry } from "@/lib/types";
import { readSkillFolder } from "@/lib/skill-folder-reader";
import { ExplorerClient } from "./ExplorerClient";

export const metadata = {
  title: "Tree Explorer — Gemma Tutor",
  description: "Browse ingested knowledge tree structures",
};

export default async function ExplorerPage() {
  const manifestPath = join(process.cwd(), "public", "data", "manifest.json");
  const raw = await readFile(manifestPath, "utf-8");
  const manifest: ManifestEntry[] = JSON.parse(raw);

  // Skill folder paths in the manifest are relative to repo root. The
  // Next.js dev/build cwd is the frontend/ directory, so go up one level.
  const repoRoot = resolve(process.cwd(), "..");

  const skillFolderEntries = manifest.filter(
    (entry): entry is ManifestEntry & { skill_folder: string } =>
      Boolean(entry.skill_folder)
  );

  // Skip entries whose on-disk folder is missing — a manifest entry is intent;
  // actual availability depends on whether ingestion has run. Callers (the
  // explorer dropdown) gracefully handle slugs with no preloaded book.
  const preloadedEntries = await Promise.all(
    skillFolderEntries.map(async (entry) => {
      try {
        const absoluteFolder = resolve(repoRoot, entry.skill_folder);
        const book = await readSkillFolder(absoluteFolder);
        return [entry.slug, book] as const;
      } catch (err) {
        console.warn(
          `[explorer] skipping manifest entry "${entry.slug}": ${(err as Error).message}`
        );
        return null;
      }
    })
  );

  const preloadedBooks: Record<string, BookData> = Object.fromEntries(
    preloadedEntries.filter((e): e is [string, BookData] => e !== null)
  );

  return (
    <ExplorerClient manifest={manifest} preloadedBooks={preloadedBooks} />
  );
}
