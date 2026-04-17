# V2 Ingestion Pipeline + Explorer Update — Design Spec

**Date:** 2026-04-17
**Status:** Approved (pending final user review)
**MVP scope:** Single book (Springboard Rajasthan Geography), end-to-end

---

## 1. Goals

- Replace PageIndex with a Gemma-only agentic ingestion pipeline that produces coherent, non-fragmented skill trees
- Output a **skill folder** (Anthropic-Skills-style `.md` files with YAML frontmatter) as the canonical knowledge unit
- Update the `/explorer` UI to visualize skill folders (radial canvas preserved; data source changes)
- Prove the pipeline on the Springboard Rajasthan Geography PDF before generalizing

## 2. Non-Goals (deferred to V2.1+)

- Admin upload UI (use a CLI script with hardcoded path)
- Dedup system (only 1 book in scope — nothing to compare against)
- RAG priming across books (no existing skill library yet)
- Retrieval runtime (Gemma tool-calling for tutor answers)
- OCR (Springboard is text-extractable; add OCR in V2.1 for scanned PDFs)
- Multi-book taxonomy consolidation

## 3. Architecture

Eight-stage pipeline. Each stage is independently testable. Stages 3 and 6 (RAG priming, dedup) are **no-ops for the MVP** since there are no existing books to compare against — the stubs stay in the code so V2.1 can drop them in without restructuring.

```
PDF → Extract → Pre-structure → [RAG prime] → Multi-agent Gemma
    → Validation → [Dedup] → Content fill + Q&A verify → Skill folder
```

## 4. Skill Folder Schema

**Location:** `database/skills/<subject>/<book_slug>/`

**Structure:**
```
database/skills/
  geography/
    springboard_rajasthan_geography/
      SKILL.md                               # root: book-level metadata
      01-location-and-borders/
        SKILL.md                             # chapter metadata + intro
        01-geographic-position.md            # leaf subtopic
        02-neighboring-states.md
      02-physical-features/
        SKILL.md
        01-thar-desert.md
        02-aravalli-hills.md
        03-rivers.md
      03-climate/
        SKILL.md
        01-seasons.md
        ...
```

**Rules:**
- Every directory contains a `SKILL.md` with metadata for that subtree
- Leaves are `.md` files directly under a chapter directory
- Numeric prefixes (`01-`, `02-`) enforce ordering
- Slugs are kebab-case, ASCII only

**Frontmatter schema:**
```yaml
---
name: Thar Desert
description: The Thar Desert's geography, climate, and human geography in Rajasthan
node_id: geography/springboard_rajasthan_geography/02-physical-features/01-thar-desert
parent: geography/springboard_rajasthan_geography/02-physical-features
depth: 2
source_book: springboard_rajasthan_geography
source_pages: [12, 13, 14]
content_hash: sha256:abc123...         # stable across re-ingestion if content unchanged
related_skills: []                      # populated by V2.1 dedup
superseded_by: null
ingested_at: 2026-04-17T18:30:00Z
ingestion_version: v2
---

[Markdown body — the actual content Gemma wrote, verified via Q&A roundtrip]
```

## 5. Stage-by-Stage Technical Details

### Stage 1 — Extraction
- **Library:** PyMuPDF (already in repo) for MVP. Returns `List[Paragraph]` with `{text, page, bbox}`.
- **OCR fallback:** deferred to V2.1 (Springboard is text-extractable)
- **Output:** `ExtractedDoc(paragraphs: List[Paragraph])` — 300–800 paragraphs for a typical book

### Stage 2 — Pre-structure (no LLM)
- **Embeddings:** `sentence-transformers` with `BAAI/bge-small-en-v1.5` (33MB, local, CPU-fast)
- **Topic segmentation:** sliding-window (k=5) cosine-similarity valleys between consecutive paragraphs. A "valley" = local minimum in similarity → topic boundary.
- **Clustering:** HDBSCAN on paragraph embeddings. Produces variable-density topic clusters without K-tuning.
- **Output:** `DraftHierarchy(clusters: List[Cluster], boundaries: List[int])` — N candidate topics, each cluster has `paragraph_ids + centroid_summary`

### Stage 3 — RAG priming
- **MVP:** no-op (returns empty `existing_skills` list since DB is empty)
- **V2.1:** embed new topics vs `database/skills/<subject>/**/SKILL.md` metadata, return top-K for Gemma's context

### Stage 4 — Multi-agent Gemma loop (the core)
- **Model:** `google/gemma-4-31b-it` (paid tier via OpenRouter, full precision) via existing `LLMClient` abstraction
- **Output format:** JSON via constrained tool-call (Gemma 4 supports function calling natively — eliminates format drift)

**Three roles:**

1. **Proposer** — given draft hierarchy + existing skills (empty for MVP), drafts a skill tree:
   ```json
   {
     "title": "Rajasthan Geography",
     "children": [
       {"title": "Location & Borders", "paragraph_refs": [0,1,2], "children": [...]},
       ...
     ]
   }
   ```

2. **Critic** — reviews Proposer output against rubric:
   - Structural balance (no chapter with 10 children while another has 1)
   - Sibling distinctness (no duplicate-sounding summaries)
   - Coverage (every paragraph is referenced somewhere)
   - Appropriate depth (leaves are actual concrete topics, not bucket categories)
   - Returns `CriticFeedback` with specific edits requested

3. **Judge (Tree of Thoughts):** runs Proposer 3× with different temperature, picks best by rubric score

- **Iteration:** Proposer → Critic → revised Proposer → final; max 2 critic rounds

### Stage 5 — Structural validation (no LLM)
- **Intra-sibling cohesion:** average pairwise cosine between sibling paragraph embeddings should exceed threshold (0.55)
- **Inter-parent divergence:** centroid of one parent's subtree should differ from another's by at least 0.15
- **Coverage:** every paragraph from extraction must be referenced in at least one leaf
- **Violations** → rejected, fed back to Gemma as specific error messages for one more revision pass
- If still failing after retry → emit warnings to admin review queue

### Stage 6 — Deduplication
- **MVP:** no-op
- **V2.1:** Layer 1 embedding similarity + Layer 2 Gemma judge

### Stage 7 — Content filling + Q&A verification
- **For each leaf skill:**
  1. Gemma writes the `.md` body using referenced source paragraphs
  2. Gemma generates 3 test questions from the source paragraphs
  3. Gemma answers each question using ONLY the written body
  4. Gemma judges: do answers match source? If yes → commit. If no → regenerate body with the gap flagged.
- **SKILL.md at each level** written similarly with focus on overview/summary rather than content

### Stage 8 — Emit skill folder
- Write `database/skills/<subject>/<book_slug>/**/SKILL.md` and `*.md` files
- Compute content hashes
- Stamp frontmatter with `ingested_at`, `ingestion_version: v2`

## 6. Frontend Changes (Explorer Update)

### Data flow change

**Before:** `frontend/public/data/manifest.json` → book JSON with pre-computed tree
**After:** Server component walks `database/skills/<subject>/<book_slug>/` and emits a tree shape the existing radial canvas already understands.

### New server-side reader

`frontend/src/app/explorer/page.tsx` gets a new helper:

```typescript
async function loadSkillFolder(bookSlug: string): Promise<BookData>
```

- Walks the skill folder
- Parses each `SKILL.md`/`*.md` frontmatter (use `gray-matter` npm package)
- Builds the nested `structure` in the existing `BookData` type
- Returns the same shape the canvas already renders — **minimal frontend code changes**

### Inspector drawer update

- **New "Content" section:** renders the `.md` body as markdown (use `react-markdown` + `remark-gfm`)
- **New "Source pages" chip:** from frontmatter `source_pages`
- **"View raw" toggle** (small button in header): switch between rendered markdown and raw frontmatter + body for QA

### Manifest update

Existing `frontend/public/data/manifest.json` stays, but points to skill folders instead of JSON files:
```json
[
  {
    "slug": "springboard_rajasthan_geography",
    "name": "Springboard Academy — Rajasthan Geography (RAS Pre)",
    "scope": "rajasthan",
    "subject": "geography",
    "skill_folder": "database/skills/geography/springboard_rajasthan_geography"
  }
]
```

### Old JSON files

- Keep `database/textbooks/*.json` (PageIndex output) as-is for reference
- New entries stop being added there
- Old explorer manifest entries pointing at these JSONs removed

## 7. Configuration

### Backend settings (add to `config.py`)

```python
model_ingestion: str = "google/gemma-4-31b-it"       # paid tier
model_critic: str = "google/gemma-4-31b-it"          # same model, different role
embedding_model: str = "BAAI/bge-small-en-v1.5"      # local
ingestion_max_critic_rounds: int = 2
ingestion_judge_samples: int = 3                      # Tree of Thoughts
```

### New Python dependencies

- `sentence-transformers` (~500MB, includes bge-small)
- `hdbscan`
- `python-frontmatter` (for reading/writing skill MD files)

### New JS dependencies

- `gray-matter` (parse frontmatter on server)
- `react-markdown` + `remark-gfm` (render MD in inspector)

## 8. File Structure (additions)

```
backend/
  ingestion_v2/
    __init__.py
    extract.py                  # Stage 1
    pre_structure.py            # Stage 2 (embeddings, segmentation, clustering)
    rag_prime.py                # Stage 3 (stub for MVP)
    multi_agent.py              # Stage 4 (Proposer/Critic/Judge)
    validation.py               # Stage 5
    dedup.py                    # Stage 6 (stub for MVP)
    content_fill.py             # Stage 7
    emit.py                     # Stage 8 (write skill folder)
    pipeline.py                 # orchestrator
  prompts_v2/
    proposer_system.md
    critic_system.md
    judge_system.md
    content_writer_system.md
    qa_verifier_system.md

scripts/
  ingest_v2.py                  # CLI: run full pipeline on one PDF

database/
  skills/
    geography/
      springboard_rajasthan_geography/   # emitted by Stage 8

frontend/
  src/
    lib/
      skill-folder-reader.ts    # NEW — walks skill folder, returns BookData
    app/explorer/
      components/
        MarkdownContent.tsx     # NEW — renders MD in inspector
        InspectorDrawer.tsx     # MODIFIED — adds Content section
      ExplorerClient.tsx        # unchanged
      page.tsx                  # MODIFIED — calls skill-folder-reader

docs/superpowers/
  specs/
    2026-04-17-v2-ingestion-pipeline-design.md  # this file
  plans/
    2026-04-17-v2-ingestion-pipeline.md          # to be written next
```

## 9. Acceptance Criteria (MVP)

1. `python scripts/ingest_v2.py --pdf /tmp/springboard.pdf --subject geography --book-slug springboard_rajasthan_geography` runs end-to-end in < 5 minutes
2. Skill folder is emitted at `database/skills/geography/springboard_rajasthan_geography/` with correctly nested `SKILL.md` files
3. Manual spot-check: 5 randomly sampled leaf skills have summaries that match their source pages (no hallucinations, no page mismatch)
4. `/explorer` loads the Springboard book from the skill folder
5. Clicking a node shows the rendered markdown body in the inspector
6. Radial canvas still renders correctly with the new data source
7. Build (`npm run build`) still passes
8. Old Contemporary India II book still visible in explorer (via unchanged JSON path) — dual-source support during migration

## 10. Risks

| Risk | Mitigation |
|------|------------|
| Gemma 4 31B output quality insufficient | Keep `LLMClient` abstraction — can swap to Sonnet 4.6 with one env var if needed |
| Embedding model slow on first run (cold cache) | Pre-warm on first-boot, cache on disk (sentence-transformers handles this automatically) |
| Coverage validation rejects too aggressively | Soft-fail with warnings for MVP; hard-fail only when >10% of paragraphs unreferenced |
| Gemma's JSON output malformed | Use tool-call (function calling) with strict schema — format errors become impossible |
| Springboard has scanned pages | Expected to be mostly text; if OCR needed, defer book to V2.1 and use a different book for MVP |

## 11. Open Questions (answer before planning)

None — design approved pending user final review.
