import { readFile } from "fs/promises";
import { join, resolve } from "path";

import { redirect } from "next/navigation";

import { ExplorerClient } from "@/app/explorer/ExplorerClient";
import type { BookData, ManifestEntry } from "@/lib/types";
import { readSkillFolder } from "@/lib/skill-folder-reader";

interface PageProps {
  params: Promise<{ subjectSlug: string }>;
}

export const metadata = {
  title: "Library — Gemma Tutor",
};

/**
 * Legacy slug aliases — old book-keyed URLs that pre-date the
 * subject-canonical refactor (spec 2026-05-04). When someone hits a
 * stale bookmark or shared link, redirect them to the right subject
 * rather than 404. Add new entries here as we migrate more sources.
 */
const LEGACY_SLUG_REDIRECTS: Record<string, string> = {
  springboard_rajasthan_geography: "rajasthan_geography",
  geography: "rajasthan_geography",
};

export default async function LibrarySubjectPage({ params }: PageProps) {
  const { subjectSlug } = await params;

  const aliased = LEGACY_SLUG_REDIRECTS[subjectSlug];
  if (aliased) {
    redirect(`/library/${aliased}`);
  }

  const manifestPath = join(process.cwd(), "public", "data", "manifest.json");
  const raw = await readFile(manifestPath, "utf-8");
  const manifest: ManifestEntry[] = JSON.parse(raw);

  const entry = manifest.find((m) => m.slug === subjectSlug);
  // Unknown slugs land back on the library index — friendlier than 404
  // for shared links from collaborators / old bookmarks.
  if (!entry || !entry.skill_folder) {
    redirect("/library");
  }

  const projectRoot = process.cwd();
  let book: BookData;
  try {
    book = await readSkillFolder(resolve(projectRoot, entry.skill_folder));
  } catch {
    redirect("/library");
  }

  return (
    <ExplorerClient
      manifest={[entry]}
      preloadedBooks={{ [subjectSlug]: book }}
    />
  );
}
