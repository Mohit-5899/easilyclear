import { hierarchy, tree, type HierarchyNode } from "d3-hierarchy";
import { linkRadial } from "d3-shape";
import type { TreeNode } from "./types";

export interface LaidOutNode {
  id: string;
  title: string;
  node_id: string;
  depth: number;
  angle: number;
  radius: number;
  x: number;
  y: number;
  pageCount: number;
  startIndex: number;
  endIndex: number;
  summary: string;
  hasChildren: boolean;
  parentId: string | null;
  isSynthetic: boolean;
}

export interface LaidOutEdge {
  id: string;
  sourceId: string;
  targetId: string;
  path: string;
  sourceDepth: number;
}

export interface RadialLayout {
  nodes: LaidOutNode[];
  edges: LaidOutEdge[];
  maxRadius: number;
}

const SYNTHETIC_ROOT_ID = "__root__";

interface InternalNode {
  id: string;
  title: string;
  node_id: string;
  start_index: number;
  end_index: number;
  summary: string;
  nodes?: InternalNode[];
  isSynthetic: boolean;
}

function annotate(
  nodes: TreeNode[],
  parentKey: string = "root"
): InternalNode[] {
  return nodes.map((n, i) => ({
    id: `${parentKey}:${n.node_id}`,
    title: n.title,
    node_id: n.node_id,
    start_index: n.start_index,
    end_index: n.end_index,
    summary: n.summary,
    isSynthetic: false,
    nodes: n.nodes ? annotate(n.nodes, `${parentKey}:${n.node_id}`) : undefined,
  }));
}

export function computeRadialLayout(
  structure: TreeNode[],
  docName: string,
  radiusPerDepth: number = 180
): RadialLayout {
  const synthetic: InternalNode = {
    id: SYNTHETIC_ROOT_ID,
    title: docName,
    node_id: SYNTHETIC_ROOT_ID,
    start_index: 0,
    end_index: 0,
    summary: "",
    isSynthetic: true,
    nodes: annotate(structure),
  };

  const root = hierarchy<InternalNode>(synthetic, (d) => d.nodes);
  const maxDepth = root.height;
  const maxRadius = Math.max(1, maxDepth) * radiusPerDepth;

  const layout = tree<InternalNode>()
    .size([2 * Math.PI, maxRadius])
    .separation((a, b) => (a.parent === b.parent ? 1 : 1.4) / Math.max(a.depth, 1));

  layout(root);

  const nodes: LaidOutNode[] = [];
  const edges: LaidOutEdge[] = [];

  const linkGen = linkRadial<unknown, HierarchyNode<InternalNode>>()
    .angle((d) => (d as HierarchyNode<InternalNode> & { x: number }).x)
    .radius((d) => (d as HierarchyNode<InternalNode> & { y: number }).y);

  root.each((d) => {
    const n = d as HierarchyNode<InternalNode> & { x: number; y: number };
    const pageCount = n.data.isSynthetic
      ? 0
      : Math.max(1, n.data.end_index - n.data.start_index + 1);

    nodes.push({
      id: n.data.id,
      title: n.data.title,
      node_id: n.data.node_id,
      depth: n.depth,
      angle: n.x,
      radius: n.y,
      x: Math.cos(n.x - Math.PI / 2) * n.y,
      y: Math.sin(n.x - Math.PI / 2) * n.y,
      pageCount,
      startIndex: n.data.start_index,
      endIndex: n.data.end_index,
      summary: n.data.summary,
      hasChildren: !!(n.children && n.children.length > 0),
      parentId: n.parent ? (n.parent as HierarchyNode<InternalNode>).data.id : null,
      isSynthetic: n.data.isSynthetic,
    });

    if (n.parent) {
      const pathData = linkGen({ source: n.parent, target: n } as unknown as HierarchyNode<InternalNode>);
      edges.push({
        id: `${(n.parent as HierarchyNode<InternalNode>).data.id}->${n.data.id}`,
        sourceId: (n.parent as HierarchyNode<InternalNode>).data.id,
        targetId: n.data.id,
        path: pathData ?? "",
        sourceDepth: n.parent.depth,
      });
    }
  });

  return { nodes, edges, maxRadius };
}

export function findLaidOutNodeByNodeId(
  layout: RadialLayout,
  nodeId: string
): LaidOutNode | undefined {
  return layout.nodes.find((n) => !n.isSynthetic && n.node_id === nodeId);
}

export function getLaidOutAncestorIds(
  layout: RadialLayout,
  targetId: string
): Set<string> {
  const byId = new Map(layout.nodes.map((n) => [n.id, n]));
  const ids = new Set<string>();
  let current = byId.get(targetId);
  while (current && current.parentId) {
    ids.add(current.parentId);
    current = byId.get(current.parentId);
  }
  return ids;
}

export function nodeRadius(pageCount: number): number {
  if (pageCount <= 0) return 8;
  return Math.max(6, Math.min(24, 6 + Math.sqrt(pageCount) * 3));
}
