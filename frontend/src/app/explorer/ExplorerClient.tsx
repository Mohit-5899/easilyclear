"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpen } from "@phosphor-icons/react";
import type { BookData, ManifestEntry } from "@/lib/types";
import { getTreeStats } from "@/lib/tree-utils";
import { KnowledgeMap, type ViewportApi } from "./components/KnowledgeMap";
import { BrandPill } from "./components/BrandPill";
import { ZoomControls } from "./components/ZoomControls";
import { InspectorDrawer } from "./components/InspectorDrawer";

interface ExplorerClientProps {
  manifest: ManifestEntry[];
}

export function ExplorerClient({ manifest }: ExplorerClientProps) {
  const [selectedSlug, setSelectedSlug] = useState<string | null>(
    manifest[0]?.slug ?? null
  );
  const [bookData, setBookData] = useState<BookData | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const viewportRef = useRef<ViewportApi | null>(null);

  useEffect(() => {
    if (!selectedSlug) return;
    const entry = manifest.find((m) => m.slug === selectedSlug);
    if (!entry) return;

    setLoading(true);
    setSelectedNodeId(null);

    fetch(`/data/${entry.file}`)
      .then((res) => res.json())
      .then((data: BookData) => {
        setBookData(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [selectedSlug, manifest]);

  const registerViewport = useCallback((api: ViewportApi) => {
    viewportRef.current = api;
  }, []);

  const handleSelectNode = useCallback((nodeId: string | null) => {
    setSelectedNodeId(nodeId);
  }, []);

  const handleNavigate = useCallback((nodeId: string) => {
    setSelectedNodeId(nodeId);
    viewportRef.current?.focusNode(nodeId);
  }, []);

  const stats = bookData ? getTreeStats(bookData.structure) : null;
  const currentBook = manifest.find((m) => m.slug === selectedSlug) ?? null;

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden bg-[#fafafa]">
      {bookData && !loading && (
        <KnowledgeMap
          book={bookData}
          selectedNodeId={selectedNodeId}
          onSelectNode={handleSelectNode}
          onRegisterViewport={registerViewport}
        />
      )}

      {loading && <LoadingState />}
      {!loading && !bookData && <EmptyState />}

      <BrandPill
        books={manifest}
        selectedSlug={selectedSlug}
        currentBookName={currentBook?.name ?? null}
        currentScope={currentBook?.scope ?? null}
        stats={stats}
        onSelect={setSelectedSlug}
      />

      {bookData && !loading && (
        <ZoomControls
          onZoomIn={() => viewportRef.current?.zoomIn()}
          onZoomOut={() => viewportRef.current?.zoomOut()}
          onFit={() => viewportRef.current?.fitToScreen()}
          onReset={() => viewportRef.current?.reset()}
        />
      )}

      <InspectorDrawer
        book={bookData}
        selectedNodeId={selectedNodeId}
        onClose={() => setSelectedNodeId(null)}
        onNavigate={handleNavigate}
      />
    </div>
  );
}

function LoadingState() {
  return (
    <div className="absolute inset-0 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="h-12 w-12 animate-pulse rounded-full bg-emerald-100" />
        <p className="text-xs text-slate-400">Loading knowledge tree…</p>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="absolute inset-0 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3 text-center">
        <BookOpen size={48} weight="thin" className="text-slate-300" />
        <p className="text-sm text-slate-400">
          Select a book from the top-left pill to explore its knowledge tree
        </p>
      </div>
    </div>
  );
}
