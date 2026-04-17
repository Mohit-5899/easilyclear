"use client";

import { useRef, useEffect } from "react";
import { motion, AnimatePresence, type Variants } from "framer-motion";
import { CaretRight } from "@phosphor-icons/react";
import type { TreeNode as TreeNodeType } from "@/lib/types";

interface TreeNodeProps {
  node: TreeNodeType;
  depth: number;
  selectedId: string | null;
  expandedIds: Set<string>;
  onSelect: (id: string) => void;
  onToggle: (id: string) => void;
}

const DEPTH_BORDER_COLORS = [
  "border-emerald-400",
  "border-emerald-300",
  "border-emerald-200",
  "border-emerald-100",
];

const childrenVariants: Variants = {
  open: {
    height: "auto",
    opacity: 1,
    transition: {
      height: { type: "spring", stiffness: 200, damping: 25 },
      opacity: { duration: 0.2 },
      staggerChildren: 0.04,
    },
  },
  closed: {
    height: 0,
    opacity: 0,
    transition: {
      height: { type: "spring", stiffness: 200, damping: 25 },
      opacity: { duration: 0.15 },
    },
  },
};

const itemVariants: Variants = {
  open: { opacity: 1, x: 0 },
  closed: { opacity: 0, x: -8 },
};

export function TreeNodeItem({
  node,
  depth,
  selectedId,
  expandedIds,
  onSelect,
  onToggle,
}: TreeNodeProps) {
  const ref = useRef<HTMLDivElement>(null);
  const isSelected = selectedId === node.node_id;
  const isExpanded = expandedIds.has(node.node_id);
  const hasChildren = node.nodes && node.nodes.length > 0;
  const borderColor = DEPTH_BORDER_COLORS[Math.min(depth, DEPTH_BORDER_COLORS.length - 1)];

  useEffect(() => {
    if (isSelected && ref.current) {
      ref.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [isSelected]);

  return (
    <motion.div variants={itemVariants}>
      <div
        ref={ref}
        role="treeitem"
        aria-selected={isSelected}
        aria-expanded={hasChildren ? isExpanded : undefined}
        className={`group flex items-center gap-2 cursor-pointer rounded-lg px-2 py-1.5 transition-colors active:scale-[0.98] ${
          isSelected
            ? `bg-emerald-50 border-l-2 ${borderColor}`
            : `hover:bg-slate-50 border-l-2 border-transparent`
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => onSelect(node.node_id)}
      >
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggle(node.node_id);
            }}
            className="flex-shrink-0 rounded p-0.5 hover:bg-slate-200/50 transition-colors"
            aria-label={isExpanded ? "Collapse" : "Expand"}
          >
            <motion.span
              animate={{ rotate: isExpanded ? 90 : 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 20 }}
              className="block"
            >
              <CaretRight size={12} weight="bold" className="text-slate-400" />
            </motion.span>
          </button>
        ) : (
          <span className="w-5" />
        )}

        <span
          className={`flex-1 truncate text-sm ${
            isSelected ? "font-medium text-zinc-950" : "text-slate-700 group-hover:text-zinc-950"
          }`}
        >
          {node.title}
        </span>

        <span className="flex-shrink-0 font-mono text-[10px] text-slate-300">
          {node.start_index === node.end_index
            ? `p${node.start_index}`
            : `p${node.start_index}-${node.end_index}`}
        </span>

        {hasChildren && (
          <span className="flex-shrink-0 rounded-full bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
            {node.nodes!.length}
          </span>
        )}
      </div>

      <AnimatePresence initial={false}>
        {hasChildren && isExpanded && (
          <motion.div
            key={`children-${node.node_id}`}
            initial="closed"
            animate="open"
            exit="closed"
            variants={childrenVariants}
            className="overflow-hidden"
          >
            {node.nodes!.map((child) => (
              <TreeNodeItem
                key={child.node_id}
                node={child}
                depth={depth + 1}
                selectedId={selectedId}
                expandedIds={expandedIds}
                onSelect={onSelect}
                onToggle={onToggle}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
