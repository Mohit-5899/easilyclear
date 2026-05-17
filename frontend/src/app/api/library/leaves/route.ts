/**
 * GET /api/library/leaves
 *
 * Returns a flat list of every leaf node across every ingested book —
 * used by the /tests "New test" modal as a topic picker. Server-side
 * because we read the manifest + skill folders from disk.
 */

import { readFile } from "fs/promises";
import { join, resolve } from "path";

import { NextResponse } from "next/server";

import type { BookData, ManifestEntry, TreeNode } from "@/lib/types";
import { readSkillFolder } from "@/lib/skill-folder-reader";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface LeafOption {
  book_slug: string;
  book_name: string;
  node_id: string;
  title: string;
  path: string; // human-readable breadcrumb e.g. "Climate › Monsoon"
}

function collectLeaves(
  nodes: TreeNode[],
  ancestors: string[],
  bookSlug: string,
  bookName: string,
  out: LeafOption[],
): void {
  for (const n of nodes) {
    const childPath = [...ancestors, n.title];
    const children = (n as TreeNode & { nodes?: TreeNode[] }).nodes ?? [];
    if (children.length === 0) {
      out.push({
        book_slug: bookSlug,
        book_name: bookName,
        node_id: n.node_id,
        title: n.title,
        path: childPath.join(" › "),
      });
    } else {
      collectLeaves(children, childPath, bookSlug, bookName, out);
    }
  }
}

export async function GET() {
  const manifestPath = join(process.cwd(), "public", "data", "manifest.json");
  let manifest: ManifestEntry[];
  try {
    manifest = JSON.parse(await readFile(manifestPath, "utf-8"));
  } catch {
    return NextResponse.json([] as LeafOption[]);
  }

  const projectRoot = process.cwd();
  const out: LeafOption[] = [];

  for (const entry of manifest) {
    if (!entry.skill_folder) continue;
    let book: BookData;
    try {
      book = await readSkillFolder(resolve(projectRoot, entry.skill_folder));
    } catch {
      continue;
    }
    // Skip the synthetic root — its title duplicates the subject name in
    // the topic-picker breadcrumb. Start at the root's children so `path`
    // reads <chapter> › <leaf> only.
    const subjectChildren =
      (book.structure[0] as TreeNode & { nodes?: TreeNode[] })?.nodes ?? book.structure;
    collectLeaves(subjectChildren, [], entry.slug, entry.name ?? entry.slug, out);
  }

  return NextResponse.json(out);
}
