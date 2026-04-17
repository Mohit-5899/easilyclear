import type { TreeNode, NodeWithPath, TreeStats } from "./types";

/**
 * Find a node by ID and return it with its ancestor path.
 * Returns null if not found.
 */
export function findNodeById(
  structure: TreeNode[],
  id: string,
  path: TreeNode[] = []
): NodeWithPath | null {
  for (const node of structure) {
    if (node.node_id === id) {
      return { node, path };
    }
    if (node.nodes) {
      const found = findNodeById(node.nodes, id, [...path, node]);
      if (found) return found;
    }
  }
  return null;
}

/**
 * Get the parent node of a given node ID.
 * Returns null if the node is at the root level.
 */
export function getParent(
  structure: TreeNode[],
  id: string
): TreeNode | null {
  const result = findNodeById(structure, id);
  if (!result || result.path.length === 0) return null;
  return result.path[result.path.length - 1];
}

/**
 * Get sibling nodes (nodes at the same level, including the node itself).
 */
export function getSiblings(
  structure: TreeNode[],
  id: string
): TreeNode[] {
  const parent = getParent(structure, id);
  if (!parent) {
    return structure;
  }
  return parent.nodes ?? [];
}

/**
 * Get direct children of a node.
 */
export function getChildren(node: TreeNode): TreeNode[] {
  return node.nodes ?? [];
}

/**
 * Flatten the tree into a list with depth metadata.
 */
export function flattenTree(
  structure: TreeNode[],
  depth: number = 0
): Array<{ node: TreeNode; depth: number }> {
  const result: Array<{ node: TreeNode; depth: number }> = [];
  for (const node of structure) {
    result.push({ node, depth });
    if (node.nodes) {
      result.push(...flattenTree(node.nodes, depth + 1));
    }
  }
  return result;
}

/**
 * Compute aggregate stats for a tree structure.
 */
export function getTreeStats(structure: TreeNode[]): TreeStats {
  let totalNodes = 0;
  let maxDepth = 0;
  let minPage = Infinity;
  let maxPage = -Infinity;

  function walk(nodes: TreeNode[], depth: number) {
    for (const node of nodes) {
      totalNodes++;
      if (depth > maxDepth) maxDepth = depth;
      if (node.start_index < minPage) minPage = node.start_index;
      if (node.end_index > maxPage) maxPage = node.end_index;
      if (node.nodes) walk(node.nodes, depth + 1);
    }
  }

  walk(structure, 0);

  return {
    totalNodes,
    maxDepth,
    pageRange: [
      minPage === Infinity ? 0 : minPage,
      maxPage === -Infinity ? 0 : maxPage,
    ],
  };
}

/**
 * Collect all ancestor node IDs for a given node.
 * Used to auto-expand the tree when selecting a node externally.
 */
export function getAncestorIds(
  structure: TreeNode[],
  id: string
): string[] {
  const result = findNodeById(structure, id);
  if (!result) return [];
  return result.path.map((n) => n.node_id);
}
