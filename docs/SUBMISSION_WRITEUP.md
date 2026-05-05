# Gemma Tutor — Personalized AI Coaching for Rajasthan Exam Aspirants

**Kaggle submission · Gemma 4 Good Hackathon · 2026-05-18**

> A self-hosted AI tutor that turns publisher-clean textbooks into a *subject-canonical*, source-preserved skill tree, then lets any RAS Pre aspirant chat with a topic and generate verifiable mock tests grounded in the actual material.

---

## The Problem

Pooja, 23, is preparing for the Rajasthan Administrative Services Preliminary exam in Sikar. RAS Pre is the most-applied state exam in India — 1.6 million aspirants for 700 seats. Coaching costs ₹35,000+ per year. Her family can't afford it.

Free PDF mirrors exist but they are:

- Watermarked with coaching-brand identities that derail any retrieval system
- Fragmented across coaching versions with inconsistent quality and contradictory facts
- Partly in Hindi while the prescribed RBSE material is English-canonical, requiring on-the-fly translation a generic chatbot can't do without losing technical precision

Off-the-shelf tutoring chatbots either don't know the syllabus or hallucinate without citations. And the syllabus itself shifts: RAS Pre, Patwari, REET, RBSE Class 10 / 12 each weight different sub-topics differently.

What Pooja needs is something that **(a)** ingests her actual textbook, **(b)** answers questions with citations to the source paragraph, **(c)** generates mock tests she can verify against the source, and **(d)** runs offline so she can study during power cuts.

---

## What Gemma Tutor Does

1. **Ingests publisher-clean textbooks** (NCERT > RBSE) into a *subject-canonical* skill tree with verbatim source content — no LLM paraphrasing
2. **Merges multiple sources into one tree.** When NCERT Class 11 lands as a second source, its leaves merge into the existing Rajasthan Geography subject tree via cosine similarity + a Gemma judge. Each leaf carries a `sources[]` list internally; brand names never reach the UI
3. **Per-topic agentic Q&A** — student selects a topic, asks a question, an agent powered by Gemma 4 26B decides when to call a `lookup_skill_content` tool, then streams the answer with `[N]` citation pills wired to the source paragraph
4. **Verifiable mock tests** — generates 10 MCQs from the selected subtree, where every "correct" answer is a substring-verified span from the textbook
5. **Open-source, self-hostable** — Apache-2.0 codebase, runs on Ollama for offline study, hosted on Vercel for the live demo

[**Demo video** ← embed YouTube link here]

---

## Architecture

The whole product is **eight Gemma calls** plus deterministic glue.

### V2 Ingestion Pipeline (one-time per source)

```
PDF → Extract → OCR → Pre-structure → Decompose → Validate → Title Refine → Merge → Content Fill → Emit
        │       │           │             │            │           │           │           │           │
   PyMuPDF  Tesseract   bookmarks    Gemma agents  Pydantic    Gemma rewrite  cosine+   verbatim   YAML+MD
                                    (Proposer +   structural   leaf titles    Gemma     paragraphs subject-canonical
                                     Critic +     gate                        judge                folder
                                     Refinement)
```

**Key decisions** (full rationale in spec docs):

- **Tesseract OCR** added after auditing 2,503 embedded images across a 267-page source — 100% of pages had image-rendered content invisible to native PDF extraction (district names, table headers, diagram labels)
- **Pydantic structural validator** with retry-with-feedback: feeds the validation error back into the LLM prompt instead of giving up. Eliminated 28% silent misrouting we saw on V2.0
- **Title refinement** (Stage 6): Gemma reads each leaf's first paragraphs and rewrites the title to match content. Catches the "Lakes' leaf full of irrigation content" drift caused by Proposer picking section boundaries one header late
- **Stage 6.5 — multi-source merge.** Each new ingest's leaves match against the existing subject tree (cosine ≥ 0.92 → auto-merge; 0.80–0.92 → Gemma judge). Matches append a new `## Source N` body section; no-matches add a new leaf or chapter. Six unit tests pin every branch
- **Source preservation as architecture**: skill bodies are verbatim concatenations — no LLM paraphrasing. Less compact than summaries, but trustworthy citations and ground truth for MCQ generation

### Runtime

- **`/tutor/agent_chat`** — Gemma is exposed as an agent with a single `lookup_skill_content` tool. The model decides when to retrieve and what scope (`all` / `subject` / `node`) to ask for. Citations stream as `data-citation` events alongside `text-delta` events using the AI SDK UI Message Stream protocol; the Next.js client renders them as cross-linked `[N]` pills
- **`/tests`** — three-stage MCQ generator: schema-constrained JSON-mode generation → deterministic answer-span substring check → LLM judge for single-correct + leakage. Reject-rate budget 30%; oversample 13 candidates to ship 10
- **Frontend** — `/library/<subject>` is a canvas-first radial knowledge map; `/chat` is a dedicated agentic-tutor page with a left thread rail and right citations rail; `/tests` is a list + new-test modal + full-screen test mode + review screen. Brand-strip discipline is enforced by a Playwright E2E test (J1) that fails the build if "Springboard / Academy / RBSE / NCERT" appears in any rendered page

---

## Why Gemma 4

Gemma 4 26B (a4b-it) does every job — Proposer, Critic, Refinement, title rewriter, dedup judge, MCQ generator, MCQ judge, runtime agent — on the same paid OpenRouter slug. One model means one prompt-engineering target, one quality bar, one fallback path (Ollama for offline). At 4-bit the 26B model fits one A4000 — feasible for a state government to deploy on its own hardware. We chose Gemma over Claude / GPT-4o not just because the hackathon is Gemma-themed: it is the only open-weights model in this size class with a license clean enough for distribution to any state board's IT department.

---

## Innovation

1. **Subject-canonical, multi-source skill trees.** Most RAG systems either keep documents as separate corpora or merge them into a flat chunk store. We do neither: each subject has one canonical tree, and every leaf carries per-source provenance (`sources[]` with publisher, pages, paragraph_ids, authority_rank) in YAML frontmatter while presenting a unified `## Source 1`, `## Source 2` body. Merge is a real pipeline stage with a Gemma judge in the cosine grey zone (0.80–0.92), not a one-shot dedup script
2. **Agent + tool calling for chat.** The model decides when to retrieve. Scope-aware (`all` / `subject` / `node`) so judges can ask about one topic or the whole subject without manually filtering
3. **Source-preservation as architecture.** Most RAG demos either summarize-then-cite (citations point to summaries) or chunk-then-cite (citations point to broken sentences). We keep paragraph boundaries intact and treat the LLM as a router, not a writer
4. **Retry-with-feedback validation** got us from 28% silent misrouting to 0% on the Geography ingest by feeding validator errors back to the model
5. **Deterministic span verification** for MCQs. Every "correct" answer carries an `answer_span` that must be a verbatim substring of the cited paragraph — caught before paying for an LLM judge call
6. **Brand-strip discipline as a CI gate.** A Playwright E2E test fails the build if any rendered page contains publisher names. Non-trivial guarantee for a system whose source PDFs are studded with watermarks

---

## Impact

- **Direct beneficiaries**: ~50,000 RAS Pre aspirants per year, ~1.6M lifetime applicants. Coaching gap: ₹2K – ₹50K per year per student
- **Extends naturally** to Patwari (4 lakh aspirants), REET (3 lakh), RBSE Class 10 / 12 (1M+ students/year), and any other Indian state board with a published English-canonical syllabus
- **Open-source, Apache-2.0**: any state board's IT team can fork, plug in their textbook PDFs, host their own tutor
- **Per-student cost**: ₹0 marginal once self-hosted (Ollama + commodity hardware). Compare to ₹35,000 / year coaching

---

## Technical Highlights

- **8-stage ingestion pipeline** with 11 spec addendums documenting every design decision
- **105 unit tests** + **7 Playwright journeys** on critical paths: structural validator, OCR merge dedupe, retrieval, prompt builder, MCQ schema, span verifier, dedup winner-rule, multi-source merge, brand-strip guard
- **100% paragraph coverage** on the Rajasthan Geography ingest (1,061 / 1,061), with 100% title-content match on a 5-leaf spot-check
- **GitHub Actions CI** runs pytest + tsc + Playwright on every PR; the Playwright job catches brand leaks before they ship
- **Reproducible**: see [`README.md`](../README.md) Quickstart — `uv sync && uv run uvicorn server.main:app` for backend, `npm install && npm run dev` for frontend. Pre-ingested subject tree is live at `/library/rajasthan_geography` with no manual setup beyond `OPENROUTER_API_KEY`
- **Hosted on Vercel**: frontend (Next.js 16 native) + backend (FastAPI on Python Fluid Compute), single-domain deploy, free-tier sufficient for the demo window

---

## Try It

- **Hosted demo**: [Vercel URL — populated post-deploy] (read-only, pre-ingested with the Rajasthan Geography subject tree)
- **GitHub**: https://github.com/Mohit-5899/easilyclear
- **Run locally**: see [`README.md`](../README.md) Quickstart (Python 3.12, Node 22, `OPENROUTER_API_KEY`)
- **Kaggle Notebook**: [`docs/kaggle/gemma_tutor_demo.ipynb`](./kaggle/gemma_tutor_demo.ipynb) — 12 cells demonstrating ingest inspection, agentic Q&A, and MCQ generation end-to-end

---

## What's Next

After the hackathon:

- **NCERT Class 11 ingest** through the new merge stage — proves the second-source flow on the ground rather than just in tests
- **LoRA fine-tune** Gemma 4 4B on RAS-Pre-style answer phrasings (Unsloth +$10K stretch prize)
- **Hindi UI surface** — Gemma already generates Hindi answers from English-canonical content via glossary-injected prompts; the missing piece is the Hindi-first frontend
- **FSRS spaced repetition** per node_id — the missing piece for retention
- **Patwari + REET expansion** — same pipeline, different exam-coverage tags

---

*Built solo over 33 days. Every implementation choice has a research note or spec — check `docs/research/` and `docs/superpowers/specs/`. The hardest single decision was **source preservation over summarization**; everything else followed from that.*
