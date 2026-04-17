"use client";

import { motion, AnimatePresence } from "framer-motion";
import { CaretRight } from "@phosphor-icons/react";
import type { TreeNode } from "@/lib/types";

interface NodeBreadcrumbProps {
  path: TreeNode[];
  current: TreeNode;
  onNavigate: (id: string) => void;
}

export function NodeBreadcrumb({ path, current, onNavigate }: NodeBreadcrumbProps) {
  const segments = [...path, current];

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1 flex-wrap">
      <AnimatePresence mode="popLayout">
        {segments.map((node, i) => {
          const isLast = i === segments.length - 1;
          return (
            <motion.span
              key={node.node_id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ type: "spring", stiffness: 300, damping: 25 }}
              className="flex items-center gap-1"
            >
              {i > 0 && <CaretRight size={10} className="text-slate-300" />}
              {isLast ? (
                <span className="text-sm font-medium text-zinc-950 truncate max-w-[200px]">
                  {node.title}
                </span>
              ) : (
                <button
                  onClick={() => onNavigate(node.node_id)}
                  className="text-sm text-slate-500 hover:text-emerald-600 transition-colors truncate max-w-[160px] active:-translate-y-[1px]"
                >
                  {node.title}
                </button>
              )}
            </motion.span>
          );
        })}
      </AnimatePresence>
    </nav>
  );
}
