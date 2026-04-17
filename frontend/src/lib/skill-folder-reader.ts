import { readFile, readdir } from "fs/promises";
import { join } from "path";
import matter from "gray-matter";
import type { BookData, TreeNode } from "./types";

/**
 * Server-side reader that walks a V2 skill folder and returns a BookData
 * shape compatible with the existing radial explorer.
 *
 * Expected folder layout:
 *   <root>/
 *     SKILL.md                            <- book metadata + root body
 *     01-<chapter-slug>/
 *       SKILL.md                          <- chapter metadata + chapter body
 *       01-<leaf-slug>.md                 <- leaf metadata + leaf body
 *       02-<leaf-slug>.md
 *     02-<chapter-slug>/
 *       ...
 */

interface ParsedMd {
  data: Record<string, unknown>;
  body: string;
}

async function parseMd(filePath: string): Promise<ParsedMd> {
  const raw = await readFile(filePath, "utf-8");
  const parsed = matter(raw);
  return {
    data: parsed.data as Record<string, unknown>,
    body: parsed.content.trim(),
  };
}

function deriveIndices(data: Record<string, unknown>): {
  start: number;
  end: number;
} {
  const pages = data.source_pages;
  if (Array.isArray(pages) && pages.length > 0) {
    const nums = pages.filter((p): p is number => typeof p === "number");
    if (nums.length > 0) {
      return { start: Math.min(...nums), end: Math.max(...nums) };
    }
  }
  return { start: 0, end: 0 };
}

function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function strArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((v): v is string => typeof v === "string");
}

function getNumericPrefix(name: string): number {
  const match = name.match(/^(\d+)-/);
  return match ? parseInt(match[1], 10) : Number.MAX_SAFE_INTEGER;
}

function sortByNumericPrefix<T extends { name: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    const diff = getNumericPrefix(a.name) - getNumericPrefix(b.name);
    if (diff !== 0) return diff;
    return a.name.localeCompare(b.name);
  });
}

interface DirEntry {
  name: string;
  isDir: boolean;
}

async function listEntries(folderPath: string): Promise<DirEntry[]> {
  const dirents = await readdir(folderPath, { withFileTypes: true });
  return dirents.map((d) => ({
    name: d.name,
    isDir: d.isDirectory(),
  }));
}

async function buildLeafNode(filePath: string): Promise<TreeNode> {
  const { data, body } = await parseMd(filePath);
  const { start, end } = deriveIndices(data);
  return {
    title: str(data.name, "Untitled"),
    node_id: str(data.node_id, filePath),
    start_index: start,
    end_index: end,
    summary: str(data.description, ""),
    body: body.length > 0 ? body : null,
  };
}

async function buildChapterNode(folderPath: string): Promise<TreeNode> {
  const skillPath = join(folderPath, "SKILL.md");
  const { data, body } = await parseMd(skillPath);
  const { start, end } = deriveIndices(data);

  const entries = await listEntries(folderPath);
  const leafEntries = sortByNumericPrefix(
    entries.filter(
      (e) => !e.isDir && e.name.endsWith(".md") && e.name !== "SKILL.md"
    )
  );

  const leaves = await Promise.all(
    leafEntries.map((e) => buildLeafNode(join(folderPath, e.name)))
  );

  return {
    title: str(data.name, "Untitled Chapter"),
    node_id: str(data.node_id, folderPath),
    start_index: start,
    end_index: end,
    summary: str(data.description, ""),
    body: body.length > 0 ? body : null,
    nodes: leaves,
  };
}

/**
 * Walk a skill folder and return the BookData shape used by the explorer.
 */
export async function readSkillFolder(
  absoluteFolderPath: string
): Promise<BookData> {
  const rootSkillPath = join(absoluteFolderPath, "SKILL.md");
  const { data: rootData, body: rootBody } = await parseMd(rootSkillPath);

  const entries = await listEntries(absoluteFolderPath);
  const chapterDirs = sortByNumericPrefix(entries.filter((e) => e.isDir));

  const chapters = await Promise.all(
    chapterDirs.map((e) => buildChapterNode(join(absoluteFolderPath, e.name)))
  );

  // Compute book-level page range from chapter spans when available.
  const allStarts = chapters.map((c) => c.start_index).filter((n) => n > 0);
  const allEnds = chapters.map((c) => c.end_index).filter((n) => n > 0);
  const rootStart = allStarts.length > 0 ? Math.min(...allStarts) : 0;
  const rootEnd = allEnds.length > 0 ? Math.max(...allEnds) : 0;

  const rootNode: TreeNode = {
    title: str(rootData.name, "Untitled Book"),
    node_id: str(rootData.node_id, absoluteFolderPath),
    start_index: rootStart,
    end_index: rootEnd,
    summary: str(rootData.description, ""),
    body: rootBody.length > 0 ? rootBody : null,
    nodes: chapters,
  };

  const subjectScope = (() => {
    const raw = str(rootData.subject_scope, "pan_india");
    if (raw === "rajasthan" || raw === "pan_india" || raw === "world") {
      return raw;
    }
    return "pan_india";
  })();

  const book: BookData = {
    doc_name: str(rootData.name),
    book_slug: str(rootData.source_book) || str(rootData.book_slug),
    doc_description: str(rootData.description),
    source_url: str(rootData.source_url),
    source_authority: str(rootData.source_authority, "official"),
    source_publisher: str(rootData.source_publisher),
    language: str(rootData.language, "en"),
    subject: str(rootData.subject),
    subject_scope: subjectScope,
    exam_coverage: strArray(rootData.exam_coverage),
    ingested_at: str(rootData.ingested_at),
    cleaned_at: str(rootData.cleaned_at),
    cleanup_version: str(rootData.cleanup_version),
    cleaner_layers_applied: strArray(rootData.cleaner_layers_applied),
    pageindex_version: str(rootData.pageindex_version),
    llm_model_indexing: str(
      rootData.llm_model_indexing,
      str(rootData.ingestion_version)
    ),
    structure: [rootNode],
  };

  return book;
}
