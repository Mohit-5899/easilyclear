"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  computeRadialLayout,
  getLaidOutAncestorIds,
  nodeRadius,
  type LaidOutNode,
} from "@/lib/radial-layout";
import type { BookData } from "@/lib/types";

interface KnowledgeMapProps {
  book: BookData;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
  onRegisterViewport?: (api: ViewportApi) => void;
}

export interface ViewportApi {
  zoomIn: () => void;
  zoomOut: () => void;
  reset: () => void;
  fitToScreen: () => void;
  focusNode: (nodeId: string) => void;
}

const MIN_SCALE = 0.3;
const MAX_SCALE = 3;
const ZOOM_STEP = 1.2;

export function KnowledgeMap({
  book,
  selectedNodeId,
  onSelectNode,
  onRegisterViewport,
}: KnowledgeMapProps) {
  const layout = useMemo(
    () => computeRadialLayout(book.structure, book.doc_name),
    [book]
  );

  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 800, height: 800 });
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const dragStateRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null);

  // Track container size
  useEffect(() => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    const update = () => {
      const rect = el.getBoundingClientRect();
      setSize({ width: rect.width, height: rect.height });
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const centerX = size.width / 2;
  const centerY = size.height / 2;

  // Fit-to-screen
  const fitToScreen = useCallback(() => {
    const diameter = layout.maxRadius * 2 + 120;
    const fitScale = Math.min(
      size.width / diameter,
      size.height / diameter,
      1
    );
    setTransform({ x: 0, y: 0, scale: Math.max(MIN_SCALE, fitScale) });
  }, [layout.maxRadius, size.width, size.height]);

  // Fit on first layout + book change
  useEffect(() => {
    fitToScreen();
  }, [fitToScreen]);

  const zoomIn = useCallback(() => {
    setTransform((t) => ({
      ...t,
      scale: Math.min(MAX_SCALE, t.scale * ZOOM_STEP),
    }));
  }, []);

  const zoomOut = useCallback(() => {
    setTransform((t) => ({
      ...t,
      scale: Math.max(MIN_SCALE, t.scale / ZOOM_STEP),
    }));
  }, []);

  const reset = useCallback(() => {
    fitToScreen();
  }, [fitToScreen]);

  const focusNode = useCallback(
    (nodeId: string) => {
      const target = layout.nodes.find((n) => n.node_id === nodeId);
      if (!target) return;
      const nextScale = 1.2;
      setTransform({
        x: -target.x * nextScale,
        y: -target.y * nextScale,
        scale: nextScale,
      });
    },
    [layout.nodes]
  );

  // Register API with parent
  useEffect(() => {
    onRegisterViewport?.({ zoomIn, zoomOut, reset, fitToScreen, focusNode });
  }, [zoomIn, zoomOut, reset, fitToScreen, focusNode, onRegisterViewport]);

  // Wheel zoom (centered on cursor)
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      const direction = e.deltaY < 0 ? 1 : -1;
      const factor = direction > 0 ? ZOOM_STEP : 1 / ZOOM_STEP;
      setTransform((t) => {
        const nextScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, t.scale * factor));
        if (nextScale === t.scale) return t;
        const rect = containerRef.current?.getBoundingClientRect();
        if (!rect) return { ...t, scale: nextScale };
        const cursorX = e.clientX - rect.left - centerX;
        const cursorY = e.clientY - rect.top - centerY;
        const ratio = nextScale / t.scale;
        return {
          scale: nextScale,
          x: cursorX - (cursorX - t.x) * ratio,
          y: cursorY - (cursorY - t.y) * ratio,
        };
      });
    },
    [centerX, centerY]
  );

  // Drag to pan
  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (e.button !== 0) return;
      // Don't start drag when clicking on a node (nodes stopPropagation)
      (e.target as Element).setPointerCapture(e.pointerId);
      dragStateRef.current = {
        startX: e.clientX,
        startY: e.clientY,
        origX: transform.x,
        origY: transform.y,
      };
      setDragging(true);
    },
    [transform.x, transform.y]
  );

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    const state = dragStateRef.current;
    if (!state) return;
    const dx = e.clientX - state.startX;
    const dy = e.clientY - state.startY;
    setTransform((t) => ({ ...t, x: state.origX + dx, y: state.origY + dy }));
  }, []);

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    (e.target as Element).releasePointerCapture?.(e.pointerId);
    dragStateRef.current = null;
    setDragging(false);
  }, []);

  const ancestorIds = useMemo(() => {
    if (!selectedNodeId) return new Set<string>();
    const target = layout.nodes.find((n) => n.node_id === selectedNodeId);
    if (!target) return new Set<string>();
    return getLaidOutAncestorIds(layout, target.id);
  }, [layout, selectedNodeId]);

  const selectedLaidOutId = useMemo(() => {
    if (!selectedNodeId) return null;
    return layout.nodes.find((n) => n.node_id === selectedNodeId)?.id ?? null;
  }, [layout.nodes, selectedNodeId]);

  const handleBackgroundClick = useCallback(() => {
    // Click on empty canvas clears selection — only when not dragging
    if (!dragStateRef.current) onSelectNode(null);
  }, [onSelectNode]);

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full overflow-hidden bg-[#fafafa]"
      style={{
        backgroundImage:
          "radial-gradient(circle at 1px 1px, rgba(15,23,42,0.06) 1px, transparent 0)",
        backgroundSize: "24px 24px",
        cursor: dragging ? "grabbing" : "grab",
      }}
      onWheel={handleWheel}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
    >
      <svg
        width={size.width}
        height={size.height}
        className="pointer-events-none absolute inset-0 select-none"
      >
        <g
          transform={`translate(${centerX + transform.x}, ${centerY + transform.y}) scale(${transform.scale})`}
        >
          {/* Edges */}
          <g className="pointer-events-none">
            {layout.edges.map((edge) => {
              const isOnPath =
                ancestorIds.has(edge.targetId) ||
                edge.targetId === selectedLaidOutId;
              return (
                <path
                  key={edge.id}
                  d={edge.path}
                  fill="none"
                  stroke={isOnPath ? "#10b981" : "#cbd5e1"}
                  strokeWidth={isOnPath ? 1.5 : 0.8}
                  strokeOpacity={isOnPath ? 0.9 : 0.5}
                  style={{ transition: "stroke 180ms, stroke-width 180ms" }}
                />
              );
            })}
          </g>

          {/* Nodes */}
          <g>
            {layout.nodes.map((node) => (
              <NodeCircle
                key={node.id}
                node={node}
                isSelected={node.id === selectedLaidOutId}
                isAncestor={ancestorIds.has(node.id)}
                isHovered={hoverId === node.id}
                onClick={() => {
                  if (!node.isSynthetic) onSelectNode(node.node_id);
                }}
                onHover={(hovering) => setHoverId(hovering ? node.id : null)}
                scale={transform.scale}
              />
            ))}
          </g>
        </g>
      </svg>

      {/* Transparent overlay to catch background clicks */}
      <div
        className="absolute inset-0"
        onClick={handleBackgroundClick}
        style={{ pointerEvents: dragging ? "none" : "auto", zIndex: -1 }}
      />
    </div>
  );
}

interface NodeCircleProps {
  node: LaidOutNode;
  isSelected: boolean;
  isAncestor: boolean;
  isHovered: boolean;
  onClick: () => void;
  onHover: (hovering: boolean) => void;
  scale: number;
}

function NodeCircle({
  node,
  isSelected,
  isAncestor,
  isHovered,
  onClick,
  onHover,
  scale,
}: NodeCircleProps) {
  const r = node.isSynthetic ? 14 : nodeRadius(node.pageCount);

  const fill = node.isSynthetic
    ? "#0f172a"
    : isSelected
      ? "#10b981"
      : isAncestor
        ? "#a7f3d0"
        : "#e2e8f0";

  const stroke = isSelected
    ? "#047857"
    : isHovered
      ? "#10b981"
      : isAncestor
        ? "#10b981"
        : "transparent";

  const showLabel = isSelected || isHovered || node.depth <= 1 || scale > 1.3;
  const labelOpacity = showLabel ? 1 : 0;

  // Radial label angle (avoid upside-down text)
  const degrees = (node.angle * 180) / Math.PI - 90;
  const flip = degrees > 90 && degrees < 270;
  const labelTransform = flip
    ? `rotate(${degrees + 180} ${node.x} ${node.y}) translate(${-(r + 6)} 0)`
    : `rotate(${degrees} ${node.x} ${node.y}) translate(${r + 6} 0)`;
  const textAnchor = flip ? "end" : "start";

  return (
    <g
      style={{ cursor: node.isSynthetic ? "default" : "pointer", pointerEvents: "auto" }}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
    >
      {isSelected && (
        <motion.circle
          cx={node.x}
          cy={node.y}
          r={r + 4}
          fill="none"
          stroke="#10b981"
          strokeWidth={1.5}
          animate={{ scale: [1, 1.25, 1], opacity: [0.6, 0, 0.6] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      <motion.circle
        cx={node.x}
        cy={node.y}
        r={r}
        fill={fill}
        stroke={stroke}
        strokeWidth={isSelected || isHovered ? 2 : 1}
        animate={{ scale: isHovered && !isSelected ? 1.15 : 1 }}
        transition={{ type: "spring", stiffness: 300, damping: 22 }}
        style={{ transformOrigin: `${node.x}px ${node.y}px` }}
      />
      <text
        x={node.x}
        y={node.y}
        dy="0.32em"
        textAnchor={textAnchor}
        transform={node.isSynthetic ? undefined : labelTransform}
        fontSize={node.isSynthetic ? 11 : 10}
        fontFamily="var(--font-geist-sans)"
        fill={
          node.isSynthetic
            ? "#ffffff"
            : isSelected
              ? "#064e3b"
              : isAncestor
                ? "#065f46"
                : "#334155"
        }
        fontWeight={node.isSynthetic || isSelected ? 600 : 400}
        style={{
          opacity: node.isSynthetic ? 1 : labelOpacity,
          transition: "opacity 180ms",
          pointerEvents: "none",
          userSelect: "none",
        }}
      >
        {node.isSynthetic
          ? "BOOK"
          : node.title.length > 28
            ? `${node.title.slice(0, 26)}…`
            : node.title}
      </text>
    </g>
  );
}
