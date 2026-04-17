# V2 Ingestion Pipeline Implementation Plan

> **For agentic workers:** checkboxes track progress. Follow the spec at `docs/superpowers/specs/2026-04-17-v2-ingestion-pipeline-design.md`.

**Goal:** Build Gemma-only 8-stage ingestion pipeline; run end-to-end on Springboard Rajasthan Geography; update `/explorer` to read skill folders.

**MVP scope simplification:** Skip embeddings/HDBSCAN/Tree-of-Thoughts in V0 (they're architectural infrastructure for quality but not required to ship). Keep Proposer + Critic (core of the self-critique loop). Pre-structure uses PDF bookmarks if present, else flat paragraph list. Validation is coverage-only.

**Tech Stack:** Python (FastAPI backend) + PyMuPDF + python-frontmatter + OpenRouter (Gemma 4). Frontend: Next.js 16 + gray-matter + react-markdown.

---

## Phase A — Backend pipeline

### Task A1: Package skeleton + deps
- Create `backend/ingestion_v2/__init__.py`
- Create `backend/prompts_v2/` directory
- Add `python-frontmatter` to `backend/pyproject.toml`
- Run `uv sync`

### Task A2: Stage 1 — Extraction
- Create `backend/ingestion_v2/extract.py`
- Pydantic models: `Paragraph(page: int, text: str, bbox: tuple)`, `ExtractedDoc(paragraphs: list, bookmarks: list | None)`
- Function `extract_document(pdf_path: Path) -> ExtractedDoc`:
  - PyMuPDF `fitz.open(pdf_path)`
  - Iterate pages → extract text → split on double-newline or 40-word-min heuristic
  - Extract `doc.get_toc()` if present → bookmarks
- Commit

### Task A3: Stage 2 — Pre-structure (lite)
- Create `backend/ingestion_v2/pre_structure.py`
- Pydantic: `DraftHierarchy(candidate_chapters: list[CandidateChapter])` where `CandidateChapter = {title: str | None, paragraph_ids: list[int]}`
- Function `build_draft(doc: ExtractedDoc) -> DraftHierarchy`:
  - If bookmarks exist: group paragraphs by bookmark level-1 boundaries
  - Else: return single-chapter draft (Gemma has to discover structure from raw paragraphs)
- Commit

### Task A4: Prompts
- Create `backend/prompts_v2/proposer_system.md`: asks model to output a hierarchical tree of chapters + leaf subtopics, with rules about balance and first-principles structure
- Create `backend/prompts_v2/critic_system.md`: asks model to critique a proposed tree against rubric (balance, distinctness, coverage) and return structured feedback
- Create `backend/prompts_v2/content_writer_system.md`: asks model to write a skill .md body given source paragraphs
- Commit

### Task A5: Stage 4 — Multi-agent Gemma (Proposer + Critic only for MVP)
- Create `backend/ingestion_v2/multi_agent.py`
- Pydantic models:
  - `ProposedNode(title, description, paragraph_refs: list[int], children: list[ProposedNode])`
  - `ProposedTree(root_title, root_description, nodes: list[ProposedNode])`
- Function `run_proposer(llm, draft, extracted, existing_skills=[]) -> ProposedTree`
  - Renders a user prompt with: book metadata + all paragraphs (numbered) + draft hierarchy + (empty) existing skills
  - Calls `llm.complete_json(system, user, schema=ProposedTree.model_json_schema())`
  - Returns validated tree
- Function `run_critic(llm, proposed: ProposedTree, extracted: ExtractedDoc) -> CriticFeedback`
  - User prompt: the proposed tree + paragraph count
  - Returns `{issues: list[Issue], edits: list[EditRequest]}`
- Function `refine_with_critic(llm, initial: ProposedTree, feedback: CriticFeedback) -> ProposedTree`
  - Re-prompts Proposer with the feedback
- Function `decompose(llm, draft, extracted, max_critic_rounds=1) -> ProposedTree`:
  1. proposed = run_proposer()
  2. feedback = run_critic(proposed)
  3. if feedback has issues and rounds_left > 0: proposed = refine_with_critic(); continue
  4. return proposed
- Commit

### Task A6: Stage 5 — Validation (coverage only for MVP)
- Create `backend/ingestion_v2/validation.py`
- Function `validate_coverage(tree: ProposedTree, extracted: ExtractedDoc) -> ValidationResult`:
  - Collect all paragraph_refs from tree leaves
  - Check every paragraph in extracted.paragraphs is referenced
  - Return `{coverage: float, unreferenced: list[int], ok: bool}`
- Commit

### Task A7: Stage 7 — Content filling (simplified, no Q&A verification for MVP)
- Create `backend/ingestion_v2/content_fill.py`
- Function `fill_content(llm, tree: ProposedTree, extracted: ExtractedDoc) -> FilledTree`:
  - For each node (DFS): collect referenced paragraph texts, ask Gemma to write a coherent markdown body
  - `FilledNode = ProposedNode + {body: str, source_pages: list[int]}`
- Commit

### Task A8: Stage 8 — Emit skill folder
- Create `backend/ingestion_v2/emit.py`
- Function `emit_skill_folder(filled: FilledTree, subject: str, book_slug: str, book_metadata: dict, output_root: Path)`:
  - For each internal node: write `<slug>/SKILL.md` with frontmatter + body
  - For each leaf node: write `<slug>.md`
  - Numeric prefix by position: `01-location-and-borders/`, `02-physical-features/`, etc.
  - Compute content_hash (sha256 of body)
- Commit

### Task A9: Pipeline orchestrator
- Create `backend/ingestion_v2/pipeline.py`
- Function `run_pipeline(pdf_path, subject, book_slug, book_metadata, output_root) -> PipelineResult`:
  - extracted = extract_document(pdf_path)
  - draft = build_draft(extracted)
  - llm = get_llm_client(settings) with settings.model_ingestion
  - proposed = decompose(llm, draft, extracted)
  - validation = validate_coverage(proposed, extracted)
  - if not validation.ok: log warning but continue
  - filled = fill_content(llm, proposed, extracted)
  - emit_skill_folder(filled, subject, book_slug, book_metadata, output_root)
  - return PipelineResult(skill_folder_path, stats)
- Commit

### Task A10: CLI script
- Create `scripts/ingest_v2.py`
- Args: `--pdf`, `--subject`, `--book-slug`, `--book-name`, `--scope`, `--exam-coverage`
- Loads settings, runs `asyncio.run(run_pipeline(...))`
- Prints stats + skill folder path
- Commit

### Task A11: Config update
- Add `model_ingestion: str = "google/gemma-4-26b-a4b-it:free"` to `backend/config.py` (default to free tier; user can override)
- Add `MODEL_INGESTION` to `.env.example`
- Commit

### Task A12: Run on Springboard
- Locate Springboard PDF (check `/tmp/gemma-tutor-smoke/` first, then `/tmp/gemma-tutor-ingest/`)
- Run `python scripts/ingest_v2.py --pdf <path> --subject geography --book-slug springboard_rajasthan_geography --book-name "..." --scope rajasthan --exam-coverage ras_pre`
- Verify skill folder at `database/skills/geography/springboard_rajasthan_geography/`
- Spot check 3 skills for content accuracy
- Commit (skill folder into git)

---

## Phase B — Frontend skill folder reader + UI update

### Task B1: Frontend deps
- `cd frontend && npm install gray-matter react-markdown remark-gfm`
- Commit package.json + lock

### Task B2: skill-folder-reader.ts
- Create `frontend/src/lib/skill-folder-reader.ts`
- Function `readSkillFolder(folderPath: string): Promise<BookData>`:
  - Uses Node `fs/promises` + `path`
  - Walks the folder, parses each `.md` with gray-matter (frontmatter + body)
  - Builds the nested `structure` in the existing `BookData` shape
  - Each TreeNode adds a new optional field: `body: string | null` (the markdown content)
- Extend `types.ts` TreeNode with `body?: string | null`
- Commit

### Task B3: Update page.tsx
- Keep existing fetch-based flow for old JSON-backed books (NCERT)
- Add new path: if manifest entry has `skill_folder`, call `readSkillFolder()` at build time and pass the resolved BookData to ExplorerClient
- Update `manifest.json` to use `skill_folder` for Springboard entry
- Commit

### Task B4: MarkdownContent + InspectorDrawer update
- Create `frontend/src/app/explorer/components/MarkdownContent.tsx`:
  - Props: `body: string`
  - Uses `react-markdown` with `remark-gfm` plugin
  - Styled with prose/typography classes (manual since no @tailwindcss/typography installed — custom styles)
- Update `InspectorDrawer.tsx`:
  - If `node.body` present: render `<MarkdownContent body={node.body} />` in place of the summary paragraph
  - Else: fall back to `summary`
- Commit

### Task B5: Verify
- `npm run build` passes
- Dev server: open `/explorer`, select Springboard, click a few nodes, confirm:
  - Radial canvas renders with new skill-folder-based tree
  - Inspector shows rendered markdown
  - NCERT book (old JSON) still works
- Commit any fixes

---

## Acceptance

- [ ] Skill folder exists at `database/skills/geography/springboard_rajasthan_geography/`
- [ ] At least 3 chapters (depth 1) with at least 1 leaf each
- [ ] Leaf MD files have frontmatter + body
- [ ] `/explorer` loads Springboard from skill folder
- [ ] Inspector renders markdown
- [ ] NCERT still loads from old JSON path
- [ ] Build passes

## Execution

Dispatched as 2 phases: backend pipeline first (Tasks A1–A12), then frontend (B1–B5). Running Springboard in Task A12 is the "smoke test" before moving to frontend.
