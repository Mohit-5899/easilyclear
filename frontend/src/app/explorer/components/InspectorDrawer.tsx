"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  ArrowLeft,
  ArrowRight,
  Hash,
  BookOpen,
  ArrowsOutLineVertical,
  TreeStructure,
  CaretRight,
  FileText,
} from "@phosphor-icons/react";
import type { BookData, TreeNode } from "@/lib/types";
import { findNodeById, getSiblings } from "@/lib/tree-utils";

interface InspectorDrawerProps {
  book: BookData | null;
  selectedNodeId: string | null;
  onClose: () => void;
  onNavigate: (nodeId: string) => void;
}

export function InspectorDrawer({
  book,
  selectedNodeId,
  onClose,
  onNavigate,
}: InspectorDrawerProps) {
  const isOpen = !!selectedNodeId && !!book;

  const result = book && selectedNodeId ? findNodeById(book.structure, selectedNodeId) : null;
  const node = result?.node ?? null;
  const path = result?.path ?? [];
  const depth = path.length;

  const siblings = book && selectedNodeId ? getSiblings(book.structure, selectedNodeId) : [];
  const currentIndex = node ? siblings.findIndex((s) => s.node_id === node.node_id) : -1;
  const prevSibling = currentIndex > 0 ? siblings[currentIndex - 1] : null;
  const nextSibling = currentIndex >= 0 && currentIndex < siblings.length - 1 ? siblings[currentIndex + 1] : null;

  // Esc closes drawer
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && node && (
        <>
          {/* Scrim */}
          <motion.div
            key="scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
            className="pointer-events-auto absolute inset-0 z-40 bg-zinc-950/10 backdrop-blur-[2px]"
          />

          {/* Drawer */}
          <motion.aside
            key="drawer"
            initial={{ x: 460, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 460, opacity: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 32 }}
            className="pointer-events-auto absolute right-0 top-0 z-50 flex h-full w-[440px] max-w-[92vw] flex-col border-l border-slate-200 bg-white shadow-[-30px_0_60px_-20px_rgba(15,23,42,0.12)]"
          >
            {/* Header */}
            <header className="flex items-start justify-between gap-3 border-b border-slate-100 px-6 py-5">
              <div className="min-w-0 flex-1">
                <Breadcrumb path={path} current={node} onNavigate={onNavigate} />
                <h2 className="mt-2 text-xl font-semibold tracking-tight text-zinc-950 leading-snug">
                  {node.title}
                </h2>
              </div>
              <button
                onClick={onClose}
                aria-label="Close inspector"
                className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-slate-100 hover:text-zinc-950 active:scale-[0.94]"
              >
                <X size={14} weight="bold" />
              </button>
            </header>

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto px-6 py-5">
              <MetadataChips
                nodeId={node.node_id}
                depth={depth}
                startIndex={node.start_index}
                endIndex={node.end_index}
                childCount={node.nodes?.length ?? 0}
              />

              <section className="mt-5">
                <SectionLabel icon={<FileText size={11} />} label="Summary" />
                <p className="mt-2 text-sm leading-relaxed text-slate-700">
                  {node.summary}
                </p>
              </section>

              {book && (node.nodes?.length || path.length > 0) ? (
                <section className="mt-6">
                  <SectionLabel icon={<TreeStructure size={11} />} label="Neighborhood" />
                  <MiniNeighborhood
                    book={book}
                    node={node}
                    path={path}
                    onNavigate={onNavigate}
                  />
                </section>
              ) : null}
            </div>

            {/* Footer: sibling nav */}
            {siblings.length > 1 && (
              <footer className="flex items-stretch gap-2 border-t border-slate-100 p-3">
                <SiblingButton
                  direction="prev"
                  sibling={prevSibling}
                  onNavigate={onNavigate}
                />
                <SiblingButton
                  direction="next"
                  sibling={nextSibling}
                  onNavigate={onNavigate}
                />
              </footer>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function SectionLabel({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-slate-400">
      <span className="text-slate-400">{icon}</span>
      {label}
    </div>
  );
}

function Breadcrumb({
  path,
  current,
  onNavigate,
}: {
  path: TreeNode[];
  current: TreeNode;
  onNavigate: (id: string) => void;
}) {
  const segments = [...path, current];
  return (
    <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1">
      {segments.map((n, i) => {
        const isLast = i === segments.length - 1;
        return (
          <span key={n.node_id} className="flex items-center gap-1">
            {i > 0 && <CaretRight size={9} className="text-slate-300" />}
            {isLast ? (
              <span className="max-w-[180px] truncate text-[11px] font-medium text-zinc-950">
                {n.title}
              </span>
            ) : (
              <button
                onClick={() => onNavigate(n.node_id)}
                className="max-w-[140px] truncate text-[11px] text-slate-500 transition-colors hover:text-emerald-600"
              >
                {n.title}
              </button>
            )}
          </span>
        );
      })}
    </nav>
  );
}

function MetadataChips({
  nodeId,
  depth,
  startIndex,
  endIndex,
  childCount,
}: {
  nodeId: string;
  depth: number;
  startIndex: number;
  endIndex: number;
  childCount: number;
}) {
  const pageRange = startIndex === endIndex ? `p${startIndex}` : `p${startIndex}–${endIndex}`;
  return (
    <div className="flex flex-wrap gap-1.5">
      <Chip icon={<Hash size={11} />}>
        <span className="font-mono">{nodeId}</span>
      </Chip>
      <Chip icon={<BookOpen size={11} />}>
        <span className="font-mono">{pageRange}</span>
      </Chip>
      <Chip icon={<ArrowsOutLineVertical size={11} />}>
        depth {depth}
      </Chip>
      {childCount > 0 && (
        <Chip icon={<TreeStructure size={11} />} tone="emerald">
          {childCount} {childCount === 1 ? "child" : "children"}
        </Chip>
      )}
    </div>
  );
}

function Chip({
  children,
  icon,
  tone = "slate",
}: {
  children: React.ReactNode;
  icon?: React.ReactNode;
  tone?: "slate" | "emerald";
}) {
  const styles =
    tone === "emerald"
      ? "bg-emerald-50 text-emerald-700"
      : "bg-slate-100 text-slate-600";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] ${styles}`}
    >
      {icon}
      {children}
    </span>
  );
}

function SiblingButton({
  direction,
  sibling,
  onNavigate,
}: {
  direction: "prev" | "next";
  sibling: TreeNode | null;
  onNavigate: (id: string) => void;
}) {
  const icon = direction === "prev" ? <ArrowLeft size={12} /> : <ArrowRight size={12} />;
  const label = direction === "prev" ? "Previous" : "Next";
  const alignment = direction === "prev" ? "text-left" : "text-right";
  const flexDir = direction === "prev" ? "" : "flex-row-reverse";

  return (
    <button
      onClick={() => sibling && onNavigate(sibling.node_id)}
      disabled={!sibling}
      className={`flex flex-1 items-center gap-2 rounded-xl border border-slate-100 px-3 py-2 transition-colors hover:bg-slate-50 active:-translate-y-[1px] disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent ${flexDir}`}
    >
      <span className="flex-shrink-0 text-slate-400">{icon}</span>
      <div className={`min-w-0 flex-1 ${alignment}`}>
        <p className="text-[9px] uppercase tracking-wider text-slate-400">{label}</p>
        <p className="truncate text-xs text-zinc-950">
          {sibling?.title ?? "—"}
        </p>
      </div>
    </button>
  );
}

function MiniNeighborhood({
  book,
  node,
  path,
  onNavigate,
}: {
  book: BookData;
  node: TreeNode;
  path: TreeNode[];
  onNavigate: (id: string) => void;
}) {
  const parent = path.length > 0 ? path[path.length - 1] : null;
  const siblings = getSiblings(book.structure, node.node_id).filter(
    (s) => s.node_id !== node.node_id
  );
  const allSiblings = getSiblings(book.structure, node.node_id);
  const idx = allSiblings.findIndex((s) => s.node_id === node.node_id);
  const leftSibs = allSiblings.slice(Math.max(0, idx - 1), idx);
  const rightSibs = allSiblings.slice(idx + 1, idx + 2);
  const children = (node.nodes ?? []).slice(0, 4);

  if (!parent && children.length === 0 && siblings.length === 0) return null;

  return (
    <div className="mt-2 space-y-2.5">
      {parent && (
        <NeighborGroup label="Parent">
          <NeighborButton node={parent} onClick={() => onNavigate(parent.node_id)} />
        </NeighborGroup>
      )}
      {(leftSibs.length > 0 || rightSibs.length > 0) && (
        <NeighborGroup label="Siblings">
          <div className="flex flex-wrap gap-1.5">
            {leftSibs.map((s) => (
              <NeighborButton
                key={s.node_id}
                node={s}
                onClick={() => onNavigate(s.node_id)}
                compact
              />
            ))}
            {rightSibs.map((s) => (
              <NeighborButton
                key={s.node_id}
                node={s}
                onClick={() => onNavigate(s.node_id)}
                compact
              />
            ))}
          </div>
        </NeighborGroup>
      )}
      {children.length > 0 && (
        <NeighborGroup label={`Children (${node.nodes?.length ?? 0})`}>
          <div className="space-y-1">
            {children.map((c) => (
              <NeighborButton key={c.node_id} node={c} onClick={() => onNavigate(c.node_id)} />
            ))}
          </div>
        </NeighborGroup>
      )}
    </div>
  );
}

function NeighborGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[9px] uppercase tracking-wider text-slate-400">{label}</p>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function NeighborButton({
  node,
  onClick,
  compact,
}: {
  node: TreeNode;
  onClick: () => void;
  compact?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`${compact ? "inline-flex" : "flex w-full"} items-center gap-2 rounded-lg border border-slate-100 bg-white px-2.5 py-1.5 text-left transition-colors hover:border-emerald-200 hover:bg-emerald-50/40 active:scale-[0.98]`}
    >
      <span className="truncate text-xs text-zinc-950">{node.title}</span>
      <span className="flex-shrink-0 font-mono text-[9px] text-slate-400">
        {node.start_index === node.end_index
          ? `p${node.start_index}`
          : `p${node.start_index}–${node.end_index}`}
      </span>
    </button>
  );
}
