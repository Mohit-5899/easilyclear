import { readFile } from "fs/promises";
import { join } from "path";
import type { ManifestEntry } from "@/lib/types";
import { ExplorerClient } from "./ExplorerClient";

export const metadata = {
  title: "Tree Explorer — Gemma Tutor",
  description: "Browse ingested knowledge tree structures",
};

export default async function ExplorerPage() {
  const manifestPath = join(process.cwd(), "public", "data", "manifest.json");
  const raw = await readFile(manifestPath, "utf-8");
  const manifest: ManifestEntry[] = JSON.parse(raw);

  return <ExplorerClient manifest={manifest} />;
}
