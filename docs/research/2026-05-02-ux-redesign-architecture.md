# UX Redesign — Agentic Tutor Shell

**Date:** 2026-05-02
**Status:** proposal
**Author:** architect (UX track)
**Demo deadline:** 2026-05-18 (T–16 days)

## 1. Information Architecture

### Current state (verified)
- `/` Day-1 backend health page (dead route)
- `/explorer` doubles as data-management surface (BrandPill book picker + radial canvas) AND chat/practice host (drawer tabs)
- `/test/[id]` and `/test/[id]/review` standalone full-screen
- `/ingest` admin upload + SSE pipeline progress
- No persistent shell — every route reinvents its own chrome
- Chat is node-scoped: must click a node before chatting, BM25 only sees that subtree

### Recommended IA — single shell, four nav items

```
┌──────────────────────────────────────────────────────────┐
│ AppShell (RootLayout)                                    │
│ ┌──────────┬─────────────────────────────────────────┐   │
│ │ Sidebar  │ <route content>                         │   │
│ │          │                                         │   │
│ └──────────┴─────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

**Sidebar items (student-facing, 4):**
1. **Chat** (`/chat`, `/chat/[threadId]`) — default landing
2. **Tests** (`/tests`, `/tests/[testId]`, `/tests/[testId]/review`)
3. **Library** (`/library`, `/library/[bookSlug]`) — formerly `/explorer`
4. **Settings** (`/settings`) — book picker default, model toggle, language

**Admin (hidden behind `?admin=1` flag or `NEXT_PUBLIC_ADMIN=true`):**
5. **Ingest** (`/admin/ingest`) — moved out of student nav

### Route disposition

| Old | New | Action |
|---|---|---|
| `/` | `/chat` | redirect; demo health page deleted |
| `/explorer` | `/library/[bookSlug]` | rename + canvas becomes one of two view modes |
| `/explorer` (BrandPill picker) | `/library` (index) | book grid replaces the in-canvas dropdown |
| `/test/[id]` | `/tests/[testId]` | pluralize + nest under shell |
| `/test/[id]/review` | `/tests/[testId]/review` | same |
| `/ingest` | `/admin/ingest` | hidden from student nav |
| InspectorDrawer Chat tab | merged into `/chat` agentic surface | per-node chat retired (the agent finds the node) |
| InspectorDrawer Practice tab | "Generate test from this node" CTA → posts to `/tests/new?node_id=…` | thin shim, drawer keeps action |
| InspectorDrawer Content tab | kept (it's the verbatim source viewer — power user value) | unchanged |

### Where the radial canvas lives

Keep it. It's our differentiator at demo time. House it inside `/library/[bookSlug]` as the **default view**, with a "Tree outline" toggle for accessibility (many judges will appreciate a non-visual fallback). The canvas is no longer the entry to chat — chat lives at `/chat`. Library is now honestly framed as "explore the source dataset", which is what it always was.

## 2. Page-level wireframes

### 2.1 Sidebar (expanded ~220px / collapsed ~56px)

```
┌─────────────────────┐    ┌──────┐
│ ◆ Gemma Tutor       │    │ ◆    │
│                     │    │      │
│ ▸ Chat       ⌘1    │    │ 💬   │
│   Tests      ⌘2    │    │ 📝   │
│   Library    ⌘3    │    │ 🌳   │
│   Settings   ⌘4    │    │ ⚙    │
│                     │    │      │
│ ── Recent threads ──│    │  ⤺   │
│ • Why Aravalli is…  │    │      │
│ • Mawath rainfall   │    │      │
│ • RAS-mock #3       │    │      │
│                     │    │      │
│ [book picker pill]  │    │ [📚] │
│ ⌃B collapse         │    └──────┘
└─────────────────────┘
```

The "current book" pill at the bottom of the sidebar is the global retrieval scope — used by `/chat` to know which book(s) to query and by `/library` as the active book.

### 2.2 `/chat` — agentic chat surface

```
┌──────┬───────────────────────────────────────┬──────────────────┐
│ Side │ Thread: "Why Aravalli is the…"        │ Sources           │
│ bar  │                                       │ ┌──────────────┐ │
│      │ [user] Why is Aravalli called the     │ │ [1] p18      │ │
│      │  planning region?                     │ │ "tribal      │ │
│      │                                       │ │  areas, …"   │ │
│      │ [agent] 🔍 Searching in               │ │ open in lib →│ │
│      │  "Aravalli Mountain Range"…           │ └──────────────┘ │
│      │  ✓ Found 3 paragraphs                 │ ┌──────────────┐ │
│      │                                       │ │ [2] p21      │ │
│      │  Aravalli is called the planning      │ │ "Gurushikhar"│ │
│      │  region because it concentrates       │ └──────────────┘ │
│      │  tribal districts, river-valley       │                  │
│      │  projects, and major mining belts     │ ─ actions ─      │
│      │  [1][2]…                              │ ▸ Make a test    │
│      │                                       │   from this chat │
│      │                                       │ ▸ Save to notes  │
│      │ ┌───────────────────────────────────┐ │                  │
│      │ │ Ask anything…                  ↵ │ │                  │
│      │ └───────────────────────────────────┘ │                  │
│      │ Scope: All books ▾   Model: Gemma 26B │                  │
└──────┴───────────────────────────────────────┴──────────────────┘
```

Key elements:
- **Tool-call pill** ("Searching in 'Aravalli Mountain Range'…") renders inline in the assistant turn while the agent is in tool-use phase. Becomes a click-through breadcrumb on completion that opens the node in `/library`.
- **Right rail** is the citations panel (replaces the per-node Content tab). Hovering [1] highlights the corresponding card.
- **"Make a test from this chat"** in the rail collects all cited node_ids from the conversation and POSTs to `/tests` with `n=10` and a `from_thread_id` field — the topic-picker is implicit in the chat.
- **Scope dropdown** ("All books" / "This book only" / "This subtree only") is the single user-facing knob for retrieval scope. Defaults to the sidebar's active book.
- **Streaming UX:** tool pill → text-delta → citation cards animate in left-to-right. No layout shift.

### 2.3 `/tests` — list + new test

```
┌──────┬───────────────────────────────────────────────────────────┐
│ Side │ Tests                                  [+ New test]       │
│      │                                                           │
│      │ ─ In progress ───────────────────────────────────────     │
│      │ ▸ test-9af2  Climate of Rajasthan  · 4/10 answered        │
│      │                                                           │
│      │ ─ Past ─────────────────────────────────────────────      │
│      │ ▸ test-3c11  Aravalli         · 7/10  · 2 days ago        │
│      │ ▸ test-7d40  Mineral resources · 9/10 · last week         │
│      │                                                           │
└──────┴───────────────────────────────────────────────────────────┘
```

**[+ New test] modal:**

```
┌──────────────────────────────────────────────────┐
│ Generate a mock test                             │
│                                                  │
│ Topic: ⊙ Pick a node from the tree               │
│        ◯ From a recent chat thread               │
│        ◯ Whole book: [Springboard …  ▾]          │
│                                                  │
│ Questions: [5] [10] [15]                         │
│ Difficulty: 4 easy · 3 med · 3 hard              │
│                                                  │
│ [Cancel]                       [Generate]        │
└──────────────────────────────────────────────────┘
```

The "pick a node" mode opens a mini tree picker (collapsible outline) — same data as `/library`, no canvas. Inside `/tests/[testId]` and `/tests/[testId]/review`, hide the sidebar (full-screen test mode). Today's pages survive almost unchanged behind a Next.js layout swap.

### 2.4 `/library` index + `/library/[bookSlug]`

```
/library                              /library/[bookSlug]
┌────────────────────────────┐        ┌───────────────────────────┐
│ Library                    │        │ Springboard Rajasthan Geo │
│                            │        │ [Canvas | Outline] ◀ tabs │
│ ┌────────┐  ┌────────┐     │        │                           │
│ │📕 Spring│ │📗 RBSE │     │        │   ◉                       │
│ │board RJ │ │Cl.11 Ge│     │        │  ╱│╲     (radial canvas)  │
│ │243 nodes│ │187 nod │     │        │ ◉ ◉ ◉                     │
│ └────────┘ └────────┘     │        │                           │
│                            │        │ → InspectorDrawer (Content│
│ + Ingest a new book        │        │    tab + "Ask in chat" CTA│
│   (admin)                  │        │    + "Generate test" CTA) │
└────────────────────────────┘        └───────────────────────────┘
```

InspectorDrawer is preserved but loses the Chat tab. The Content tab gets two prominent CTAs: **"Ask in chat"** (deep-links to `/chat?scope=node:<id>`) and **"Generate test"** (existing PracticeTab behavior).

### 2.5 `/admin/ingest`

Unchanged from today's `/ingest` page — same SSE stream, same form. Hidden from student nav. Sidebar appears only when `NEXT_PUBLIC_SHOW_ADMIN=true` or `?admin=1` is set.

## 3. Agentic chat architecture

### Tool contract

```
tool: lookup_skill_content
args:
  query: string                  # paraphrased search query
  scope: "all" | "book" | "node" # retrieval scope
  book_slug?: string             # required when scope=book or node
  node_id?: string               # required when scope=node
returns:
  hits: ParagraphHit[]           # same shape as current retriever
  scope_label: string            # human-readable e.g. "Aravalli Mountain Range"
```

Server-side resolution: scope determines which BM25 index to build. For `scope="all"`, walk every book in the manifest, build a flat corpus (still <20K paragraphs at hackathon scale — BM25 handles this in <50ms). Cache per-scope indices in process memory keyed by `(scope, book_slug?, node_id?)`.

### Tool-calling strategy — keep the hybrid, but simplify

The 2026-05-01 research note recommended native → inline-tag → JSON-mode fallback. **Recommendation: ship a simpler variant for the demo**.

- **Skip native `tools` API.** It's the least reliable path on Gemma 4 26B per the research, and OpenRouter providers vary. We're already paying the JSON-mode tax in `tests_engine`, we know it works.
- **Path A (primary): JSON-mode tool decision.** First LLM turn uses `response_format={"type":"json_object"}` with a system prompt that says: "If you need to look up source content, output `{\"action\":\"lookup\", \"query\":..., \"scope\":..., \"book_slug\":..., \"node_id\":...}`. If you can answer from prior context, output `{\"action\":\"answer\", \"text\":\"…\"}`."
- **Path B (fallback): inline tag parse.** If JSON parse fails, try the `<|tool_call|>{...}<|tool_call|>` regex pattern from research §2 before erroring.
- **Path C (degrade): no tool.** If both fail twice, fall back to today's behavior — assume the user's sidebar-scoped book and do BM25 against its root, then answer. Never block the user on tool-call failure.

Why simplify: ONE format to debug, ONE prompt to tune, demo-day risk minimized. Native tool API can be added post-hackathon when there's time to test across providers.

### Multi-turn loop

```
loop (max_steps = 3):
  1. Call Gemma with [system, …history, last_user, …tool_results]
  2. Parse response (JSON-mode) → action
  3. if action == "lookup":
        emit SSE event {type:"tool-call", query, scope}
        run BM25, format hits
        emit SSE events {type:"data-citation", …} per hit
        append {role:"tool", content: hits_json} to history
        continue
     if action == "answer":
        stream the "text" field as text-delta events
        break
  4. if step == max_steps: force final-answer turn (no tools allowed)
```

Stop conditions: model emits `action=answer`, OR step budget exhausted (force final synthesis), OR identical query repeated (loop guard).

### Streaming UX for tool calls

New SSE event types layered on the existing AI SDK UI Message Stream:
- `{type:"tool-call", id:"tc1", name:"lookup_skill_content", args:{query,scope,…}}` — UI renders the "🔍 Searching in '…'…" pill
- `{type:"tool-result", id:"tc1", hit_count:3, scope_label:"Aravalli Mountain Range"}` — pill flips to "✓ Found 3 paragraphs in 'Aravalli…'"
- existing `data-citation`, `text-delta`, `text-end`, `finish` follow

Frontend keeps the same parser shape it already has in ChatTab.tsx — just adds two event handlers.

### Differences from today

| | Today | Proposed |
|---|---|---|
| Entry | Click node → drawer → Chat tab | Type in `/chat` |
| Scope | Hard-bound to one node | Agent picks via tool, user can override |
| Retrieval | One BM25 call before LLM | 1–3 BM25 calls, agent-driven |
| Citations | Only nodes in subtree | Any node, traceable by node_id |
| Failure mode | Wrong node = bad answer | Agent re-queries or asks user |

## 4. Migration plan (16 days, sequenced)

| Days | Work | Type | Behind flag? |
|---|---|---|---|
| **1** (5/2) | Create `(app)` route group, build AppShell + Sidebar, redirect `/` → `/chat`. Keep all existing routes working. | net-new | full cutover (low risk) |
| **2** (5/3) | Move `/explorer` → `/library/[bookSlug]`, `/test/*` → `/tests/*`, `/ingest` → `/admin/ingest`. Add redirects from old paths. InspectorDrawer keeps Content + Practice; Chat tab swap to "Ask in chat" deep-link. | refactor (file moves only) | no |
| **3–4** (5/4–5) | Backend: add `lookup_skill_content` tool executor, scope resolver, multi-book BM25 cache. Add `/tutor/agent_chat` endpoint that runs the JSON-mode loop. **TDD: 6 unit tests** covering lookup paths and loop termination. | net-new | endpoint behind `?agent=1` query flag |
| **5–6** (5/6–7) | Frontend: build `/chat` page (input, thread list, right rail, tool pills). Wire to new endpoint. Keep old node-scoped chat reachable via `/library` deep-link (free fallback if agent breaks). | net-new | feature flag `NEXT_PUBLIC_AGENT_CHAT=1` |
| **7** (5/8) | `/tests` index page + new-test modal. Pulls from `_TEST_STORE` (will need a `/tests` GET listing endpoint — 20-line addition). | mixed | no |
| **8–9** (5/9–10) | Polish: tool-call pill animations, citation right rail hover sync, "Make a test from chat" action, sidebar collapse, keyboard shortcuts, light/dark consistency. | refactor | no |
| **10** (5/11) | E2E with Playwright: 5 reference questions through agentic chat, 1 test generation flow, 1 library browse. Fix top 3 bugs. | TDD | no |
| **11** (5/12) | Cutover: flip `NEXT_PUBLIC_AGENT_CHAT=1` default. Old node-scoped endpoint stays in code (fallback path C uses it). | flag flip | n/a |
| **12–13** (5/13–14) | Buffer for fallout. Demo script rehearsal. | — | — |
| **14–16** (5/15–17) | Submission writeup, video record, Kaggle notebook, polish. | docs | n/a |

**Critical path for demo:** Days 1, 5–6, 11. Everything else can slip a day without killing the submission.

**Pure refactors (low risk):** AppShell extraction, route renames, sidebar, `/tests` index, tool-call SSE event additions.
**Net-new (where bugs live):** agent loop, JSON-mode tool decision, multi-book BM25 cache, right rail.

## 5. Open questions for the user

1. **Default scope in `/chat`:** when no book is selected in the sidebar, should the agent search across **all** books, or refuse with "pick a book first"? Cross-book is the differentiator; it's also the riskiest retrieval. Recommend: default to all-books at demo time on the curated 2–3 book set.
2. **Thread persistence:** in-memory only (matches current `_TEST_STORE` pattern), localStorage, or a JSON file in `database/threads/`? Hackathon spec said no cross-session persistence for chat — does that still hold for `/chat`'s thread list?
3. **Tool-call step budget:** 3 steps is my proposal. At ~5–8s per step with cold BM25 + Gemma latency, that's 15–24s worst case. Acceptable on demo, or should we cap at 2?
4. **Admin gating:** is `?admin=1` query flag enough, or do you want a real auth check (even a hardcoded password) before submission? Judges may try to break things.
5. **Mobile:** today nothing is mobile-friendly. Do we ship a mobile sidebar drawer, or explicitly mark "desktop demo" in the README and skip the responsive work? Recommend: skip, mark desktop-only.
