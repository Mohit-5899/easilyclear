# Knowledge Tree Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `/explorer` route that lets users browse ingested book structures as interactive trees with node details, neighborhood graphs, and provenance metadata.

**Architecture:** Static JSON data served from `frontend/public/data/`. Single `ExplorerClient` client component owns all state. Pure utility functions for tree traversal. Leaf components for animation-heavy elements (neighborhood graph pulse).

**Tech Stack:** Next.js 16, React 19, Tailwind 4, framer-motion, @phosphor-icons/react, Geist + Geist Mono fonts (already configured in layout.tsx)

---

## File Structure

```
frontend/
  public/data/
    manifest.json                              # CREATE — book index
    ncert_class10_contemporary_india_2.json     # COPY from database/textbooks/
    springboard_rajasthan_geography_ras_pre_UNOFFICIAL.json  # COPY from database/textbooks/unofficial/
  src/
    lib/
      types.ts                                 # CREATE — TypeScript types for book data + tree nodes
      tree-utils.ts                            # CREATE — pure tree traversal functions
    app/
      explorer/
        page.tsx                               # CREATE — server component shell
        ExplorerClient.tsx                      # CREATE — main client component (state, layout)
        components/
          BookSelector.tsx                      # CREATE — dropdown for book selection
          BookMetadata.tsx                      # CREATE — provenance metadata card
          TreeNavigator.tsx                     # CREATE — collapsible tree container
          TreeNode.tsx                          # CREATE — recursive tree node (expand/collapse)
          NodeBreadcrumb.tsx                    # CREATE — clickable ancestor path
          NodeDetail.tsx                        # CREATE — selected node info card
          NeighborhoodGraph.tsx                 # CREATE — SVG mini-map of node neighborhood
          SiblingNav.tsx                        # CREATE — prev/next sibling buttons
          SkeletonLoader.tsx                    # CREATE — shimmer loading states
```

---

### Task 1: Install dependencies and copy static data

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/public/data/manifest.json`
- Copy: `frontend/public/data/ncert_class10_contemporary_india_2.json`
- Copy: `frontend/public/data/springboard_rajasthan_geography_ras_pre_UNOFFICIAL.json`

- [ ] **Step 1: Install framer-motion and phosphor-icons**

```bash
cd frontend && npm install framer-motion @phosphor-icons/react
```

- [ ] **Step 2: Create the public/data directory and copy book JSONs**

```bash
mkdir -p frontend/public/data
cp database/textbooks/ncert_class10_contemporary_india_2.json frontend/public/data/
cp database/textbooks/unofficial/springboard_rajasthan_geography_ras_pre_UNOFFICIAL.json frontend/public/data/
```

- [ ] **Step 3: Create manifest.json**

Create `frontend/public/data/manifest.json`:

```json
[
  {
    "slug": "ncert_class10_contemporary_india_2",
    "name": "Contemporary India II (NCERT Class 10 Geography)",
    "scope": "pan_india",
    "file": "ncert_class10_contemporary_india_2.json"
  },
  {
    "slug": "springboard_rajasthan_geography_ras_pre_UNOFFICIAL",
    "name": "Springboard Academy — Rajasthan Geography Notes (RAS Pre)",
    "scope": "rajasthan",
    "file": "springboard_rajasthan_geography_ras_pre_UNOFFICIAL.json"
  }
]
```

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/public/data/
git commit -m "chore: add framer-motion, phosphor-icons, static book data for explorer"
```

---

### Task 2: TypeScript types

**Files:**
- Create: `frontend/src/lib/types.ts`

- [ ] **Step 1: Create types.ts**

Create `frontend/src/lib/types.ts`:

```typescript
export interface TreeNode {
  title: string;
  node_id: string;
  start_index: number;
  end_index: number;
  summary: string;
  nodes?: TreeNode[];
}

export interface BookData {
  doc_name: string;
  book_slug: string;
  doc_description: string;
  source_url: string;
  source_authority: string;
  source_publisher: string;
  language: string;
  subject: string;
  subject_scope: "rajasthan" | "pan_india" | "world";
  exam_coverage: string[];
  ingested_at: string;
  cleaned_at: string;
  cleanup_version: string;
  cleaner_layers_applied: string[];
  pageindex_version: string;
  llm_model_indexing: string;
  structure: TreeNode[];
}

export interface ManifestEntry {
  slug: string;
  name: string;
  scope: string;
  file: string;
}

export interface TreeStats {
  totalNodes: number;
  maxDepth: number;
  pageRange: [number, number];
}

export interface NodeWithPath {
  node: TreeNode;
  path: TreeNode[];
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat: add TypeScript types for book data and tree nodes"
```

---

### Task 3: Tree utility functions

**Files:**
- Create: `frontend/src/lib/tree-utils.ts`

- [ ] **Step 1: Create tree-utils.ts**

Create `frontend/src/lib/tree-utils.ts`:

```typescript
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
    // Root level — siblings are the top-level structure
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/tree-utils.ts
git commit -m "feat: add pure tree traversal utility functions"
```

---

### Task 4: Skeleton loader component

**Files:**
- Create: `frontend/src/app/explorer/components/SkeletonLoader.tsx`

- [ ] **Step 1: Create SkeletonLoader.tsx**

Create `frontend/src/app/explorer/components/SkeletonLoader.tsx`:

```tsx
"use client";

export function TreeSkeleton() {
  return (
    <div className="space-y-3 p-4 animate-pulse">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3" style={{ paddingLeft: `${(i % 3) * 16}px` }}>
          <div className="h-4 w-4 rounded bg-slate-200" />
          <div className="h-4 rounded bg-slate-200" style={{ width: `${140 - (i % 3) * 20}px` }} />
          <div className="h-3 w-10 rounded bg-slate-100 ml-auto" />
        </div>
      ))}
    </div>
  );
}

export function DetailSkeleton() {
  return (
    <div className="space-y-6 p-6 animate-pulse">
      <div className="flex gap-2">
        <div className="h-4 w-16 rounded bg-slate-200" />
        <div className="h-4 w-4 rounded bg-slate-100" />
        <div className="h-4 w-24 rounded bg-slate-200" />
        <div className="h-4 w-4 rounded bg-slate-100" />
        <div className="h-4 w-20 rounded bg-slate-200" />
      </div>
      <div className="space-y-3">
        <div className="h-7 w-64 rounded bg-slate-200" />
        <div className="flex gap-3">
          <div className="h-5 w-20 rounded bg-slate-100" />
          <div className="h-5 w-16 rounded bg-slate-100" />
          <div className="h-5 w-24 rounded bg-slate-100" />
        </div>
      </div>
      <div className="space-y-2">
        <div className="h-4 w-full rounded bg-slate-100" />
        <div className="h-4 w-5/6 rounded bg-slate-100" />
        <div className="h-4 w-4/6 rounded bg-slate-100" />
        <div className="h-4 w-5/6 rounded bg-slate-100" />
      </div>
      <div className="h-48 w-full rounded-xl bg-slate-100" />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/explorer/components/SkeletonLoader.tsx
git commit -m "feat: add skeleton shimmer loaders for tree and detail panels"
```

---

### Task 5: BookSelector component

**Files:**
- Create: `frontend/src/app/explorer/components/BookSelector.tsx`

- [ ] **Step 1: Create BookSelector.tsx**

Create `frontend/src/app/explorer/components/BookSelector.tsx`:

```tsx
"use client";

import { CaretDown } from "@phosphor-icons/react";
import type { ManifestEntry } from "@/lib/types";

interface BookSelectorProps {
  books: ManifestEntry[];
  selectedSlug: string | null;
  onSelect: (slug: string) => void;
}

export function BookSelector({ books, selectedSlug, onSelect }: BookSelectorProps) {
  return (
    <div className="relative">
      <select
        value={selectedSlug ?? ""}
        onChange={(e) => onSelect(e.target.value)}
        className="w-full appearance-none rounded-xl border border-slate-200/50 bg-white px-4 py-3 pr-10 font-sans text-sm font-medium text-zinc-950 shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)] transition-colors hover:border-slate-300 focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-400/20"
      >
        <option value="" disabled>
          Select a book to explore
        </option>
        {books.map((book) => (
          <option key={book.slug} value={book.slug}>
            {book.name}
          </option>
        ))}
      </select>
      <CaretDown
        size={16}
        weight="bold"
        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/explorer/components/BookSelector.tsx
git commit -m "feat: add BookSelector dropdown component"
```

---

### Task 6: BookMetadata component

**Files:**
- Create: `frontend/src/app/explorer/components/BookMetadata.tsx`

- [ ] **Step 1: Create BookMetadata.tsx**

Create `frontend/src/app/explorer/components/BookMetadata.tsx`:

```tsx
"use client";

import {
  BookOpen,
  Buildings,
  GraduationCap,
  Funnel,
  Brain,
  Calendar,
  TreeStructure,
  CheckCircle,
} from "@phosphor-icons/react";
import type { BookData, TreeStats } from "@/lib/types";

interface BookMetadataProps {
  book: BookData;
  stats: TreeStats;
}

function ScopeBadge({ scope }: { scope: string }) {
  const isRajasthan = scope === "rajasthan";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        isRajasthan
          ? "bg-emerald-50 text-emerald-700"
          : "bg-slate-100 text-slate-600"
      }`}
    >
      {scope}
    </span>
  );
}

function MetadataRow({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <span className="mt-0.5 text-slate-400">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
          {label}
        </p>
        <div className="mt-0.5 text-sm text-zinc-950">{children}</div>
      </div>
    </div>
  );
}

export function BookMetadata({ book, stats }: BookMetadataProps) {
  const ingestedDate = new Date(book.ingested_at).toLocaleDateString("en-IN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div className="divide-y divide-slate-100 rounded-xl border border-slate-200/50 bg-white shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)]">
      <MetadataRow icon={<Buildings size={16} />} label="Publisher">
        <span className="font-medium">{book.source_publisher}</span>
        <span className="ml-2 text-xs text-slate-400">({book.source_authority})</span>
      </MetadataRow>

      <MetadataRow icon={<BookOpen size={16} />} label="Scope">
        <ScopeBadge scope={book.subject_scope} />
      </MetadataRow>

      <MetadataRow icon={<GraduationCap size={16} />} label="Exam Coverage">
        <div className="flex flex-wrap gap-1.5">
          {book.exam_coverage.map((exam) => (
            <span
              key={exam}
              className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
            >
              {exam}
            </span>
          ))}
        </div>
      </MetadataRow>

      <MetadataRow icon={<Funnel size={16} />} label="Cleaning Layers">
        <div className="flex items-center gap-1.5 flex-wrap">
          {book.cleaner_layers_applied.map((layer, i) => (
            <span key={layer} className="flex items-center gap-1">
              {i > 0 && <span className="text-slate-300 text-xs">&#8594;</span>}
              <CheckCircle size={12} weight="fill" className="text-emerald-500" />
              <span className="text-xs font-mono">{layer}</span>
            </span>
          ))}
        </div>
      </MetadataRow>

      <MetadataRow icon={<Brain size={16} />} label="LLM Model">
        <span className="font-mono text-xs">{book.llm_model_indexing}</span>
      </MetadataRow>

      <MetadataRow icon={<Calendar size={16} />} label="Ingested">
        {ingestedDate}
      </MetadataRow>

      <MetadataRow icon={<TreeStructure size={16} />} label="Stats">
        <div className="flex gap-4 font-mono text-xs">
          <span>
            <span className="text-zinc-950 font-semibold">{stats.totalNodes}</span>{" "}
            <span className="text-slate-400">nodes</span>
          </span>
          <span>
            <span className="text-zinc-950 font-semibold">{stats.maxDepth}</span>{" "}
            <span className="text-slate-400">depth</span>
          </span>
          <span>
            <span className="text-zinc-950 font-semibold">
              {stats.pageRange[0]}-{stats.pageRange[1]}
            </span>{" "}
            <span className="text-slate-400">pages</span>
          </span>
        </div>
      </MetadataRow>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/explorer/components/BookMetadata.tsx
git commit -m "feat: add BookMetadata provenance card with scope badges and pipeline visualization"
```

---

### Task 7: TreeNode and TreeNavigator components

**Files:**
- Create: `frontend/src/app/explorer/components/TreeNode.tsx`
- Create: `frontend/src/app/explorer/components/TreeNavigator.tsx`

- [ ] **Step 1: Create TreeNode.tsx**

Create `frontend/src/app/explorer/components/TreeNode.tsx`:

```tsx
"use client";

import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
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

const childrenVariants = {
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

const itemVariants = {
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
```

- [ ] **Step 2: Create TreeNavigator.tsx**

Create `frontend/src/app/explorer/components/TreeNavigator.tsx`:

```tsx
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
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/explorer/components/TreeNode.tsx frontend/src/app/explorer/components/TreeNavigator.tsx
git commit -m "feat: add TreeNode and TreeNavigator with spring expand/collapse animations"
```

---

### Task 8: NodeBreadcrumb component

**Files:**
- Create: `frontend/src/app/explorer/components/NodeBreadcrumb.tsx`

- [ ] **Step 1: Create NodeBreadcrumb.tsx**

Create `frontend/src/app/explorer/components/NodeBreadcrumb.tsx`:

```tsx
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/explorer/components/NodeBreadcrumb.tsx
git commit -m "feat: add NodeBreadcrumb with animated segment transitions"
```

---

### Task 9: NodeDetail component

**Files:**
- Create: `frontend/src/app/explorer/components/NodeDetail.tsx`

- [ ] **Step 1: Create NodeDetail.tsx**

Create `frontend/src/app/explorer/components/NodeDetail.tsx`:

```tsx
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

export function NodeDetail({ node, depth, path }: NodeDetailProps) {
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/explorer/components/NodeDetail.tsx
git commit -m "feat: add NodeDetail card with animated transitions and empty state"
```

---

### Task 10: NeighborhoodGraph component

**Files:**
- Create: `frontend/src/app/explorer/components/NeighborhoodGraph.tsx`

- [ ] **Step 1: Create NeighborhoodGraph.tsx**

Create `frontend/src/app/explorer/components/NeighborhoodGraph.tsx`:

```tsx
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

const ACTIVE_COLOR = "#10b981"; // emerald-500
const NODE_COLOR = "#e2e8f0"; // slate-200
const TEXT_COLOR = "#334155"; // slate-700
const LINE_COLOR = "#cbd5e1"; // slate-300

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
    const siblings = getSiblings(structure, node.node_id).filter(
      (s) => s.node_id !== node.node_id
    );
    const children = getChildren(node);

    // Limit displayed siblings to 2 on each side
    const nodeIndex = getSiblings(structure, node.node_id).findIndex(
      (s) => s.node_id === node.node_id
    );
    const leftSiblings = siblings.filter((_, i) => {
      const origIndex = getSiblings(structure, node.node_id).indexOf(siblings[i]);
      return origIndex < nodeIndex;
    }).slice(-2);
    const rightSiblings = siblings.filter((_, i) => {
      const origIndex = getSiblings(structure, node.node_id).indexOf(siblings[i]);
      return origIndex > nodeIndex;
    }).slice(0, 2);

    const WIDTH = 400;
    const CX = WIDTH / 2;
    let currentY = 30;

    const nodes: GraphNode[] = [];
    const linesList: GraphLine[] = [];

    // Parent row
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

    // Sibling row (left siblings + active + right siblings)
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

    // Lines from parent to all siblings
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

    // Children row
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

  // Don't render if the node is a root-level leaf
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/explorer/components/NeighborhoodGraph.tsx
git commit -m "feat: add NeighborhoodGraph SVG mini-map with pulsing active node"
```

---

### Task 11: SiblingNav component

**Files:**
- Create: `frontend/src/app/explorer/components/SiblingNav.tsx`

- [ ] **Step 1: Create SiblingNav.tsx**

Create `frontend/src/app/explorer/components/SiblingNav.tsx`:

```tsx
"use client";

import { ArrowLeft, ArrowRight } from "@phosphor-icons/react";
import type { TreeNode } from "@/lib/types";

interface SiblingNavProps {
  siblings: TreeNode[];
  currentId: string;
  onNavigate: (id: string) => void;
}

export function SiblingNav({ siblings, currentId, onNavigate }: SiblingNavProps) {
  const currentIndex = siblings.findIndex((s) => s.node_id === currentId);
  if (currentIndex === -1 || siblings.length <= 1) return null;

  const prev = currentIndex > 0 ? siblings[currentIndex - 1] : null;
  const next = currentIndex < siblings.length - 1 ? siblings[currentIndex + 1] : null;

  return (
    <div className="flex items-stretch gap-3 pt-4 border-t border-slate-100">
      <button
        onClick={() => prev && onNavigate(prev.node_id)}
        disabled={!prev}
        className="flex-1 flex items-center gap-2 rounded-xl border border-slate-100 px-4 py-3 text-left transition-colors hover:bg-slate-50 active:-translate-y-[1px] disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent"
      >
        <ArrowLeft size={14} className="flex-shrink-0 text-slate-400" />
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wider text-slate-400">Previous</p>
          <p className="text-sm text-zinc-950 truncate">
            {prev?.title ?? "\u2014"}
          </p>
        </div>
      </button>

      <button
        onClick={() => next && onNavigate(next.node_id)}
        disabled={!next}
        className="flex-1 flex items-center justify-end gap-2 rounded-xl border border-slate-100 px-4 py-3 text-right transition-colors hover:bg-slate-50 active:-translate-y-[1px] disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent"
      >
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wider text-slate-400">Next</p>
          <p className="text-sm text-zinc-950 truncate">
            {next?.title ?? "\u2014"}
          </p>
        </div>
        <ArrowRight size={14} className="flex-shrink-0 text-slate-400" />
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/explorer/components/SiblingNav.tsx
git commit -m "feat: add SiblingNav prev/next navigation buttons"
```

---

### Task 12: ExplorerClient main component

**Files:**
- Create: `frontend/src/app/explorer/ExplorerClient.tsx`

- [ ] **Step 1: Create ExplorerClient.tsx**

Create `frontend/src/app/explorer/ExplorerClient.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen } from "@phosphor-icons/react";
import type { BookData, ManifestEntry, TreeNode } from "@/lib/types";
import {
  findNodeById,
  getAncestorIds,
  getSiblings,
  getTreeStats,
} from "@/lib/tree-utils";
import { BookSelector } from "./components/BookSelector";
import { BookMetadata } from "./components/BookMetadata";
import { TreeNavigator } from "./components/TreeNavigator";
import { NodeBreadcrumb } from "./components/NodeBreadcrumb";
import { NodeDetail } from "./components/NodeDetail";
import { NeighborhoodGraph } from "./components/NeighborhoodGraph";
import { SiblingNav } from "./components/SiblingNav";
import { TreeSkeleton, DetailSkeleton } from "./components/SkeletonLoader";

interface ExplorerClientProps {
  manifest: ManifestEntry[];
}

export function ExplorerClient({ manifest }: ExplorerClientProps) {
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [bookData, setBookData] = useState<BookData | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  // Load book data when slug changes
  useEffect(() => {
    if (!selectedSlug) return;
    const entry = manifest.find((m) => m.slug === selectedSlug);
    if (!entry) return;

    setLoading(true);
    setSelectedNodeId(null);
    setExpandedIds(new Set());

    fetch(`/data/${entry.file}`)
      .then((res) => res.json())
      .then((data: BookData) => {
        setBookData(data);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, [selectedSlug, manifest]);

  // Navigate to a node: select it, expand ancestors, expand it if it has children
  const navigateToNode = useCallback(
    (id: string) => {
      if (!bookData) return;
      setSelectedNodeId(id);
      const ancestorIds = getAncestorIds(bookData.structure, id);
      setExpandedIds((prev) => {
        const next = new Set(prev);
        for (const aid of ancestorIds) next.add(aid);
        // Also expand the node itself so children are visible
        next.add(id);
        return next;
      });
    },
    [bookData]
  );

  const toggleExpand = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  // Derived state
  const selectedResult =
    bookData && selectedNodeId
      ? findNodeById(bookData.structure, selectedNodeId)
      : null;
  const selectedNode = selectedResult?.node ?? null;
  const nodePath = selectedResult?.path ?? [];
  const nodeDepth = nodePath.length;
  const siblings =
    bookData && selectedNodeId
      ? getSiblings(bookData.structure, selectedNodeId)
      : [];
  const stats = bookData ? getTreeStats(bookData.structure) : null;

  return (
    <div className="flex min-h-[100dvh] bg-[#f9fafb]">
      {/* Left Panel */}
      <aside className="w-80 flex-shrink-0 border-r border-slate-200/50 bg-white overflow-y-auto">
        <div className="p-4 space-y-4">
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-zinc-950">
              Tree Explorer
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Browse ingested knowledge structures
            </p>
          </div>

          <BookSelector
            books={manifest}
            selectedSlug={selectedSlug}
            onSelect={setSelectedSlug}
          />

          {loading && <TreeSkeleton />}

          {bookData && !loading && stats && (
            <>
              <BookMetadata book={bookData} stats={stats} />
              <TreeNavigator
                structure={bookData.structure}
                selectedId={selectedNodeId}
                expandedIds={expandedIds}
                onSelect={navigateToNode}
                onToggle={toggleExpand}
              />
            </>
          )}
        </div>
      </aside>

      {/* Detail Panel */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-6">
          {loading && <DetailSkeleton />}

          {!loading && !bookData && (
            <div className="flex flex-col items-center justify-center py-32 text-center">
              <BookOpen size={56} weight="thin" className="text-slate-300 mb-4" />
              <p className="text-sm text-slate-400">
                Select a book to explore its knowledge tree
              </p>
            </div>
          )}

          {!loading && bookData && (
            <>
              {selectedNode && (
                <NodeBreadcrumb
                  path={nodePath}
                  current={selectedNode}
                  onNavigate={navigateToNode}
                />
              )}

              <NodeDetail
                node={selectedNode}
                depth={nodeDepth}
                path={nodePath}
              />

              {selectedNode && bookData && (
                <NeighborhoodGraph
                  structure={bookData.structure}
                  node={selectedNode}
                  onNavigate={navigateToNode}
                />
              )}

              {selectedNode && siblings.length > 1 && (
                <SiblingNav
                  siblings={siblings}
                  currentId={selectedNode.node_id}
                  onNavigate={navigateToNode}
                />
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/explorer/ExplorerClient.tsx
git commit -m "feat: add ExplorerClient with state management, panel layout, and data loading"
```

---

### Task 13: Explorer page (server component shell)

**Files:**
- Create: `frontend/src/app/explorer/page.tsx`

- [ ] **Step 1: Create page.tsx**

Create `frontend/src/app/explorer/page.tsx`:

```tsx
import { readFile } from "fs/promises";
import { join } from "path";
import type { ManifestEntry } from "@/lib/types";
import { ExplorerClient } from "./ExplorerClient";

export const metadata = {
  title: "Tree Explorer — Gemma Tutor",
  description: "Browse ingested knowledge tree structures",
};

export default async function ExplorerPage() {
  const manifestPath = join(process.cwd(), "public", "data", "manifest.json");
  const raw = await readFile(manifestPath, "utf-8");
  const manifest: ManifestEntry[] = JSON.parse(raw);

  return <ExplorerClient manifest={manifest} />;
}
```

- [ ] **Step 2: Verify dev server compiles**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000/explorer` in a browser. Verify:
- Page loads without errors
- Book selector dropdown appears with both books
- Selecting a book loads the tree in the left panel
- Clicking a node shows details in the right panel
- Breadcrumb, neighborhood graph, and sibling nav all render
- Expand/collapse animations work with spring physics

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/explorer/page.tsx
git commit -m "feat: add /explorer server component page with manifest loading"
```

---

### Task 14: Visual QA and polish pass

**Files:**
- Modify: any component files as needed based on browser testing

- [ ] **Step 1: Test book switching**

In the browser at `http://localhost:3000/explorer`:
- Switch between the two books
- Verify skeleton loader appears during transition
- Verify tree stagger-reveals after loading
- Verify selected node and expanded state reset on book switch

- [ ] **Step 2: Test tree interactions**

- Click multiple nodes at different depths
- Verify emerald highlight follows selection
- Expand/collapse several branches — confirm spring animation
- Verify auto-scroll when selecting a deep node

- [ ] **Step 3: Test neighborhood graph**

- Select a node with parent + children + siblings
- Verify SVG shows correct topology
- Click a node in the graph — verify tree navigates and expands
- Select a root-level leaf — verify graph is hidden

- [ ] **Step 4: Test sibling navigation**

- Use prev/next buttons to traverse siblings
- Verify disabled state at first/last sibling
- Confirm detail panel crossfades between siblings

- [ ] **Step 5: Test empty states**

- Load page fresh (no book selected) — verify centered empty state
- Select a book but don't click a node — verify "Click a node" message

- [ ] **Step 6: Fix any visual issues found, commit**

```bash
git add -u frontend/src/
git commit -m "fix: visual polish from QA pass"
```

---

### Task 15: Final commit with all explorer files

- [ ] **Step 1: Verify build passes**

```bash
cd frontend && npm run build
```

- [ ] **Step 2: Create final commit if any unstaged changes remain**

```bash
git add frontend/
git commit -m "feat: complete Knowledge Tree Explorer at /explorer"
```

- [ ] **Step 3: Push to remote**

```bash
git push origin main
```

Plan complete and saved to `docs/superpowers/plans/2026-04-17-knowledge-tree-explorer.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?