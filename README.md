# Gemma Tutor

> A personalized AI tutor for Rajasthan government exam aspirants — built on Gemma 4 26B for the [Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/google-gemma-4-good-hackathon) (Kaggle, deadline 2026-05-18).

**Pilot subject:** Geography · **Target exam:** RAS Pre · **Model:** Gemma 4 26B via OpenRouter (offline demo via Ollama)

---

## The problem in one paragraph

A Rajasthan exam aspirant in Sikar pays ₹35,000+ per year for coaching she can't really afford. Free PDF mirrors are watermarked, fragmented across coaching brands, and partly in Hindi while the prescribed RBSE textbooks are in English. Off-the-shelf chatbots either don't know the syllabus or don't cite sources — and "the syllabus" itself is a moving target across RAS Pre, Patwari, REET, and the four RBSE board variants.

**Gemma Tutor** ingests publisher-clean textbooks (NCERT-first, RBSE-second) into a structured, source-preserved **subject-canonical** skill tree, then lets the student chat with each topic and generate verifiable mock tests grounded in the actual textbook. Multiple sources covering the same subject merge into one tree; brand names never reach the UI.

## Demo at a glance

1. Open `/library/rajasthan_geography` — see the radial canvas of the subject (13 chapters)
2. Click any chapter — read the verbatim source paragraphs
3. Switch to **Chat** in the sidebar — ask *"why is Aravalli called the planning region?"* — get a streamed answer with `[1]` citation pills linking to source paragraphs
4. Switch to **Tests** — generate 10 MCQs grounded in the selected subtree, take the test, see the score with explanations and source spans

(Demo video coming for the Kaggle submission — see [`docs/superpowers/specs/2026-05-15-submission.md`](./docs/superpowers/specs/2026-05-15-submission.md).)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Browser — Next.js 16 App Router + Tailwind v4 + Zod (port 3001)    │
│  ┌────────────┐  ┌────────────┐  ┌────────┐  ┌─────────┐            │
│  │  /library  │  │  /chat     │  │ /tests │  │ /admin  │            │
│  │  canvas    │  │  agent UI  │  │ MCQ    │  │ ingest  │            │
│  └─────┬──────┘  └─────┬──────┘  └───┬────┘  └────┬────┘            │
└────────┼───────────────┼─────────────┼────────────┼─────────────────┘
         │               │             │            │
         ▼               ▼             ▼            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  FastAPI backend (port 8010)                                        │
│   ┌──────────────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│   │ /tutor/agent_chat    │  │ /tests CRUD  │  │ /ingest SSE     │   │
│   │ tool-calling agent + │  │ 3-stage MCQ  │  │ V2 pipeline     │   │
│   │ lookup_skill_content │  │ generator    │  │ as a job runner │   │
│   │ + AI SDK UI Message  │  │              │  │                 │   │
│   └──────────┬───────────┘  └──────┬───────┘  └────────┬────────┘   │
│              │                     │                   │            │
│              └─────────┬───────────┴───────────────────┘            │
│                        ▼                                            │
│           LLMClient Protocol (OpenRouter | Ollama | Mock)           │
└────────────────────────────────────┬────────────────────────────────┘
                                     │
                                     ▼
                       ┌─────────────────────────────────┐
                       │  Gemma 4 26B (a4b-it, paid)     │
                       │  via OpenRouter chat completions │
                       └─────────────────────────────────┘

                                     ▲
                                     │
┌────────────────────────────────────┴────────────────────────────────┐
│  V2 Ingestion Pipeline (8 stages, all Gemma-only)                   │
│   1. Extract  (PyMuPDF)                                             │
│   1.5 OCR     (Tesseract — recovers map labels & tables)            │
│   2. Pre-structure (TOC bookmarks → draft chapters)                 │
│   4. Decompose (Proposer → Critic → Refinement, 5-retry validator)  │
│   5. Validate (95% coverage gate, structural Pydantic checks)       │
│   6. Title refine (Gemma rewrites leaf titles from real content)    │
│   6.5 Dedup   (BGE cosine + Gemma judge across sources of a subject)│
│   7. Content fill (deterministic, source-preserving — NO LLM)       │
│   8. Emit     (subject-canonical folder, multi-source frontmatter)  │
└─────────────────────────────────────────────────────────────────────┘
```

### Why this design

- **Subject-canonical tree.** One tree per subject, not per book. Multiple sources covering the same subject (NCERT + RBSE + …) merge into a single canonical structure with `sources[]` provenance in every leaf's frontmatter. The UI never sees publisher names — internal audit fields stay internal. (Spec: [`docs/superpowers/specs/2026-05-04-subject-canonical-refactor.md`](./docs/superpowers/specs/2026-05-04-subject-canonical-refactor.md))
- **Source preservation.** Skill bodies are verbatim concatenations of the cleaned source paragraphs — no LLM paraphrasing. This is the load-bearing decision: students get the publisher's actual words, citations are trustworthy, and the mock-test generator has ground truth to verify against. (Spec: [`docs/superpowers/specs/2026-04-17-v2-ingestion-pipeline-design.md`](./docs/superpowers/specs/2026-04-17-v2-ingestion-pipeline-design.md), Addendum A.1)
- **Pydantic structural validator.** The Proposer occasionally emits null leaves or overlapping ranges. We catch that at parse time and feed the validation error back into a retry-with-feedback loop (up to 5 attempts). This eliminated ~30% silent misrouting we saw on V2.0. (Addendum A.9)
- **Tool-calling agent for chat.** `/tutor/agent_chat` exposes a `lookup_skill_content` tool to Gemma; the model decides when to retrieve, citations stream as `data-citation` events alongside text deltas via the AI SDK UI Message Stream protocol. (Spec: [`docs/research/2026-05-02-ux-redesign-architecture.md`](./docs/research/2026-05-02-ux-redesign-architecture.md))
- **OCR for image-rendered content.** Maps, tables, and section headers in some PDFs are raster images PyMuPDF can't read. Tesseract OCR recovers ~250+ paragraphs per book. (Addendum A.10)
- **Verifiable MCQs.** The generator emits an `answer_span` field — a verbatim substring of the cited paragraph that proves the correct answer. Stage 2 deterministically verifies the substring exists; Stage 3 is an LLM judge for single-correct + leakage. (Spec: [`2026-05-03-mock-test.md`](./docs/superpowers/specs/2026-05-03-mock-test.md))

---

## Quickstart

### Prerequisites

- Python 3.12+
- Node 22+
- [Tesseract](https://github.com/tesseract-ocr/tesseract) on `$PATH` (`brew install tesseract`)
- An OpenRouter API key (paid tier recommended; free tier 429s out under load)

### 1. Backend

```bash
cd backend
cp .env.example .env
# Edit .env — at minimum set OPENROUTER_API_KEY
uv sync
uv run uvicorn api.main:app --host 127.0.0.1 --port 8010 --reload
```

Health check: `curl http://127.0.0.1:8010/health`

### 2. Frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev          # runs on port 3001
```

Open `http://localhost:3001/library/rajasthan_geography` → click a chapter → use the **Chat** and **Tests** entries in the sidebar.

### 3. Run the full pipeline on a fresh PDF

```bash
cd backend && source .venv/bin/activate
MODEL_INGESTION=google/gemma-4-26b-a4b-it python ../scripts/ingest_v2.py \
  --source /path/to/book.pdf \
  --subject-slug rajasthan_geography \
  --book-slug ncert_class_11_geography \
  --book-name "Class 11 — India Physical Environment" \
  --authority-rank 0 \
  --scope rajasthan
```

Expected runtime: ~8 min on Gemma 4 26B paid tier (267-page book, with OCR + title refiner). Output lands at `database/skills/<subject-slug>/`. A second source on an existing subject must use `merge` (Stage 6.5) instead of `--overwrite-subject` so provenance is preserved across publishers.

---

## Repo layout

```
gemma-4-good-hackathon/
├── README.md                   ← this file
├── HACKATHON.md                ← Kaggle submission requirements
├── PRD.md                      ← product spec
├── ARCHITECTURE.md             ← technical design
├── TASKS.md                    ← day-by-day plan
├── backend/                    ← FastAPI + Pydantic
│   ├── ingestion_v2/           ← 8-stage pipeline (extract → emit)
│   ├── tutor/                  ← agent + lookup_skill_content tool
│   ├── tests_engine/           ← MCQ generator (3-stage)
│   ├── llm/                    ← LLMClient abstraction (OpenRouter/Ollama/mock)
│   ├── api/                    ← FastAPI routers (agent_chat, tests, health)
│   ├── prompts_v2/             ← System prompts for all V2 LLM stages
│   └── tests/                  ← 97 unit tests
├── frontend/                   ← Next.js 16 App Router
│   ├── src/app/(app)/          ← shared AppShell layout
│   │   ├── library/            ← canvas-first radial knowledge map
│   │   ├── chat/               ← tool-calling agent UI
│   │   ├── tests/              ← MCQ test list + new-test modal
│   │   ├── admin/              ← browser-based ingestion
│   │   └── settings/           ← preferences
│   ├── src/app/api/            ← Next.js → FastAPI proxy routes
│   └── e2e/                    ← Playwright sanity suite (J1–J5)
├── database/skills/            ← V3 subject-canonical folders
├── scripts/                    ← CLI utilities (ingest_v2.py, etc.)
├── docs/
│   ├── research/               ← decision-grade research notes (Phase 0)
│   └── superpowers/specs/      ← per-feature specs (spec-driven)
└── sessions/                   ← daily progress logs
```

---

## Test status

```bash
cd backend && uv run pytest -q
# 97 passed
```

```bash
cd frontend && npx playwright test
# 7 passed (J1 chat empty state, J2 library card, J3 canvas + redirects,
#           J4 tests modal breadcrumb, J5 sidebar localStorage)
```

Coverage focuses on the load-bearing logic: structural validator, OCR merge dedupe, JSON extraction, retrieval, prompt builder, AI SDK stream protocol, MCQ schema, span verifier, dedup winner-rule + cosine. Playwright J1 also enforces the brand-strip rule in the chat composer, empty state, and citations rail.

---

## Engineering principles

This repo follows the workflow in `CLAUDE.md` (gitignored — partner-mode operating contract):
- **Spec before code** — every feature lands with a spec under `docs/superpowers/specs/` (or research note under `docs/research/`)
- **TDD** — Pydantic + pytest for backend; Zod schemas at the boundary
- **Source hygiene** — non-negotiable. Only NCERT/RBSE-class official sources; coaching PDFs are banned outright (see `ARCHITECTURE.md §10`)
- **Brand-strip discipline** — internal `sources[].publisher` fields keep audit info; no publisher name ever reaches user-facing copy
- **Small files** — 200-400 lines typical, 800 max
- **No premature abstraction** — three similar lines beats a half-baked abstraction

---

## License

Apache-2.0 (see [`LICENSE`](./LICENSE)).

## Acknowledgements

- Built for the **Gemma 4 Good Hackathon** by Google + Kaggle
- Source-preservation pattern inspired by Anthropic Skills (YAML frontmatter + verbatim Markdown)
- PageIndex (V1, since deprecated) and BGE embeddings for retrieval primitives

---

## Status (2026-05-05)

| Feature | Status |
|---|---|
| V2.2 ingestion pipeline (extract → OCR → decompose → validate → refine → fill → emit) | ✅ Done, hardened |
| Subject-canonical refactor (V3 schema, multi-source frontmatter, brand-strip) | ✅ Done |
| Rajasthan Geography subject tree (13 chapters) | ✅ Ingested |
| Tutor agent (`/tutor/agent_chat`) — tool calling + Gemma streaming + AI SDK protocol | ✅ Done |
| Tutor chat UI (dedicated `/chat` page with tool pills + citations rail) | ✅ Done |
| Mock test generator backend (3-stage with span verification) | ✅ Done |
| Mock test UI (`/tests` index + new-test modal + full-screen mode + review) | ✅ Done |
| Cross-subject library canvas (`/library/<subject>`) | ✅ Done |
| Cross-source dedup core (cosine + winner rule) | ✅ Done |
| Playwright sanity suite (J1–J5, brand-strip guard) | ✅ Done |
| Second source ingest (NCERT Class 11 India Physical Environment) | ⏳ Awaiting |
| Stage 6.5 dedup wired into `merge.py` | ⏳ Pending |
| Hosted demo (GCP Cloud Run) + demo video + Kaggle writeup | 🚧 In progress |
