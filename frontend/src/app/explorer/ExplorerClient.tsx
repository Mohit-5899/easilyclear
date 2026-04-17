"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen } from "@phosphor-icons/react";
import type { BookData, ManifestEntry, TreeNode } from "@/lib/types";
import {
  findNodeById,
  getAncestorIds,
  getSiblings,
  getTreeStats,
} from "@/lib/tree-utils";
import { BookSelector } from "./components/BookSelector";
import { BookMetadata } from "./components/BookMetadata";
import { TreeNavigator } from "./components/TreeNavigator";
import { NodeBreadcrumb } from "./components/NodeBreadcrumb";
import { NodeDetail } from "./components/NodeDetail";
import { NeighborhoodGraph } from "./components/NeighborhoodGraph";
import { SiblingNav } from "./components/SiblingNav";
import { TreeSkeleton, DetailSkeleton } from "./components/SkeletonLoader";

interface ExplorerClientProps {
  manifest: ManifestEntry[];
}

export function ExplorerClient({ manifest }: ExplorerClientProps) {
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [bookData, setBookData] = useState<BookData | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!selectedSlug) return;
    const entry = manifest.find((m) => m.slug === selectedSlug);
    if (!entry) return;

    setLoading(true);
    setSelectedNodeId(null);
    setExpandedIds(new Set());

    fetch(`/data/${entry.file}`)
      .then((res) => res.json())
      .then((data: BookData) => {
        setBookData(data);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, [selectedSlug, manifest]);

  const navigateToNode = useCallback(
    (id: string) => {
      if (!bookData) return;
      setSelectedNodeId(id);
      const ancestorIds = getAncestorIds(bookData.structure, id);
      setExpandedIds((prev) => {
        const next = new Set(prev);
        for (const aid of ancestorIds) next.add(aid);
        next.add(id);
        return next;
      });
    },
    [bookData]
  );

  const toggleExpand = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectedResult =
    bookData && selectedNodeId
      ? findNodeById(bookData.structure, selectedNodeId)
      : null;
  const selectedNode = selectedResult?.node ?? null;
  const nodePath = selectedResult?.path ?? [];
  const nodeDepth = nodePath.length;
  const siblings =
    bookData && selectedNodeId
      ? getSiblings(bookData.structure, selectedNodeId)
      : [];
  const stats = bookData ? getTreeStats(bookData.structure) : null;

  return (
    <div className="flex min-h-[100dvh] bg-[#f9fafb]">
      <aside className="w-80 flex-shrink-0 border-r border-slate-200/50 bg-white overflow-y-auto">
        <div className="p-4 space-y-4">
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-zinc-950">
              Tree Explorer
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Browse ingested knowledge structures
            </p>
          </div>

          <BookSelector
            books={manifest}
            selectedSlug={selectedSlug}
            onSelect={setSelectedSlug}
          />

          {loading && <TreeSkeleton />}

          {bookData && !loading && stats && (
            <>
              <BookMetadata book={bookData} stats={stats} />
              <TreeNavigator
                structure={bookData.structure}
                selectedId={selectedNodeId}
                expandedIds={expandedIds}
                onSelect={navigateToNode}
                onToggle={toggleExpand}
              />
            </>
          )}
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-6">
          {loading && <DetailSkeleton />}

          {!loading && !bookData && (
            <div className="flex flex-col items-center justify-center py-32 text-center">
              <BookOpen size={56} weight="thin" className="text-slate-300 mb-4" />
              <p className="text-sm text-slate-400">
                Select a book to explore its knowledge tree
              </p>
            </div>
          )}

          {!loading && bookData && (
            <>
              {selectedNode && (
                <NodeBreadcrumb
                  path={nodePath}
                  current={selectedNode}
                  onNavigate={navigateToNode}
                />
              )}

              <NodeDetail
                node={selectedNode}
                depth={nodeDepth}
                path={nodePath}
              />

              {selectedNode && bookData && (
                <NeighborhoodGraph
                  structure={bookData.structure}
                  node={selectedNode}
                  onNavigate={navigateToNode}
                />
              )}

              {selectedNode && siblings.length > 1 && (
                <SiblingNav
                  siblings={siblings}
                  currentId={selectedNode.node_id}
                  onNavigate={navigateToNode}
                />
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
