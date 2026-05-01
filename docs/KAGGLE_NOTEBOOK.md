# Kaggle Notebook — Gemma Tutor Demo

> This is the source-of-truth for the notebook we'll publish on Kaggle. Convert to `.ipynb` via `jupytext` or by pasting the cells into a fresh notebook.

```bash
# Convert to ipynb when ready to publish:
#   jupytext --to ipynb docs/KAGGLE_NOTEBOOK.md -o submission.ipynb
```

---

## Cell 1 — Markdown · Title

```markdown
# Gemma Tutor — Personalized AI Coaching for Rajasthan Exam Aspirants

A self-hosted AI tutor that turns publisher-clean textbooks into source-preserved skill folders, letting any RAS Pre aspirant chat with a topic and generate verifiable mock tests grounded in the actual material.

**Built for:** Gemma 4 Good Hackathon (Kaggle, 2026-05-18)
**Repo:** https://github.com/Mohit-5899/easilyclear
**Demo video:** [3-min YouTube]
**License:** Apache-2.0
```

---

## Cell 2 — Markdown · The problem

```markdown
## The problem

Pooja, 23, is preparing for the Rajasthan Administrative Services Preliminary exam in Sikar. RAS Pre is one of India's most competitive state exams — 1.6 million aspirants, ~700 seats. Coaching costs ₹35,000+ per year that her family can't afford.

Free PDFs exist but are watermarked, fragmented across coaching brands, and partly in Hindi. Off-the-shelf chatbots either don't know the syllabus or hallucinate without citations.

Gemma Tutor ingests publisher-clean textbooks (NCERT > RBSE > vetted coaching) into a hierarchical skill tree with verbatim source content, then lets the student chat with each topic and generate verifiable mock tests grounded in the actual textbook.
```

---

## Cell 3 — Code · Setup

```python
# %% [code]
!pip install -q openrouter PyMuPDF pytesseract rank-bm25 pydantic frontmatter sentence-transformers
!apt-get install -qq tesseract-ocr

import os, json
from pathlib import Path

# Set your OpenRouter API key as a Kaggle Secret named OPENROUTER_API_KEY
os.environ.setdefault("OPENROUTER_API_KEY", "<your-key-here>")
print("Setup complete.")
```

---

## Cell 4 — Markdown · Step 1: Inspect a pre-ingested skill folder

```markdown
## Step 1: Inspect a pre-ingested skill folder

We've pre-ingested the Springboard Academy "Rajasthan Geography" notes (267 pages → 1061 paragraphs after OCR, 13 chapters / 34 leaves, 100% paragraph coverage). Each leaf is a Markdown file with YAML frontmatter and verbatim source content.
```

---

## Cell 5 — Code · Show the tree structure

```python
# %% [code]
!git clone -q https://github.com/Mohit-5899/easilyclear /kaggle/working/gemma-tutor
import os
os.chdir("/kaggle/working/gemma-tutor")

# List the skill folder
!find database/skills/geography/springboard_rajasthan_geography -type f -name "*.md" | sort | head -30
```

---

## Cell 6 — Code · Read one leaf to see the source-preserved content

```python
# %% [code]
import frontmatter
from pathlib import Path

leaf = Path("database/skills/geography/springboard_rajasthan_geography/02-physiographic-divisions/03-characteristics-and-divisions-of-aravali.md")
post = frontmatter.load(leaf)

print("=== Frontmatter ===")
for k, v in post.metadata.items():
    print(f"  {k}: {v}")

print("\n=== Body (first 800 chars) ===")
print(post.content[:800])
```

---

## Cell 7 — Markdown · Step 2: Tutor Q&A

```markdown
## Step 2: Tutor Q&A — answer with source citations

The tutor agent does BM25 retrieval over the selected node's subtree, then asks Gemma 4 26B to answer using **only** those paragraphs, with `[N]` citation markers.
```

---

## Cell 8 — Code · Run a tutor query

```python
# %% [code]
import sys
sys.path.insert(0, "backend")

from tutor.retriever import build_retriever_for_node
from tutor.prompt import build_tutor_messages
from llm.openrouter import OpenRouterClient

retriever = build_retriever_for_node(
    Path("database/skills"),
    "geography/springboard_rajasthan_geography/02-physiographic-divisions/03-characteristics-and-divisions-of-aravali",
)
hits = retriever.search("Why is Aravalli called the planning region?", k=3)
print("Retrieved", len(hits), "paragraphs:")
for h in hits:
    print(f"  [score={h.score:.2f} page={h.page}] {h.snippet[:120]}…")

messages = build_tutor_messages(
    question="Why is Aravalli called the planning region?",
    node_title="Aravalli Mountain Range",
    hits=hits,
)

client = OpenRouterClient(api_key=os.environ["OPENROUTER_API_KEY"])
import asyncio
from llm.base import Message

response = asyncio.run(client.complete(
    [Message(**m) for m in messages],
    model="google/gemma-4-26b-a4b-it",
    temperature=0.3,
    max_tokens=400,
))
print("\n=== Tutor answer ===")
print(response.content)
```

---

## Cell 9 — Markdown · Step 3: Generate a verifiable mock test

```markdown
## Step 3: Generate a verifiable mock test

The mock test generator runs three stages:

1. **Generation** — Gemma 4 26B emits structured MCQs in JSON mode, with an `answer_span` field that's a verbatim substring of the cited paragraph
2. **Span verification** (deterministic, no LLM) — confirms `answer_span` actually appears in the source
3. **LLM judge** — confirms the question has a single correct answer and isn't solvable from general knowledge alone

We oversample to 13 candidates and keep the 10 that pass.
```

---

## Cell 10 — Code · Generate 5 questions on the Aravalli leaf

```python
# %% [code]
import asyncio
from tests_engine.orchestrator import build_mock_test

# Reuse the retriever's paragraph list as the corpus.
paragraphs = list(getattr(retriever, "_paragraphs", []))

test = asyncio.run(build_mock_test(
    llm=client,
    generator_model="google/gemma-4-26b-a4b-it",
    judge_model="google/gemma-4-26b-a4b-it",
    node_id="geography/springboard_rajasthan_geography/02-physiographic-divisions/03-characteristics-and-divisions-of-aravali",
    paragraphs=paragraphs,
    n=5,
    oversample_n=8,
    difficulty_mix=(2, 2, 1),
))

print(f"Generated {len(test.questions)} questions in {test.elapsed_seconds:.1f}s\n")
for i, q in enumerate(test.questions, 1):
    print(f"Q{i} [{q.difficulty}]: {q.prompt}")
    for k, v in q.choices.items():
        marker = "✓" if k == q.correct else " "
        print(f"  {marker} {k}: {v}")
    print(f"  Source span: \"{q.answer_span[:80]}…\"")
    print()
```

---

## Cell 11 — Markdown · How this scales

```markdown
## How this scales

The same pipeline works for any English-language textbook with a clean source:

- **NCERT Class 10/12** — pre-structured PDFs, ~10 min ingest time per book on the paid Gemma 4 26B tier
- **RBSE Class 10/12** — analogous structure for Rajasthan State Board
- **Patwari + REET** — different source whitelist, same code

Per-student cost is ₹0 once self-hosted (Ollama + commodity hardware). Compare to ₹35K/year coaching.

To add a new book: drop the PDF into `/ingest`, fill the metadata form, watch the 8 pipeline stages stream live. Skill folder appears in `/explorer` when done.
```

---

## Cell 12 — Markdown · Try the live demo

```markdown
## Try the live demo

- **Hosted demo**: [vercel-url] (read-only, pre-ingested with Springboard Rajasthan Geography)
- **GitHub**: https://github.com/Mohit-5899/easilyclear
- **Run locally**: `make demo` (Docker Compose + OpenRouter key in `.env`)

Built solo over 33 days. Every implementation choice has a research note or spec — check `docs/research/` and `docs/superpowers/specs/`.

The hardest single decision was **source preservation over summarization**; everything else followed from that.
```
