# Gemma Tutor — Personalized AI Coaching for Rajasthan Exam Aspirants

**Kaggle submission · Gemma 4 Good Hackathon · 2026-05-18**

> A self-hosted AI tutor that turns publisher-clean textbooks into source-preserved skill folders, letting any RAS Pre aspirant chat with a topic and generate verifiable mock tests grounded in the actual material.

---

## The Problem

Pooja, 23, is preparing for the Rajasthan Administrative Services Preliminary exam in Sikar. RAS Pre is the most-applied state exam in India — 1.6 million aspirants for 700 seats. Coaching costs ₹35,000+ per year. Her family can't afford it.

Free PDF mirrors exist but they are:

- Watermarked with coaching brand identities ("SPRINGBOARD ACADEMY", "Visit Vedantu") that derail any retrieval system
- Fragmented across coaching versions (Springboard, Utkarsh, Drishti) with inconsistent quality
- Partly in Hindi while RBSE prescribed material is English-canonical, requiring on-the-fly translation a generic chatbot can't do without losing technical precision

Off-the-shelf tutoring chatbots either don't know the syllabus or make up answers without citations. And the syllabus itself shifts: RAS Pre, Patwari, REET, RBSE Class 10 / 12 each weight different sub-topics differently.

What Pooja needs is something that **(a)** ingests her actual textbook, **(b)** answers questions with citations to the source paragraph, **(c)** generates mock tests she can verify against the source, and **(d)** runs offline so she can study during power cuts.

---

## What Gemma Tutor Does

1. **Ingests publisher-clean textbooks** into a hierarchical skill tree with verbatim source content (no LLM paraphrasing)
2. **Per-topic streaming Q&A** — student selects a leaf, asks a question, gets a streamed answer with `[1]` citations linking to the exact source paragraph
3. **Verifiable mock tests** — generates 10 MCQs from the selected subtree, where every "correct" answer is a substring-verified span from the textbook
4. **Open-source, self-hostable** — Apache-2.0 codebase, runs on Ollama for offline study

[**Demo video** ← embed YouTube link here]

---

## Architecture

The whole product is **eight Gemma calls** plus deterministic glue.

### V2 Ingestion Pipeline (one-time per book)

```
PDF → Extract → OCR → Pre-structure → Decompose → Validate → Title Refine → Dedup → Content Fill → Emit
        │       │           │             │            │           │           │            │           │
   PyMuPDF  Tesseract   bookmarks    Gemma agents  Pydantic    Gemma rewrite  BGE+Gemma   verbatim     YAML+MD
                                    (Proposer +   structural   leaf titles    judge      paragraphs   skill folder
                                     Critic +     gate
                                     Refinement)
```

**Key decisions** (one per stage, full rationale in [spec docs](./superpowers/specs/2026-04-17-v2-ingestion-pipeline-design.md)):

- **Tesseract OCR** added after auditing 2503 embedded images across 267 pages of one Springboard book — 100% of pages had image-rendered content invisible to native PDF text extraction
- **Multi-agent decomposer** with Pydantic structural validator: catches null leaves, inverted ranges, and overlapping siblings at parse time, feeds the violation back to Gemma for retry-with-feedback. Eliminated 28% silent misrouting we saw on V2.0
- **Title refinement** as Stage 6: Gemma reads each leaf's actual first paragraphs and rewrites the title to match. Without this, leaf titles drift one section header late ("Lakes" leaf has irrigation content)
- **Source preservation**: skill bodies are verbatim concatenations — no LLM paraphrasing. Trade-off: less compact than summaries, but trustworthy citations and ground truth for the mock test generator

### Runtime

- **`/tutor/chat`** — BM25 over the selected node's subtree, prompt with numbered sources, Gemma streams response, FastAPI emits the AI SDK UI Message Stream protocol so Next.js `useChat` works natively
- **`/tests`** — Three-stage MCQ generator: schema-constrained JSON-mode generation → deterministic answer-span substring check → LLM judge for single-correct + leakage. Reject rate budget 30%; oversample to 13 to ship 10
- **Frontend** — Canvas-first radial knowledge map; clicking a node opens a tabbed inspector drawer (Content / Chat / Practice). Full-screen test mode with one-question stepper, persisted answers, color-coded review

---

## Why Gemma 4

Gemma 4 26B (a4b-it) does every job in the system:

- **Ingestion**: Proposer (decomposer), Critic, refinement, title rewriting, MCQ generator, MCQ judge, dedup judge — all on the same paid OpenRouter slug
- **Runtime**: tutor chat answers + mock test grading

One model means one prompt-engineering target, one quality bar, one fallback path (Ollama for offline). At 4-bit quantization the 26B model fits one A4000 — feasible for a state government to deploy on their own hardware.

We chose Gemma over Claude/GPT-4o not just because the hackathon is Gemma-themed: it's the only open-weights model in this size class with a license clean enough for distribution to any state board's IT department.

---

## Innovation

What's novel here:

1. **Source-preservation as architecture, not aspiration.** Most RAG demos either summarize-then-cite (citations point to summaries, not source) or chunk-then-cite (citations point to broken sentences). We keep paragraph boundaries intact and treat the LLM as a router, not a writer
2. **Pydantic structural validators with retry-with-feedback.** Instead of validating LLM output once and giving up, we feed the validator's exact error message back to the model and ask it to fix THAT leaf. 5 retries converge in 90% of runs; it's how we got from 28% misrouting to 0% on the Springboard ingest
3. **Title refinement as a separate stage.** A small (1-leaf-at-a-time) LLM pass that fixes systematic mislabeling without touching content. Cheap (~$0.10/book), independently testable
4. **Deterministic span verification** — the MCQ generator emits an `answer_span` field that's a verbatim substring of the source. We can verify groundedness without an LLM call. The LLM judge only catches semantic failures (multi-correct, leakage)

---

## Impact

- **Direct beneficiaries**: ~50,000 RAS Pre aspirants/year. ~1.6M lifetime applicants. Coaching gap: ₹2K-50K/year per student
- **Extends naturally** to Patwari (4 Lakh aspirants), REET (3 Lakh), RBSE Class 10/12 (1M+ students/year)
- **Open-source, Apache-2.0**: any state board's IT team can fork, plug in their textbook PDFs, host their own tutor
- **Per-student cost**: ₹0 marginal once self-hosted (Ollama + commodity hardware). Compare to ₹35K coaching

---

## Technical Highlights

- **8-stage ingestion pipeline** with 11 spec addendums documenting every decision (`docs/superpowers/specs/2026-04-17-v2-ingestion-pipeline-design.md`)
- **97 unit tests** + **7 Playwright journeys** on critical paths: structural validator, OCR merge dedupe, retrieval, MCQ schema, span verifier, dedup winner-rule, JSON utils, brand-strip guard
- **100% paragraph coverage** on the Rajasthan Geography ingest (1061/1061), with 100% title-content match on spot check
- **Reproducible**: see [`README.md`](../README.md) Quickstart — `uv sync && uv run uvicorn ...` for backend, `npm install && npm run dev` for frontend; pre-ingested subject tree is live at `/library/rajasthan_geography`. No manual setup beyond `OPENROUTER_API_KEY`.

---

## Try It

- **Hosted demo**: [GCP Cloud Run url — pending] (read-only, pre-ingested with Rajasthan Geography subject tree)
- **GitHub**: https://github.com/Mohit-5899/easilyclear
- **Run locally**: see [`README.md`](../README.md) Quickstart (Python 3.12, Node 22, `OPENROUTER_API_KEY`).

---

## What's Next

After the hackathon:

- Ingest NCERT + RBSE for full RAS Pre Geography coverage
- LoRA fine-tune Gemma 4 4B on RAS-Pre-style answer phrasings (target the +$10K Unsloth prize)
- Hindi UI surface (Gemma already generates Hindi answers from English-canonical content via glossary-injected prompts)
- FSRS spaced repetition per node — the missing piece for retention
- Patwari + REET expansion — the same pipeline, just different source whitelist

---

*Built solo over 33 days. Every implementation choice has a research note or spec — check `docs/research/` and `docs/superpowers/specs/`. The hardest single decision was **source preservation over summarization**; everything else followed from that.*
