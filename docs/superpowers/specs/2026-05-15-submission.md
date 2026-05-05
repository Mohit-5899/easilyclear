# Spec — Kaggle Submission Package (Day 29–32)

**Status**: draft · **Last updated**: 2026-05-01

## Goal

Ship a complete, polished Kaggle submission for the Gemma 4 Good Hackathon by **2026-05-18 23:59 UTC** (≈ 2026-05-19 05:29 IST).

## Required artifacts (per research `2026-05-01-kaggle-submission.md`)

1. **Public Kaggle Writeup** (~1,400 words, markdown) — primary judging artifact
2. **Public Kaggle Notebook** (runnable on Kaggle GPU)
3. **Public GitHub repo** — Apache-2.0, README with one-command-per-tier quickstart (backend + frontend)
4. **YouTube demo video** (≤3 minutes, embedded in writeup)
5. **Cover image** (1200×630 in Media Gallery)
6. **Hosted demo URL** (Vercel preview + Cloudflare tunnel for FastAPI backend)

## Judging rubric (target weights)

- Innovation: 30%
- Impact: 30%
- Technical quality: 25%
- Accessibility: 15%

## Writeup structure (1,400 words)

```
# Gemma Tutor — Personalized AI Coaching for Rajasthan Exam Aspirants

## The Problem (200w)
Pooja, 23, RAS aspirant in Sikar. Coaching costs ₹35K/year she can't afford.
Free PDFs are watermarked, fragmented, partially in Hindi.
[stat about RAS aspirant population]

## What Gemma Tutor Does (200w)
- Ingests official + vetted coaching textbooks into a structured skill tree
- Per-topic streaming Q&A with citations to the actual source paragraph
- Generates verifiable mock tests grounded in textbook spans
- Runs locally on Ollama for offline study

## Demo Video (embedded)
[3-min video: Pooja's pain → ingest pipeline → tutor chat → mock test]

## Architecture (250w)
[Architecture diagram]
- V2 ingestion: PyMuPDF + Tesseract OCR + Gemma multi-agent decomposer
- Source-preserved skill folders (Anthropic Skills format)
- BM25-over-subtree retrieval, Vercel AI SDK 5 streaming
- Structural validator + title refiner (catches bugs at parse time)

## Why Gemma 4 (150w)
- Single model handles ingestion (Proposer/Critic), tutoring, test generation
- 26B at 4-bit fits one A4000 — feasible for offline distribution
- [comparison vs prior coaching apps]

## Innovation (150w)
- Source-preservation (verbatim, not paraphrased) → trustworthy citations
- Pydantic structural validator + retry-with-feedback loop teaches Gemma to fix its own malformed trees
- Title-refine pass corrects shift-by-one labeling (caught and fixed in our ingestion audit)

## Impact (150w)
- 50K+ RAS Pre aspirants/year, ₹2K-50K coaching gap
- Same architecture extends to Patwari, REET, RBSE Class 10/12 prep
- Open-source: any state board can plug in their textbook PDFs

## Technical Highlights (150w)
- 8-stage pipeline with 11 spec addendums documenting every design decision
- 17 unit tests on critical path (validator, OCR merge, JSON utils)
- 100% paragraph coverage on Springboard ingestion (1061/1061)

## Try It (50w)
- Hosted demo: <vercel-url>
- GitHub: github.com/Mohit-5899/easilyclear
- Run locally: see repo `README.md` Quickstart (Python 3.12, Node 22, OpenRouter key in `.env`)
```

## Demo video script (2:45 target)

```
[0:00-0:20] Hook: aspirant in Sikar, ₹35K coaching she can't afford, opens GeMma Tutor
[0:20-0:45] /explorer canvas — radial knowledge map of Rajasthan Geography
[0:45-1:15] Click leaf → Chat tab → asks question → streamed answer with [1] citation
[1:15-1:45] Practice tab → "Generate 10 questions" → MCQs appear → take test
[1:45-2:15] Review screen — score, correct answers, source paragraphs
[2:15-2:35] Architecture sketch — Gemma 4 powers ingestion, chat, test gen
[2:35-2:45] Open-source, Apache-2.0, run locally on Ollama
```

Recording: OBS or QuickTime, 1080p, edited in DaVinci Resolve. Voiceover in clear English; consider Hindi subtitles.

## Repo polish checklist

- [ ] README rewrite — pitch, screenshot, run instructions, architecture diagram
- [ ] Replace Claude Code attribution / co-author lines with neutral
- [ ] Apache-2.0 LICENSE file
- [ ] CONTRIBUTING.md (basic — for the open-source angle)
- [ ] One-command-per-tier quickstart verified end-to-end (backend `uv sync && uv run uvicorn ...`, frontend `npm install && npm run dev`)
- [ ] Architecture SVG (mermaid → SVG export, in `docs/`)
- [ ] One canned ingestion pre-run, skill folder committed (so judges don't need OpenRouter key)
- [ ] CHANGELOG.md tagged `v1.0-hackathon`

## Kaggle notebook

Single notebook reproducing:
1. Clone repo
2. Install deps (`uv pip install -r backend/requirements.txt`)
3. Pull pre-ingested skill folder (or run V2 ingestion on a small NCERT chapter)
4. Demo tutor chat with 3 reference questions
5. Demo mock test with 5 questions

Constraints: must run on Kaggle GPU (T4) with Internet enabled (OpenRouter calls). Cell outputs pre-populated so reviewers see results without running.

## Hosted demo

- **Frontend**: Vercel preview URL (free tier, GitHub-linked)
- **Backend**: Cloudflare Tunnel from local machine (free, no signup) OR Render free-tier (cold start risk)
- Pre-load Springboard skill folder
- Disable admin upload in production (read-only demo)

## Submission-day timeline (2026-05-18)

| Time | Task |
|---|---|
| 09:00 IST | Final repo green check, push final commit |
| 10:00 IST | Re-record demo if any issues, upload to YouTube |
| 11:00 IST | Lock writeup, paste into Kaggle |
| 12:00 IST | Submit Kaggle entry (notebook + writeup + repo link + video link) |
| 13:00 IST | Verify submission visible, share with friends for spot-check |
| 14:00 IST | Buffer for fixes |
| 23:59 UTC = 05:29 IST (May 19) | DEADLINE — must be in by here |

## Cut points if behind schedule

- Drop hosted demo (rely on local README quickstart only)
- Drop Kaggle Notebook (writeup + GitHub + video may be sufficient)
- Drop second book (one polished book is OK)

## Open verifications

- [ ] Confirm 1,400-word writeup limit (research note flagged this as inferred from sister hackathon, not the official Gemma 4 Good page)
- [ ] Confirm 3-minute video cap
- [ ] Confirm submission deadline timezone (UTC vs IST)
- [ ] Day 14 (2026-05-15) decision: Unsloth LoRA fine-tune for the +$10K prize?
