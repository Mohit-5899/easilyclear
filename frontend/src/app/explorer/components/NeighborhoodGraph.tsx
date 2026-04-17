"use client";

import React, { useMemo } from "react";
import { motion } from "framer-motion";
import type { TreeNode } from "@/lib/types";
import { getParent, getSiblings, getChildren } from "@/lib/tree-utils";

interface NeighborhoodGraphProps {
  structure: TreeNode[];
  node: TreeNode;
  onNavigate: (id: string) => void;
}

const ACTIVE_COLOR = "#10b981";
const NODE_COLOR = "#e2e8f0";
const TEXT_COLOR = "#334155";
const LINE_COLOR = "#cbd5e1";

interface GraphNode {
  id: string;
  label: string;
  x: number;
  y: number;
  isActive: boolean;
}

interface GraphLine {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

const PulsingCircle = React.memo(function PulsingCircle({
  cx,
  cy,
}: {
  cx: number;
  cy: number;
}) {
  return (
    <motion.circle
      cx={cx}
      cy={cy}
      r={20}
      fill={ACTIVE_COLOR}
      animate={{ scale: [1, 1.08, 1] }}
      transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
    />
  );
});

export function NeighborhoodGraph({
  structure,
  node,
  onNavigate,
}: NeighborhoodGraphProps) {
  const { graphNodes, lines, svgHeight } = useMemo(() => {
    const parent = getParent(structure, node.node_id);
    const allSiblings = getSiblings(structure, node.node_id);
    const siblings = allSiblings.filter((s) => s.node_id !== node.node_id);
    const children = getChildren(node);

    const nodeIndex = allSiblings.findIndex((s) => s.node_id === node.node_id);
    const leftSiblings = allSiblings.filter((_, i) => i < nodeIndex).slice(-2);
    const rightSiblings = allSiblings.filter((_, i) => i > nodeIndex).slice(0, 2);

    const WIDTH = 400;
    const CX = WIDTH / 2;
    let currentY = 30;

    const nodes: GraphNode[] = [];
    const linesList: GraphLine[] = [];

    if (parent) {
      nodes.push({
        id: parent.node_id,
        label: parent.title,
        x: CX,
        y: currentY,
        isActive: false,
      });
      currentY += 70;
    }

    const sibRow = [...leftSiblings, node, ...rightSiblings];
    const sibSpacing = Math.min(90, WIDTH / (sibRow.length + 1));
    const sibStartX = CX - ((sibRow.length - 1) * sibSpacing) / 2;
    const activeY = currentY;

    sibRow.forEach((s, i) => {
      nodes.push({
        id: s.node_id,
        label: s.title,
        x: sibStartX + i * sibSpacing,
        y: currentY,
        isActive: s.node_id === node.node_id,
      });
    });

    if (parent) {
      const parentNode = nodes[0];
      sibRow.forEach((_, i) => {
        linesList.push({
          x1: parentNode.x,
          y1: parentNode.y + 20,
          x2: sibStartX + i * sibSpacing,
          y2: currentY - 20,
        });
      });
    }

    currentY += 70;

    if (children.length > 0) {
      const displayChildren = children.slice(0, 5);
      const childSpacing = Math.min(80, WIDTH / (displayChildren.length + 1));
      const childStartX = CX - ((displayChildren.length - 1) * childSpacing) / 2;

      const activeNode = nodes.find((n) => n.isActive)!;

      displayChildren.forEach((c, i) => {
        const cx = childStartX + i * childSpacing;
        nodes.push({
          id: c.node_id,
          label: c.title,
          x: cx,
          y: currentY,
          isActive: false,
        });
        linesList.push({
          x1: activeNode.x,
          y1: activeY + 20,
          x2: cx,
          y2: currentY - 20,
        });
      });
      currentY += 30;
    }

    return {
      graphNodes: nodes,
      lines: linesList,
      svgHeight: currentY + 20,
    };
  }, [structure, node]);

  const parent = getParent(structure, node.node_id);
  const children = getChildren(node);
  if (!parent && children.length === 0) return null;

  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50/30 p-4">
      <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-3">
        Neighborhood
      </p>
      <svg
        viewBox={`0 0 400 ${svgHeight}`}
        className="w-full"
        style={{ maxHeight: "280px" }}
      >
        {lines.map((line, i) => (
          <line
            key={i}
            x1={line.x1}
            y1={line.y1}
            x2={line.x2}
            y2={line.y2}
            stroke={LINE_COLOR}
            strokeWidth={1.5}
          />
        ))}

        {graphNodes.map((gn) => (
          <g
            key={gn.id}
            className="cursor-pointer"
            onClick={() => onNavigate(gn.id)}
          >
            {gn.isActive ? (
              <PulsingCircle cx={gn.x} cy={gn.y} />
            ) : (
              <motion.circle
                cx={gn.x}
                cy={gn.y}
                r={16}
                fill={NODE_COLOR}
                whileHover={{ scale: 1.2, fill: ACTIVE_COLOR }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
              />
            )}
            <title>{gn.label}</title>
            <text
              x={gn.x}
              y={gn.y + 32}
              textAnchor="middle"
              fill={TEXT_COLOR}
              fontSize={9}
              fontFamily="var(--font-geist-sans)"
              className="pointer-events-none"
            >
              {gn.label.length > 18 ? `${gn.label.slice(0, 16)}...` : gn.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
