# Spec — Subject-Canonical Tree (no brand names in UI)

**Date:** 2026-05-04
**Status:** approved (decisions locked 2026-05-04)
**Demo deadline:** 2026-05-18 (T–14 days)

## Problem

Current architecture stores ingested books as **independent trees** under one subject:

```
database/skills/geography/
└── springboard_rajasthan_geography/    ← brand-named tree
    └── 02-physiographic-divisions/03-aravali.md
```

Three issues this causes:

1. **Knowledge fragmentation** — if RBSE Class 11 is added later, "Aravalli" lives twice. Cross-book dedup marks one `superseded_by` the other but the trees stay separate. Retrieval surfaces both copies.
2. **Brand exposure** — book paths and citation rails leak publisher names ("Springboard Academy", "RBSE") into the student-facing UI. Both legally awkward and pedagogically irrelevant.
3. **Scaling problem** — every new book = a new top-level tree. By the time we add Patwari + REET sources we have ~6 parallel trees per subject. Mock-test generation and chat retrieval both have to handle the cross-tree case.

## What changes

### 1. Storage layout — subject is the root, not a sub-folder

```
database/skills/
├── rajasthan_geography/                ← SUBJECT (canonical)
│   ├── SKILL.md
│   ├── 01-physical-geography/
│   │   ├── SKILL.md
│   │   ├── aravali-mountain.md         ← canonical leaf, multi-source
│   │   ├── thar-desert.md
│   │   └── ...
│   ├── 02-climate/
│   ├── ...
└── (future) rajasthan_history/
```

One canonical tree per subject. Books merge **into** this tree.

### 2. Leaf frontmatter — multi-source, brand-hidden

```yaml
---
node_id: rajasthan_geography/01-physical-geography/aravali-mountain
name: Aravalli Mountain Range
description: Formation, length, peaks, passes, and importance of the Aravalli range.
depth: 2
order: 1
parent: rajasthan_geography/01-physical-geography
sources:                                # ← NEW; what the UI shows
  - source_id: 1                        # 1-indexed, used as [N] citation marker
    publisher: Springboard Academy      # ← hidden from UI; used for dedup ranking + audit
    book_slug: springboard_rajasthan_geography
    pages: [18, 19, 20]
    paragraph_ids: [42, 67]
    authority_rank: 2                   # 0=NCERT, 1=RBSE/state, 2=coaching, 3=other
    content_hash: sha256:…              # for cache invalidation
  - source_id: 2
    publisher: NCERT
    book_slug: ncert_class11_india_physical
    pages: [44]
    paragraph_ids: [12, 18]
    authority_rank: 0
ingested_at: '2026-05-04T...'
ingestion_version: v3                   # bumped from v2
subject: rajasthan_geography
---

## Source 1 (pages 18-19)

(verbatim Springboard paragraphs)

## Source 2 (page 44)

(verbatim NCERT paragraphs)
```

For single-source leaves the body is just one `## Source 1 …` section — preserves source-preservation rule (CLAUDE.md A.1) cleanly.

### 3. Brand stripping rule (non-negotiable)

The strings `Springboard`, `RBSE`, `NCERT`, `Academy`, etc. — and their book_slug forms — appear **only** in:

- YAML frontmatter `sources[].publisher` and `sources[].book_slug`
- Server-side audit logs

They never appear in:

- Markdown body (only `Source 1`, `Source 2`)
- Agent system prompt
- TOOL_RESULT messages fed to Gemma
- Chat citation pills / right rail
- Test review screen
- Library navigation
- URL paths

Whoever adds a new UI surface checks this first.

### 4. URL changes

| Old | New |
|---|---|
| `/library/[bookSlug]` | `/library/[subjectSlug]` |
| `/library/springboard_rajasthan_geography` | `/library/rajasthan_geography` |
| Library index shows book cards | Library index shows subject cards |

Old paths get 307 redirects.

### 5. Agent scope hierarchy

| Old scope | New scope | Meaning |
|---|---|---|
| `all` | `all` | every subject's canonical tree |
| `book` | `subject` | one subject's tree (e.g. `rajasthan_geography`) |
| `node` | `node` | one leaf or sub-tree |

`book_slug` field on the request model becomes `subject_slug`.

### 6. Pipeline — new Stage 6.5 (merge), replaces Stage 6.5 (dedup-mark)

Today's `dedup.py` flags pairs with `superseded_by`. New `merge.py` does:

```
For each leaf in proposed_tree (the just-ingested book):
    candidate = best_match(leaf, existing_subject_tree)  # cosine prefilter + Gemma judge
    if candidate (sim >= 0.85 and judge says "duplicate"):
        APPEND new source to candidate's sources[]
        APPEND new "## Source N" section to candidate's body
    else:
        FIND best-fit chapter in existing tree (Gemma classifier)
        if found:
            ADD as new leaf under that chapter
        else:
            CREATE new chapter with the leaf
```

Winner-rule (NCERT > RBSE > coaching > other) determines `source_id` ordering: lowest `authority_rank` becomes `source_id=1`, ties broken by ingestion order.

For the **first** book ingested into a subject (current Springboard case): no merge — just emits the proposed tree as the initial subject tree, with all leaves having `sources: [{source_id: 1, ...}]`.

## Migration plan (3 phases × ~half-day each)

### Phase 1 — Schema + emit refactor (Day 1, ~6h)
- Update `ingestion_v2/content_fill.py` and `emit.py` to produce new frontmatter + body shape
- Add `LeafSource` Pydantic model
- Update `tutor/retriever.py` `_parse_leaf_paragraphs` to read multi-source bodies (split on `## Source N` headers)
- Bump `ingestion_version: v3`
- Re-emit existing Springboard tree from its current proposed_tree by feeding it through the new emitter (no LLM cost — deterministic)
- Move output from `database/skills/geography/springboard_rajasthan_geography/` to `database/skills/rajasthan_geography/`
- **Delete** old `database/skills/geography/` entirely (per user decision)
- Update `frontend/public/data/manifest.json` schema: `slug` → `subject_slug`
- Test: 109 → 109 backend tests still green (no behavior change at scale, just schema)

### Phase 2 — Merge stage + brand stripping (Day 1-2, ~6h)
- New `ingestion_v2/merge.py`:
  - `match_existing_leaf(new_leaf, subject_tree, embedder, judge)` — returns matched node or None
  - `match_chapter(new_leaf, subject_tree, llm, model)` — Gemma classifier picks best-fit chapter
  - `merge_into_subject_tree(proposed, subject_tree, llm, embedder, model)` — full orchestration
- Update `pipeline.py` Stage 6.5 to call `merge_into_subject_tree` when an existing subject tree is on disk
- Update `tutor/agent.py` `_format_tool_result_message` — strip book names, emit `source_id=N path='aravali-mountain' page=18`
- Update `prompts_v2/agent_chat_system.md` — use `Source N` not book names in examples
- Update `tutor/scope.py` — `book` → `subject`, walk subject directories under skill_root, drop the brand-tree filter (no longer relevant)
- Tests: 6 new merge unit tests + adapt the 14 agent tests to use subject scope

### Phase 3 — Frontend brand strip (Day 2, ~4h)
- `/library` index → list subjects (read directory names directly, no manifest lookup needed)
- `/library/[subjectSlug]` → renders ExplorerClient over the subject tree
- Drop BookPill component
- Chat right rail: citations show `Source N · page X` only — no book label
- `/tests` index: drop `book_slug` column, no migration needed (in-memory store regenerates per session)
- New-test modal: topic picker queries `/api/library/leaves` returns only `subject` + `path`, no book name
- Settings page: scope options become `all subjects | this subject | this leaf`
- Add 307 redirects from old `/library/<book_slug>` paths

### Phase 4 (optional, only if there's time) — Second book ingest
- Re-download or pick a second source (ideally NCERT Class 11 India Physical for clean overlap)
- Run pipeline with `--subject rajasthan_geography`
- Verify merge actually fires: assert no duplicate aravali leaves, both sources listed in frontmatter
- Snapshot the merged tree as a "before/after dedup" demo artifact for the writeup

## Acceptance criteria

For Phase 1 (must-have to keep momentum):
- [ ] `database/skills/rajasthan_geography/` exists with all 34 leaves from Springboard re-emitted under new schema
- [ ] `database/skills/geography/` deleted from disk
- [ ] Each leaf .md has `sources: [{source_id: 1, publisher: 'Springboard Academy', ...}]` in frontmatter
- [ ] Body is `## Source 1 (pages X-Y)\n\n<verbatim>` — no other text
- [ ] All 123+ backend tests green
- [ ] `/chat` still answers reference questions; right rail shows `Source 1 · page 18` (no brand)

For Phase 2:
- [ ] `merge.py` exists with 6 unit tests (match-by-embedding, no-match-add-leaf, no-match-add-chapter, append-source, ordering by authority, content-hash idempotency)
- [ ] Agent's TOOL_RESULT messages contain no publisher names
- [ ] `prompts_v2/agent_chat_system.md` updated, no brand strings

For Phase 3:
- [ ] No string match for "Springboard", "RBSE", "NCERT", "Academy" in any rendered page (`grep -ri --include='*.tsx' --include='*.ts'` audit)
- [ ] Library shows "Rajasthan Geography" subject card; clicking opens canonical tree
- [ ] Chat citation pills show only `[N]` markers; right rail shows `Source N · page X`

## Out of scope

- LoRA fine-tune or model swap (Gemma 4 26B paid stays)
- Mobile/responsive design
- Auth (admin still gated by `?admin=1`)
- Cross-subject retrieval ranking improvements (BM25 stays as-is)
- Body-rendering UI for showing source-1 vs source-2 conflicts side-by-side (the markdown body already supports this; UI just renders sequentially in v1)

## Risks

| Risk | Mitigation |
|---|---|
| Merge picks wrong chapter for new leaf | Gemma classifier has a "create new chapter" escape hatch; user can manually re-parent post-ingest |
| Single-source tree migration loses content | Phase 1 re-emit is deterministic — same paragraphs in same order, just new frontmatter wrapper |
| Brand grep audit misses dynamic strings | Add a simple Vitest unit test that fetches `/api/library/leaves` + `/chat` reference questions, asserts no brand strings in response payloads |
| Old skill folder accidentally re-indexed | `tutor/scope.py` filter already excludes `.v2.0-buggy/` etc. — same hidden-prefix rule applies once we delete `geography/` |
