"use client";

import { motion } from "framer-motion";
import type { TreeNode } from "@/lib/types";
import { TreeNodeItem } from "./TreeNode";

interface TreeNavigatorProps {
  structure: TreeNode[];
  selectedId: string | null;
  expandedIds: Set<string>;
  onSelect: (id: string) => void;
  onToggle: (id: string) => void;
}

const listVariants = {
  visible: {
    transition: { staggerChildren: 0.03 },
  },
  hidden: {},
};

const itemVariants = {
  visible: { opacity: 1, x: 0 },
  hidden: { opacity: 0, x: -12 },
};

export function TreeNavigator({
  structure,
  selectedId,
  expandedIds,
  onSelect,
  onToggle,
}: TreeNavigatorProps) {
  return (
    <motion.div
      role="tree"
      aria-label="Book structure"
      initial="hidden"
      animate="visible"
      variants={listVariants}
      className="space-y-0.5 py-2"
    >
      {structure.map((node) => (
        <motion.div key={node.node_id} variants={itemVariants}>
          <TreeNodeItem
            node={node}
            depth={0}
            selectedId={selectedId}
            expandedIds={expandedIds}
            onSelect={onSelect}
            onToggle={onToggle}
          />
        </motion.div>
      ))}
    </motion.div>
  );
}
