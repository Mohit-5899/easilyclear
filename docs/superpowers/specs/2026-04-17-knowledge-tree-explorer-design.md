# Knowledge Tree Explorer — Design Spec

**Date:** 2026-04-17
**Status:** Approved
**Route:** `/explorer`
**Purpose:** QA tool + hackathon demo for visualizing ingested book structures

---

## 1. Layout

Three-panel layout on desktop, stacked on mobile:

```
LEFT PANEL (320px fixed)          DETAIL PANEL (flex-1)
┌──────────────────────┐  ┌────────────────────────────────┐
│ Book Selector (drop) │  │ Breadcrumb (clickable)         │
│ Book Metadata (prov) │  │ Node Card (title/summary/meta) │
│ Tree Navigator       │  │ Neighborhood Graph (SVG)       │
│   (collapsible list) │  │ Sibling Nav (prev/next)        │
└──────────────────────┘  └────────────────────────────────┘
```

- Left panel: fixed 320px width, full viewport height, scrolls independently
- Detail panel: fills remaining space, scrolls independently
- Mobile (<768px): tree becomes slide-out drawer, detail panel is full width

## 2. Visual Design

### Color
- Background: `#f9fafb`
- Cards: `#ffffff` with `border-slate-200/50`, diffusion shadow `shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)]`
- Single accent: Emerald (active states, scope badges, selected indicators)
- No purple, no neon glows, no pure black (`zinc-950` for darkest text)

### Typography
- UI: Geist (sans-serif)
- Monospace: Geist Mono (node_ids, page numbers, stats)
- Headlines: `text-2xl tracking-tight font-semibold`
- Body/summaries: `text-base text-slate-600 leading-relaxed max-w-[65ch]`
- No Inter, no serif in this UI context

### Containers
- Rounded corners: `rounded-2xl` for major panels, `rounded-xl` for inner cards
- Metadata: `divide-y` layout (no card-in-card nesting)
- Padding: `p-6` inside panels, `p-4` for compact elements

## 3. Components

### 3.1 Book Selector
- Dropdown listing all available books by `doc_name`
- Shows `subject_scope` badge next to each name
- On selection: loads that book's JSON, resets tree state

### 3.2 Book Metadata Card
Compact key-value layout with `divide-y`:
- Publisher + source authority
- Subject scope: pill badge (emerald for `rajasthan`, slate for `pan_india`)
- Exam coverage: inline pill badges
- Cleaning layers: mini pipeline visualization `whitelist -> regex -> llm_pass` with checkmark icons
- LLM model used for indexing
- Ingestion date (formatted)
- Stats: total nodes, max depth, page range

### 3.3 Tree Navigator
- Indented collapsible list (file-explorer style)
- Depth indicated by left padding + subtle left border (color lightens per depth level)
- Active node: emerald left border + light emerald background wash
- Each node shows: title, page range badge (mono font), child count if has children
- Expand/collapse chevron icon for parent nodes
- Auto-expand ancestors when a node is selected externally (from graph or breadcrumb)
- Auto-scroll selected node into view

### 3.4 Node Breadcrumb
- Horizontal path: `Root > Chapter > Section > Current`
- Each segment clickable (selects that node, collapses detail to that level)
- Segments slide in from left on path change

### 3.5 Node Detail Card
- Title: `text-2xl tracking-tight`
- Page range: `Pages 5-8` in mono font
- Node ID: small mono badge
- Depth level indicator
- Child count
- Summary: full text in readable prose styling
- If no node selected: empty state with "Select a node from the tree to explore"

### 3.6 Neighborhood Graph (SVG Mini-Map)
- Simple node-link diagram showing:
  - Parent node (top)
  - Active node (center, highlighted emerald, subtle pulse)
  - Sibling nodes (same level, left/right of active)
  - Child nodes (below active)
- Lines connecting parent-child relationships
- All nodes clickable (navigates tree)
- Hidden when node has no parent and no children (root-only leaf)

### 3.7 Sibling Nav
- Previous / Next buttons at bottom of detail panel
- Shows sibling title as preview text
- Disabled at first/last sibling with muted styling

## 4. Data Flow

### Source
- Static JSON files copied to `frontend/public/data/`
- Book manifest: `frontend/public/data/manifest.json` listing available books
- No backend API changes needed

### Manifest format
```json
[
  {
    "slug": "ncert_class10_contemporary_india_2",
    "name": "Contemporary India II (NCERT Class 10 Geography)",
    "scope": "pan_india",
    "file": "ncert_class10_contemporary_india_2.json"
  }
]
```

### State (single ExplorerClient component)
- `selectedBookSlug: string | null`
- `bookData: BookData | null` (parsed JSON)
- `selectedNodeId: string | null`
- `expandedNodeIds: Set<string>`
- All derived data (breadcrumb, siblings, parent, children) computed via pure utility functions

### Tree utilities (pure functions)
- `findNodeById(structure, id)` -> node + ancestor path
- `getParent(structure, id)` -> parent node or null
- `getSiblings(structure, id)` -> sibling array
- `getChildren(node)` -> direct children array
- `flattenTree(structure)` -> flat list with depth metadata
- `getTreeStats(structure)` -> { totalNodes, maxDepth, pageRange }

## 5. Component Architecture

```
/explorer/page.tsx (Server Component — layout shell only)
  ExplorerClient.tsx ("use client" — all interactive logic)
    BookSelector.tsx
    BookMetadata.tsx
    TreeNavigator.tsx
      TreeNode.tsx (recursive, handles expand/collapse)
    NodeBreadcrumb.tsx
    NodeDetail.tsx
    NeighborhoodGraph.tsx (isolated "use client" for pulse animation)
    SiblingNav.tsx
```

File location: `frontend/src/app/explorer/`
Shared utilities: `frontend/src/lib/tree-utils.ts`
Types: `frontend/src/lib/types.ts`

## 6. Interactions & Motion

### Dependencies
- `framer-motion` — spring animations, layout transitions, AnimatePresence
- `@phosphor-icons/react` — icons

### Tree expand/collapse
- Spring: `type: "spring", stiffness: 200, damping: 25`
- Children stagger: `staggerChildren: 0.04` on expand
- Collapse: height to 0 with opacity fade

### Node selection
- Active node: layout transition for emerald background
- Detail panel: `AnimatePresence mode="wait"` crossfade on node change
- Breadcrumb: segments slide in from left

### Neighborhood graph
- Active node: infinite gentle scale pulse (isolated client component, memoized)
- Other nodes: hover scale with spring
- Clicking navigates tree

### Book switching
- Skeleton shimmer on tree + detail during load
- Tree stagger-reveals top to bottom
- Metadata stats: number count-up animation

### Tactile feedback
- Tree nodes: `scale-[0.98]` on `:active`
- Buttons: `-translate-y-[1px]` on press

## 7. States

### Loading
- Skeleton shimmer matching tree list shape (left panel)
- Skeleton shimmer matching detail card shape (right panel)

### Empty (no book selected)
- Full detail panel: centered message "Select a book to explore its knowledge tree"
- Phosphor BookOpen icon, muted slate

### Empty (no node selected)
- Detail panel: "Click a node in the tree to see its details"
- Tree fully visible and interactive

### No children
- Neighborhood graph section hidden
- Sibling nav still visible if siblings exist

## 8. Responsive

- Desktop (>=1024px): side-by-side panels as described
- Tablet (768-1023px): left panel collapses to 280px, detail panel smaller
- Mobile (<768px): left panel becomes slide-out drawer with hamburger toggle, detail panel full width

## 9. File Structure

```
frontend/src/
  app/explorer/
    page.tsx                 # Server component shell
    ExplorerClient.tsx       # Main client component
    components/
      BookSelector.tsx
      BookMetadata.tsx
      TreeNavigator.tsx
      TreeNode.tsx
      NodeBreadcrumb.tsx
      NodeDetail.tsx
      NeighborhoodGraph.tsx
      SiblingNav.tsx
      SkeletonLoader.tsx
  lib/
    tree-utils.ts            # Pure tree traversal functions
    types.ts                 # TypeScript types for book data
frontend/public/data/
    manifest.json
    ncert_class10_contemporary_india_2.json
    springboard_rajasthan_geography_ras_pre_UNOFFICIAL.json
```
