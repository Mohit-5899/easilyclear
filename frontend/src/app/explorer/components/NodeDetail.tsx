"use client";

import { motion, AnimatePresence } from "framer-motion";
import { BookOpen, TreeStructure, Hash, ArrowsOutLineVertical } from "@phosphor-icons/react";
import type { TreeNode } from "@/lib/types";

interface NodeDetailProps {
  node: TreeNode | null;
  depth: number;
  path: TreeNode[];
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <BookOpen size={48} weight="thin" className="text-slate-300 mb-4" />
      <p className="text-sm text-slate-400">
        Click a node in the tree to see its details
      </p>
    </div>
  );
}

export function NodeDetail({ node, depth, path: _path }: NodeDetailProps) {
  if (!node) return <EmptyState />;

  const childCount = node.nodes?.length ?? 0;
  const pageRange =
    node.start_index === node.end_index
      ? `Page ${node.start_index}`
      : `Pages ${node.start_index}\u2013${node.end_index}`;

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={node.node_id}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ type: "spring", stiffness: 300, damping: 25 }}
        className="space-y-5"
      >
        <div>
          <h2 className="text-2xl tracking-tight font-semibold text-zinc-950">
            {node.title}
          </h2>
          <div className="mt-2 flex flex-wrap gap-2.5">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-mono text-slate-600">
              <Hash size={12} />
              {node.node_id}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-mono text-slate-600">
              <BookOpen size={12} />
              {pageRange}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-mono text-slate-600">
              <ArrowsOutLineVertical size={12} />
              depth {depth}
            </span>
            {childCount > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-mono text-emerald-700">
                <TreeStructure size={12} />
                {childCount} {childCount === 1 ? "child" : "children"}
              </span>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-5">
          <p className="text-base text-slate-600 leading-relaxed max-w-[65ch]">
            {node.summary}
          </p>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
