# Gemma Tutor

> A personalized AI tutor for Rajasthan government exam aspirants — built on Gemma 4 26B for the [Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/google-gemma-4-good-hackathon) (Kaggle, deadline 2026-05-18).

**Pilot subject:** Geography · **Target exam:** RAS Pre · **Model:** Gemma 4 26B via OpenRouter (offline demo via Ollama)

---

## The problem in one paragraph

A Rajasthan exam aspirant in Sikar pays ₹35,000+ per year for coaching she can't really afford. Free PDF mirrors are watermarked, fragmented across coaching brands, and partly in Hindi while the prescribed RBSE textbooks are in English. Off-the-shelf chatbots either don't know the syllabus or don't cite sources — and "the syllabus" itself is a moving target across RAS Pre, Patwari, REET, and the four RBSE board variants.

**Gemma Tutor** ingests publisher-clean textbooks (NCERT-first, RBSE-second, vetted coaching as a fallback) into a structured, source-preserved skill tree, then lets the student chat with each topic and generate verifiable mock tests grounded in the actual textbook.

## Demo at a glance

1. Open `/explorer` — see the radial knowledge map of "Springboard Rajasthan Geography" (13 chapters, 34 leaves)
2. Click any leaf — read the verbatim source paragraphs
3. Switch to **Chat** — ask *"why is Aravalli called the planning region?"* — get a streamed answer with `[1]` citations linking to the source
4. Switch to **Practice** — generate 10 MCQs grounded in the selected subtree, take the test, see the score with explanations and source spans

(Demo video coming for the Kaggle submission — see [`docs/superpowers/specs/2026-05-15-submission.md`](./docs/superpowers/specs/2026-05-15-submission.md).)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Browser — Next.js 16 App Router + Tailwind v4 + Zod (port 3001)    │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │  /explorer  │  │ /test/[id]   │  │  /ingest     │                │
│  │  radial map │  │ test mode    │  │  upload PDF  │                │
│  └─────────────┘  └──────────────┘  └──────────────┘                │
│         │                │                  │                        │
└─────────┼────────────────┼──────────────────┼────────────────────────┘
          │                │                  │
          ▼                ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  FastAPI backend (port 8010)                                        │
│   ┌─────────────────┐  ┌──────────────┐  ┌──────────────────┐       │
│   │ /tutor/chat SSE │  │ /tests CRUD  │  │ /ingest SSE      │       │
│   │ BM25 retriever  │  │ 3-stage MCQ  │  │ V2 pipeline      │       │
│   │ + AI SDK proto  │  │ generator    │  │ as a job runner  │       │
│   └────────┬────────┘  └──────┬───────┘  └────────┬─────────┘       │
│            │                  │                   │                  │
│            └────────┬─────────┴───────────────────┘                  │
│                     ▼                                                │
│         LLMClient Protocol (OpenRouter | Ollama | Mock)              │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │
                                       ▼
                       ┌─────────────────────────────────┐
                       │  Gemma 4 26B (a4b-it, paid)     │
                       │  via OpenRouter chat completions │
                       └─────────────────────────────────┘

                                       ▲
                                       │
┌──────────────────────────────────────┴──────────────────────────────┐
│  V2 Ingestion Pipeline (8 stages, all Gemma-only)                   │
│   1. Extract  (PyMuPDF)                                             │
│   1.5 OCR     (Tesseract — recovers map labels & tables)            │
│   2. Pre-structure (TOC bookmarks → draft chapters)                 │
│   4. Decompose (Proposer → Critic → Refinement, 5-retry validator)  │
│   5. Validate (95% coverage gate, structural Pydantic checks)       │
│   6. Title refine (Gemma rewrites leaf titles from real content)    │
│   6.5 Dedup   (BGE cosine + Gemma judge across books)               │
│   7. Content fill (deterministic, source-preserving — NO LLM)       │
│   8. Emit     (skill folder = YAML frontmatter + verbatim Markdown) │
└─────────────────────────────────────────────────────────────────────┘
```

### Why this design

- **Source preservation.** Skill bodies are verbatim concatenations of the cleaned source paragraphs — no LLM paraphrasing. This is the load-bearing decision: students get the publisher's actual words, citations are trustworthy, and the mock-test generator has ground truth to verify against. (Spec: [`docs/superpowers/specs/2026-04-17-v2-ingestion-pipeline-design.md`](./docs/superpowers/specs/2026-04-17-v2-ingestion-pipeline-design.md), Addendum A.1)
- **Pydantic structural validator.** The Proposer occasionally emits null leaves or overlapping ranges. We catch that at parse time and feed the validation error back into a retry-with-feedback loop (up to 5 attempts). This eliminated ~30% silent misrouting we saw on V2.0. (Addendum A.9)
- **Title refinement pass.** Gemma sometimes picks paragraph boundaries one section header late, so leaf titles drift from content. Stage 6 reads each leaf's first paragraphs and rewrites the title to match what's there. (Addendum A.11)
- **OCR for image-rendered content.** Maps, tables, and section headers in coaching PDFs are raster images PyMuPDF can't read. Tesseract OCR recovers ~250+ paragraphs per book (district names, table headers, diagram labels). (Addendum A.10)
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

Open `http://localhost:3001/explorer` → click a node → use the **Chat** and **Practice** tabs.

### 3. Run the full pipeline on a fresh PDF

```bash
cd backend && source .venv/bin/activate
MODEL_INGESTION=google/gemma-4-26b-a4b-it python ../scripts/ingest_v2.py \
  --source /path/to/book.pdf \
  --subject geography \
  --book-slug my_new_book \
  --book-name "My New Book" \
  --scope rajasthan \
  --branding springboard_rajasthan   # optional, only for known coaching sources
```

Expected runtime: ~8 min on Gemma 4 26B paid tier (267-page book, with OCR + title refiner). Output lands at `database/skills/<subject>/<book-slug>/`.

---

## Repo layout

```
gemma-4-good-hackathon/
├── README.md                   ← this file
├── HACKATHON.md                ← Kaggle submission requirements
├── PRD.md                      ← product spec
├── ARCHITECTURE.md             ← technical design
├── TASKS.md                    ← day-by-day plan
├── CLAUDE.md                   ← engineering workflow / SOLID / spec-first
├── backend/                    ← FastAPI + Pydantic
│   ├── ingestion_v2/           ← 8-stage pipeline (extract → emit)
│   ├── tutor/                  ← BM25 retriever + chat streamer
│   ├── tests_engine/           ← MCQ generator (3-stage)
│   ├── llm/                    ← LLMClient abstraction (OpenRouter/Ollama/mock)
│   ├── api/                    ← FastAPI routers (chat, tests, health)
│   ├── prompts_v2/             ← System prompts for all V2 LLM stages
│   └── tests/                  ← 100+ unit tests
├── frontend/                   ← Next.js 16 App Router
│   └── src/app/
│       ├── explorer/           ← canvas-first radial knowledge map
│       ├── test/[testId]/      ← full-screen test mode + review
│       └── api/                ← Next.js → FastAPI proxy routes
├── database/skills/            ← V2 skill folders (YAML + Markdown)
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
# 101 passed
```

Coverage focuses on the load-bearing logic: structural validator, OCR merge dedupe, JSON extraction, BM25 retriever, prompt builder, AI SDK stream protocol, MCQ schema, span verifier, dedup winner-rule + cosine.

---

## Engineering principles

This repo follows the workflow in [`CLAUDE.md`](./CLAUDE.md):
- **Spec before code** — every feature lands with a spec under `docs/superpowers/specs/` (or research note under `docs/research/`)
- **TDD** — Pydantic + pytest for backend; Zod schemas at the boundary
- **Source hygiene** — non-negotiable. Coaching PDFs are flagged unofficial and gitignored; only NCERT/RBSE-class sources go in cleanly
- **Small files** — 200-400 lines typical, 800 max
- **No premature abstraction** — three similar lines beats a half-baked abstraction

---

## License

Apache-2.0 (see [`LICENSE`](./LICENSE)).

## Acknowledgements

- Built for the **Gemma 4 Good Hackathon** by Google + Kaggle
- Source-preservation pattern inspired by Anthropic Skills (YAML frontmatter + verbatim Markdown)
- PageIndex (V1) and BGE embeddings for retrieval primitives
- Springboard Academy for the Rajasthan Geography notes used in the demo

---

## Status (2026-05-01)

| Feature | Status |
|---|---|
| V2.2 ingestion pipeline (extract → OCR → decompose → validate → refine → fill → emit) | ✅ Done, hardened |
| Springboard Rajasthan Geography skill folder (13 ch / 34 leaves) | ✅ Ingested |
| Tutor chat (`/tutor/chat`) — BM25 + Gemma streaming + AI SDK protocol | ✅ Done |
| Tutor chat UI (Chat tab in InspectorDrawer) | ✅ Done |
| Mock test generator backend (3-stage with span verification) | ✅ Done |
| Mock test UI (Practice tab + full-screen test mode + review) | ✅ Done |
| Cross-book dedup core (cosine + winner rule) | ✅ Done |
| Second book ingest (RBSE Class 11 Geography) | ⏳ Awaiting PDF |
| Admin upload UI (browser-based ingestion) | ⏳ Planned |
| Submission package (demo video + Kaggle writeup) | 🚧 In progress |
