# Architecture — Gemma Tutor

**Last updated:** 2026-04-15
**Status:** MVP design, solo build, 33 days to submission

---

## 1. High-Level Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Next.js Frontend                       │
│   Chat UI │ Test Runner │ Dashboard │ Onboarding │ Settings │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST (JSON)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                        │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Retrieval  │  │    Tutor     │  │   Test Engine      │  │
│  │ (PageIndex  │→ │ (Gemma 4 via │← │ (FSRS + question   │  │
│  │   + BM25)   │  │   Ollama)    │  │  bank + patterns)  │  │
│  └──────┬──────┘  └──────┬───────┘  └─────────┬──────────┘  │
│         │                │                    │             │
└─────────┼────────────────┼────────────────────┼─────────────┘
          │                │                    │
          ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                      JSON Database                         │
│  textbooks/ │ past_papers/ │ question_bank/ │ users/ │ ...  │
└─────────────────────────────────────────────────────────────┘
          ▲
          │ one-time ingestion
┌─────────┴───────────────────────────────────────────────────┐
│ NCERT PDFs (Class 6–12) + RAS Pre Geography supplements    │
└─────────────────────────────────────────────────────────────┘
```

## 2. Folder Structure

```
gemma-4-good-hackathon/
├── HACKATHON.md              # competition requirements
├── PRD.md                    # product requirements
├── ARCHITECTURE.md           # this file
├── TASKS.md                  # day-by-day task list
├── README.md                 # setup + demo instructions (Day 30)
│
├── backend/                  # Python / FastAPI
│   ├── api/                  # FastAPI routes
│   │   ├── main.py
│   │   ├── ask.py            # POST /ask — tutor Q&A endpoint
│   │   ├── test.py           # POST /test/generate, /test/submit
│   │   ├── user.py           # GET /user, POST /user/onboarding
│   │   └── mastery.py        # GET /mastery/heatmap
│   ├── ingestion/            # PDF → cleaned text → PageIndex tree
│   │   ├── source_whitelist.py  # allowed publishers (ncert.nic.in, rajeduboard)
│   │   ├── pdf_parser.py     # PyMuPDF wrapper (Devanagari-safe)
│   │   ├── text_cleaner.py   # regex + LLM cleaning passes
│   │   ├── tree_builder.py   # wraps vendored PageIndex
│   │   └── glossary_loader.py
│   ├── vendor/               # third-party code we fork and adapt
│   │   └── pageindex/        # vendored from github.com/VectifyAI/PageIndex (MIT)
│   │       ├── page_index.py    # edited: LLMClient injection
│   │       ├── utils.py         # edited: LLMClient injection, PyMuPDF default, semaphore
│   │       └── retrieve.py      # 3 tool functions (get_document/structure/page_content)
│   ├── retrieval/            # query → context
│   │   ├── pageindex_client.py  # LLM-guided tree walk
│   │   ├── bm25_index.py     # lexical fallback
│   │   └── hybrid.py         # merge PageIndex + BM25 results
│   ├── llm/                  # LLM client abstraction (dependency inversion)
│   │   ├── base.py           # LLMClient Protocol — unified interface
│   │   ├── openrouter.py     # OpenRouterClient (dev + build phase)
│   │   ├── ollama.py         # OllamaClient (offline demo)
│   │   └── factory.py        # picks implementation from LLM_PROVIDER env var
│   ├── tutor/                # prompt engineering + LLM calls
│   │   ├── prompts.py        # system prompts, few-shot templates
│   │   ├── hindi_output.py   # glossary injection, language switch
│   │   └── citation.py       # attach page refs to answers
│   ├── tests_engine/         # adaptive testing
│   │   ├── fsrs.py           # spaced repetition scheduler
│   │   ├── question_gen.py   # few-shot MCQ generation
│   │   ├── selector.py       # weak-topic biased selection
│   │   └── evaluator.py      # grade answers, update mastery
│   ├── prompts/              # raw prompt text files (editable)
│   │   ├── tutor_system_en.md
│   │   ├── tutor_system_hi.md
│   │   ├── mcq_gen_system.md
│   │   └── pageindex_traversal.md
│   ├── utils/
│   │   ├── json_db.py        # JSON read/write helpers
│   │   └── logging.py
│   ├── pyproject.toml        # uv / pip deps
│   └── requirements.txt
│
├── frontend/                 # Next.js 15 App Router
│   ├── app/
│   │   ├── page.tsx          # landing / onboarding
│   │   ├── chat/page.tsx     # tutor chat UI
│   │   ├── test/page.tsx     # test runner
│   │   └── dashboard/page.tsx
│   ├── components/
│   │   ├── ChatMessage.tsx
│   │   ├── Citation.tsx
│   │   ├── QuestionCard.tsx
│   │   ├── MasteryHeatmap.tsx
│   │   └── LanguageToggle.tsx
│   ├── lib/
│   │   └── api.ts            # backend REST client
│   ├── public/
│   ├── package.json
│   └── tailwind.config.ts
│
├── database/                 # JSON files (MVP)
│   ├── textbooks/            # PageIndex JSON trees
│   │   ├── ncert_class6_earth_our_habitat.json
│   │   ├── ncert_class7_our_environment.json
│   │   ├── ncert_class8_resources_development.json
│   │   ├── ncert_class9_contemporary_india_1.json
│   │   ├── ncert_class10_contemporary_india_2.json
│   │   ├── ncert_class11_physical_geography.json
│   │   ├── ncert_class11_india_physical.json
│   │   ├── ncert_class12_human_geography.json
│   │   ├── ncert_class12_india_people_economy.json
│   │   └── rajasthan_geography_supplement.json
│   ├── past_papers/          # parsed MCQs + metadata
│   │   ├── rpsc_ras_pre_2018.json
│   │   ├── rpsc_ras_pre_2021.json
│   │   ├── rsmssb_patwari_2016.json
│   │   ├── rsmssb_patwari_2021.json
│   │   └── reet_2022_level2.json
│   ├── patterns/             # derived examiner intelligence
│   │   └── geography_patterns.json
│   ├── question_bank/        # curated + generated MCQs
│   │   └── geography_qbank.json
│   ├── glossary/             # terminology
│   │   └── en_hi_geography.json
│   └── users/                # per-user state
│       └── user_<id>.json    # { knowledge_state, history, mastery }
│
├── scripts/                  # one-off utilities
│   ├── ingest_ncert.py       # bulk ingest NCERT PDFs
│   ├── parse_past_papers.py
│   ├── validate_hindi.py     # 30-question Hindi quality check
│   └── seed_glossary.py
│
└── docs/                     # design notes, diagrams
    ├── demo_script.md
    ├── api_contracts.md
    └── writeup.md            # hackathon technical writeup (Day 29)
```

## 3. Data Flow — Chat Tutor

```
User types: "चम्बल नदी का उद्गम कहाँ है?"
     │
     ▼
Frontend POST /ask { question, lang: "hi", user_id }
     │
     ▼
Retrieval layer
  ├─ PageIndex tree walk (Gemma E2B via Ollama)
  │    → identifies node_id: "ncert10/ch3/rivers/chambal"
  │    → returns section text + page number
  └─ BM25 fallback if PageIndex returns empty
     │
     ▼
Tutor layer
  ├─ Load prompts/tutor_system_hi.md
  ├─ Inject terminology glossary
  ├─ Inject retrieved context
  ├─ Call Gemma E4B via Ollama
  └─ Attach page citation to response
     │
     ▼
Frontend renders answer with citation badge
     │
     ▼
Log Q&A to user knowledge state (weak topic signal)
```

## 4. Data Flow — Adaptive Test

```
User taps "Start Test" (Patwari, 20 questions)
     │
     ▼
POST /test/generate { user_id, exam: "patwari", count: 20 }
     │
     ▼
Test Engine
  ├─ Read user mastery state
  ├─ Select 60% from weak topics (mastery < 0.5)
  ├─ Select 30% from due-for-review (FSRS scheduler)
  ├─ Select 10% from unexplored topics
  ├─ Pull from question_bank/ (pre-generated + curated)
  └─ If bank lacks a topic → live-generate via Gemma
       with 3-shot from past_papers matching topic+difficulty
     │
     ▼
Return 20 questions to frontend
     │
     ▼
User answers → POST /test/submit
     │
     ▼
Evaluator
  ├─ Grade each answer
  ├─ Update FSRS state per node_id
  ├─ Update mastery scores
  └─ Persist to users/user_<id>.json
     │
     ▼
Return score + per-topic breakdown
```

## 5. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Retrieval | PageIndex (vendored + adapted) primary + BM25 safety net | Explainable, matches textbook hierarchy, innovation signal. PageIndex is vendored into `backend/vendor/pageindex/` because upstream has no LLM injection point — we fork ~3 files, ~40 lines of diff, to route all calls through our `LLMClient`. |
| Content sourcing | Source whitelist (ncert.nic.in + rajeduboard.rajasthan.gov.in only) | Eliminates 95% of promotional contamination at layer 1. See §10. |
| PDF language | English-only ingestion for MVP | Gemma still outputs Hindi answers via glossary; English PDFs avoid PyPDF2/PyMuPDF Devanagari extraction issues entirely. |
| Model runtime | **OpenRouter API** (dev/build) → **Ollama** (offline demo) via `LLMClient` abstraction | Zero local system load during build; clean swap for offline demo; dependency-inversion-compliant |
| Model variant | Gemma 4 (E4B for answers, E2B for traversal) | E4B quality for user-facing text, E2B speed for retrieval loop |
| Backend language | Python / FastAPI | PageIndex is Python; Gemma/Ollama bindings mature |
| Frontend | Next.js 15 App Router + Tailwind + shadcn/ui | Fastest iteration, clean deployment, judges can run locally |
| Database | JSON files | Zero setup, inspectable, version-controllable, user-requested |
| State management | FSRS per node_id | Modern SR scheduler, better than SM-2/Leitner |
| Personalization | No LoRA | Prompt engineering + few-shot from past papers is sufficient for MVP |
| Hindi strategy | English-canonical KB, Gemma outputs Hindi directly | Halves ingestion work, leverages Gemma's multilingual capability |
| Terminology | English↔Hindi glossary injected into prompts | Cheap authenticity fix, 2 hours to build |

## 6. API Contracts (MVP)

```
POST /ask
  req:  { user_id, question, lang: "en" | "hi" }
  res:  { answer, citations: [{ book, chapter, page, snippet }], node_ids: [] }

POST /test/generate
  req:  { user_id, exam, count }
  res:  { test_id, questions: [{ id, text, options, topic_id, difficulty }] }

POST /test/submit
  req:  { test_id, answers: { [q_id]: option } }
  res:  { score, per_topic: {}, mastery_delta: {}, weak_topics: [] }

POST /user/onboarding
  req:  { exam, lang, initial_quiz_answers }
  res:  { user_id, initial_mastery }

GET /mastery/heatmap?user_id=<id>
  res:  { nodes: [{ node_id, title, mastery, last_review }] }
```

## 7. Dependencies

**Backend (Python):**
- `fastapi`, `uvicorn` — API server
- `pydantic`, `pydantic-settings` — schemas, env-driven config
- `httpx` — HTTP client for OpenRouter + Ollama (no LiteLLM, no openai SDK)
- `pymupdf` (aka `fitz`) — PDF parsing with better layout fidelity than PyPDF2
- `rank_bm25` — lexical search (BM25 safety net)
- **PageIndex — vendored, not pip-installed.** `pip install pageindex` installs a DIFFERENT package (their paid hosted SDK). We copy the 3 relevant files from github.com/VectifyAI/PageIndex (MIT) into `backend/vendor/pageindex/` and edit `utils.py` to route all LLM calls through our `LLMClient`. See §11 for the vendoring spec.
- `pyyaml` — PageIndex config compatibility

**Frontend (Node):**
- `next@15`, `react@18`
- `tailwindcss`, `shadcn/ui`
- `lucide-react` (icons)
- `recharts` (mastery heatmap)

**External runtime:**
- **Primary (dev + build):** OpenRouter API — Gemma 4 models accessed via HTTPS. Requires `OPENROUTER_API_KEY` in `.env`.
- **Offline demo (Day 26+):** Ollama with `gemma-4-e4b-it` and `gemma-4-e2b-it` pulled locally. Swap is a one-line `LLM_PROVIDER` env change — no caller code changes.

## 9. LLM Client Abstraction (Dependency Inversion in practice)

```python
# backend/llm/base.py — single interface all callers depend on
class LLMClient(Protocol):
    async def complete(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse: ...

    async def stream(self, ...) -> AsyncIterator[str]: ...
```

Two implementations behind it:
- `OpenRouterClient` — HTTPS POST to `openrouter.ai/api/v1/chat/completions`
- `OllamaClient` — HTTP POST to `localhost:11434/api/chat`

Factory picks one based on `LLM_PROVIDER=openrouter|ollama|mock`. `mock` returns deterministic fake responses for unit tests and for working without a key during early scaffold.

**Why this matters:** Every module in `retrieval/`, `tutor/`, `tests_engine/` depends on `LLMClient`, never on a concrete class. Swapping OpenRouter → Ollama at demo time is one env var. Zero code changes in retrieval or tutor layers.

## 8. Out-of-Scope Items (referenced from PRD §4)

No Android, no LoRA, no MongoDB, no cloud sync, no subjects beyond Geography, no web search tool, no voice, no TTS. No ingestion from non-whitelisted sources. No Hindi PDF ingestion for MVP. All deferred post-hackathon per solo-build scope discipline.

---

## 10. Content Ingestion Pipeline — source hygiene and cleaning

**Principle:** Noise in → noise out. If a scraped PDF has "Download from vedantu.com" watermarks or "Utkarsh App" footers, those strings end up in the PageIndex tree summaries → retrieved context → Gemma's answers. The tutor starts recommending coaching institutes to students. Plus IP/copyright exposure.

### 10.1 Source whitelist (Layer 1 — handles 95% of the problem)

Only these domains are allowed:

| Domain | Use |
|---|---|
| `ncert.nic.in` | NCERT Geography textbooks Class 6–12 (English editions) |
| `rajeduboard.rajasthan.gov.in` | RBSE supplements, Rajasthan-specific Geography |

**Enforcement:** `backend/ingestion/source_whitelist.py` exposes `is_allowed(url: str) -> bool`. The ingestion entry point rejects any PDF whose `source_url` is not whitelisted with a clear error message.

### 10.2 Four-layer cleaning pipeline

```
PDF download
    │
    ▼
[Layer 1] Source whitelist check ─→ reject if not official
    │
    ▼
PyMuPDF extraction → raw page text
    │
    ▼
[Layer 2] Regex pre-filter
    ├─ strip URLs (https?://, www.)
    ├─ strip coaching names (vedantu|utkarsh|byjus?|testbook|adda247|drishti|...)
    ├─ strip social handles (@\w{4,})
    ├─ strip "downloaded from X" watermarks
    ├─ strip injected pagination ("Page N of M")
    └─ strip copyright footers
    │
    ▼
Per-page text flagged as "clean" or "suspicious"
    │
    ▼
[Layer 3] LLM cleaning pass (only for flagged pages)
    ├─ Prompt: "Remove promotional content, preserve educational content exactly"
    └─ Via our LLMClient abstraction (any provider)
    │
    ▼
Cleaned page text → hand to vendored PageIndex builder
    │
    ▼
JSON tree written to database/textbooks/<book_slug>.json
    │
    ▼
[Layer 4] Manual JSON review
    └─ grep -iE "vedantu|utkarsh|byju|telegram|http|@\w+" database/textbooks/*.json
       → any hits → hand-edit (superpower of flat-file JSON storage)
```

### 10.3 JSON schema with source provenance

Every book tree carries provenance metadata at the root so we can prove purity and re-run cleaning deterministically:

```jsonc
{
  "doc_name": "NCERT Class 10 - Contemporary India II",
  "book_slug": "ncert_class10_contemporary_india_2",
  "doc_description": "...",

  "source_url": "https://ncert.nic.in/textbook/pdf/jess1dd.zip",
  "source_authority": "official",          // "official" | "rejected" (rejected never gets here)
  "source_publisher": "NCERT",
  "language": "en",

  // Subject-level scoping (MVP = Rajasthan Geography)
  "subject": "geography",                   // single-subject MVP; other subjects post-hackathon
  "subject_scope": "rajasthan",             // "rajasthan" | "pan_india" | "world"
                                            //   - rajasthan: Rajasthan-native content (RBSE supplements) — PRIMARY
                                            //   - pan_india: national content (NCERT) — SECONDARY fallback
                                            //   - world: global context — tertiary
  "exam_coverage": ["patwari", "reet", "ras_pre", "rbse_10"],  // which exams this book helps with

  "ingested_at": "2026-04-16T10:30:00Z",
  "cleaned_at": "2026-04-16T10:32:00Z",
  "cleanup_version": "v1",                 // bump when regex or LLM prompt changes
  "cleaner_layers_applied": ["whitelist", "regex", "llm_pass", "manual"],

  "pageindex_version": "vendored-2026-04-15",
  "llm_model_indexing": "google/gemma-4-26b-a4b-it",

  "structure": [
    { "title": "Resources and Development", "node_id": "0001", "start_index": 5, "end_index": 18, "summary": "...", "nodes": [...] },
    ...
  ]
}
```

### 10.4 Ingestion API contract

```
POST /textbooks/ingest
  req:  { source_url, book_slug, language: "en" }
  res:  { job_id, status: "queued" }

GET /textbooks/ingest/:job_id
  res:  { status: "running"|"done"|"failed", progress: 0..1, log: [...] }

GET /textbooks
  res:  { books: [{ book_slug, doc_name, source_authority, page_count, node_count, ingested_at }] }
```

Ingestion runs as a background task (expect 2–8 minutes per 150-page book). The API is internal — triggered from a CLI script during bulk ingestion, not exposed to end users.

---

## 11. PageIndex vendoring spec

**Why vendor and not pip-install:**
1. `pip install pageindex` installs a DIFFERENT package (VectifyAI's hosted cloud SDK, paid, not the OSS code).
2. The OSS repo at github.com/VectifyAI/PageIndex has no pip release for self-hosting.
3. The OSS code hardcodes LiteLLM for every LLM call — there is no injection point. To route through our `LLMClient`, we must edit `utils.py`.
4. Default PDF parser is PyPDF2 (poor layout fidelity); `page_index_main` does not forward a `pdf_parser=` kwarg, so we must fork `get_page_tokens` to default PyMuPDF.
5. **5 unbounded `asyncio.gather` sites** (page_index.py lines 92, 842, 937, 1025, 1061) will fire all LLM calls concurrently → instant OpenRouter rate-limit hits. All 5 must be wrapped with a shared semaphore.
6. `utils.py` also uses `litellm.token_counter` for bucketing pages into ~20K-token windows — needs a replacement (we use a `len(text)//4` heuristic, accurate enough for bucketing).
7. `llm_completion` has a **conditional return type** — `str` or `tuple[str, finish_reason]` based on `return_finish_reason` kwarg. Drop-in replacement must preserve both shapes.

**Files to vendor into `backend/vendor/pageindex/`:**

| File | Upstream size | Edits needed |
|---|---|---|
| `page_index.py` | 1153 lines | None (calls go through utils) |
| `utils.py` | 710 lines | **Rewrite `llm_completion` / `llm_acompletion`** (lines 32–82) to call our `LLMClient`. Default `get_page_tokens(..., pdf_parser="PyMuPDF")`. Add semaphore around `asyncio.gather` in `generate_summaries_for_structure` (line 589). |
| `retrieve.py` | 137 lines | None — three stateless tool functions, vendor as-is |

**Files NOT vendored:** `client.py` (workspace/UUID mode, not our pattern), `page_index_md.py` (markdown input), `__init__.py` (we write our own).

**Dependencies dropped vs upstream:** `litellm`, `openai-agents`, `PyPDF2` (we use PyMuPDF only).
**Dependencies kept:** `pymupdf`, `pyyaml`, `python-dotenv`.

**Retrieval is not a traversal algorithm:** it's an LLM agent calling `get_document()` / `get_document_structure()` / `get_page_content()`. The "tree walk" is tool-calling. We build a ~60-line agent loop in `backend/retrieval/pageindex_agent.py` that:
1. Loads `database/textbooks/<book_slug>.json`
2. Binds the three tools to this book via closures
3. Runs a tool-calling loop via our `LLMClient` (streaming final answer)
4. Returns answer + `[{node_id, start_index, end_index}]` citations

**Cost model per book indexing:** 100–250 LLM calls (TOC detection + summaries + verification). At Gemma 4 prices (~$0.08/$0.35 per M tokens), **< $5 for all 9 NCERT Geography books one-time**. Never re-run — commit the JSON trees to the repo.

**Cost model per query:** 3–6 tool calls, 2–5 seconds on OpenRouter Gemma 4, tokens dominated by node summaries (~200 per level × ~4 levels deep).

### BM25 safety net

`backend/retrieval/bm25_index.py` runs in parallel to PageIndex. If PageIndex returns low-confidence citations (e.g., top branch score below threshold), we fall back to BM25 over leaf summaries. ~50 lines, always-on second opinion. Rationale: LLM traversal has no backtracking — a single bad branch decision makes the correct leaf unreachable. BM25 is the cheap safety net.
