# Tasks — Day-by-Day Plan

**Start:** 2026-04-15 (Wed)
**Submission deadline:** 2026-05-18 (Mon)
**Total days:** 33
**Buffer days:** 3 (Days 31–33)

Legend: `[ ]` todo · `[x]` done · `🎯` critical path · `✨` stretch

---

## Phase 1 — Foundation (Days 1–5, Apr 15–19)

### Day 1 — Apr 15 Wed — Environment + skeleton 🎯
**Decision (2026-04-15):** Use OpenRouter API instead of local Ollama during build. Build `LLMClient` abstraction so swap is one env var. Ollama returns for offline demo (Day 26+).
- [ ] Initialize backend: `uv init backend`, add FastAPI, pydantic, pydantic-settings, httpx
- [ ] Create `backend/config.py` with pydantic-settings reading `.env`
- [ ] Create `backend/llm/base.py` — `LLMClient` Protocol + `Message`, `LLMResponse` types
- [ ] Create `backend/llm/openrouter.py` — OpenRouter HTTPS client
- [ ] Create `backend/llm/ollama.py` — Ollama stub (raises NotImplementedError for now, filled in Day 26)
- [ ] Create `backend/llm/mock.py` — deterministic fake client for no-key dev
- [ ] Create `backend/llm/factory.py` — picks implementation from `LLM_PROVIDER` env
- [ ] Create `backend/api/main.py` — FastAPI app with `/health` and `/llm/test` endpoints
- [ ] Create `backend/.env.example` — documented env var template
- [ ] Initialize frontend: `npx create-next-app@latest frontend --app --ts --tailwind`
- [ ] Install shadcn/ui, add Button/Input/Card components
- [ ] Create `frontend/lib/api.ts` — backend REST client
- [ ] `frontend/app/page.tsx` — landing page with health check + LLM ping button
- [ ] Git init, `.gitignore` both sides, first commit
- [ ] Later (when user provides key): drop `OPENROUTER_API_KEY` in `backend/.env` → switch `LLM_PROVIDER=openrouter` → verify real response

### Day 2 — Apr 16 Thu — Vendor PageIndex + clean ingestion pipeline 🎯
**Decision locked (2026-04-15 evening):** PageIndex is **vendored**, not pip-installed. Upstream has no LLM injection point, hardcodes LiteLLM, defaults to PyPDF2, and fires unlimited concurrent gather calls. We copy 3 files, edit ~40 lines, route through our `LLMClient`. Also: source whitelist + 4-layer content cleaning before PageIndex ever sees a page. English PDFs only (skips Devanagari extraction issues entirely).

**Source whitelist + hygiene**
- [ ] Create `backend/ingestion/source_whitelist.py` — `is_allowed(url)` checks domain against `{ncert.nic.in, rajeduboard.rajasthan.gov.in}`
- [ ] Write unit test: 5 allowed URLs pass, 5 disallowed URLs (vedantu, byjus, scribd, telegram, github gist) fail

**Vendor PageIndex (fork ~3 files)**
- [ ] `git clone https://github.com/VectifyAI/PageIndex /tmp/pageindex-upstream`
- [ ] Copy `page_index.py`, `utils.py`, `retrieve.py` → `backend/vendor/pageindex/`
- [ ] Write new `backend/vendor/pageindex/__init__.py` exposing only the functions we use
- [ ] Edit `utils.py` `llm_completion` and `llm_acompletion` → call our `LLMClient` via `backend/llm/factory.py`
- [ ] Edit `utils.py` `get_page_tokens` → hardcode `pdf_parser="PyMuPDF"` as default
- [ ] Edit `utils.py` `generate_summaries_for_structure` → wrap `asyncio.gather` in an `asyncio.Semaphore(5)` to stay under OpenRouter rate limits
- [ ] Remove `litellm` imports; `uv remove litellm` if present; keep `pymupdf`, `pyyaml`
- [ ] Add dependency: `uv add pymupdf pyyaml`

**Text cleaner (Layers 2 + 3)**
- [ ] Create `backend/ingestion/text_cleaner.py`:
  - `regex_clean(text) -> (cleaned, was_suspicious)` — strips URLs, coaching names, handles, watermarks, injected pagination, copyright footers
  - `llm_clean(text, llm_client)` — targeted LLM cleanup pass for suspicious pages only
- [ ] Unit tests with 10 synthetic promotional strings + 10 clean educational strings

**First real ingestion**
- [ ] Download **NCERT Class 10 `Contemporary India II`** directly from `https://ncert.nic.in/textbook/pdf/jess1dd.zip` (14.4 MB zip, 9 per-chapter PDFs — `jess3` is History, do NOT confuse)
- [ ] Unzip, merge 9 chapter PDFs into a single document via PyMuPDF `insert_pdf` (NCERT does not ship a merged PDF)
- [ ] Write `backend/ingestion/tree_builder.py` — the clean entry point: whitelist check → PyMuPDF extract → regex clean → LLM clean → vendored PageIndex → write JSON
- [ ] Add `source_url`, `source_authority`, `source_publisher`, `language`, `ingested_at`, `cleaned_at`, `cleanup_version`, `pageindex_version`, `llm_model_indexing` fields to the root JSON (per ARCHITECTURE §10.3)
- [ ] Run builder end-to-end, save to `database/textbooks/ncert_class10_contemporary_india_2.json`
- [ ] **Expected cost:** < $0.50 on OpenRouter Gemma 4 paid tier
- [ ] **Expected time:** 2–8 minutes

**Verify (Layer 4 — manual review)**
- [ ] `grep -iE "vedantu|utkarsh|byju|telegram|http|@\w+" database/textbooks/ncert_class10_contemporary_india_2.json` → **zero hits expected** (NCERT original is clean)
- [ ] Visually inspect: Unit → Chapter → Topic hierarchy clean? Summaries factual? Page numbers correct?
- [ ] Count nodes; compare against table of contents of the physical book
- [ ] **Day 2 exit criterion:** one clean tree JSON committed, LLMClient routed through vendored PageIndex, tests pass

### Day 3 — Apr 17 Fri — Retrieval agent loop + BM25 safety net 🎯
**Context:** `LLMClient` already exists (Day 1). PageIndex is vendored (Day 2). Today we wire the agent loop that actually answers questions.
- [ ] Write `backend/retrieval/pageindex_agent.py`:
  - Load `database/textbooks/<book_slug>.json`
  - Bind the three retrieval tools (`get_document`, `get_document_structure`, `get_page_content`) as closures over the loaded tree
  - Run a tool-calling loop via `LLMClient` (OpenRouter → Gemma 4)
  - Return `{answer, citations: [{node_id, start_index, end_index, title}]}`
- [ ] Write `backend/retrieval/bm25_index.py`:
  - Build BM25 index over leaf-node summaries + titles
  - `query(text, top_k) -> [{node_id, score}]`
  - ~50 lines
- [ ] Write `backend/retrieval/hybrid.py`:
  - Primary: PageIndex agent
  - Fallback: BM25 top-3 if agent returns low confidence OR zero citations
- [ ] Unit test: 5 known Geography questions → correct section returned for ≥4 of 5
- [ ] Benchmark: measure LLM calls per query + latency (target: <6 calls, <5s)

### Day 4 — Apr 18 Sat — First end-to-end /ask 🎯
- [ ] Write `backend/prompts/tutor_system_en.md` — tutor persona, answer format
- [ ] Write `backend/tutor/prompts.py` — load prompt, inject context
- [ ] Write `backend/api/ask.py` — POST /ask, wire retrieval + Gemma
- [ ] Frontend: `app/chat/page.tsx` — minimal chat UI, one message + response
- [ ] Test end-to-end: "What is the Chambal river?" → answer with citation

### Day 5 — Apr 19 Sun — Citation rendering + buffer
- [ ] Implement citation attachment in `backend/tutor/citation.py`
- [ ] Frontend `Citation.tsx` component — shows book/chapter/page badge
- [ ] Fix Day 1–4 bugs, tidy structure
- [ ] **Milestone:** Ask any question about Class 10 Geography, get cited answer

---

## Phase 2 — Content + Hindi (Days 6–12, Apr 20–26)

### Day 6 — Apr 20 Mon — Bulk NCERT ingestion 🎯
- [ ] Download all NCERT Geography PDFs from **ncert.nic.in only** — Class 6, 7, 8, 9, 10, 11 (×2), 12 (×2) — 9 books
- [ ] Verify each download via `source_whitelist.is_allowed` (Day 2 code)
- [ ] Write `scripts/ingest_ncert.py` — batch runs of `tree_builder.ingest_pdf(...)` with progress log
- [ ] Kick off ingestion sequentially (avoid concurrent OpenRouter rate limits)
- [ ] **Expected total time:** 30–60 minutes; **expected total cost:** < $5
- [ ] For each tree: run Layer 4 grep (`grep -iE "vedantu|utkarsh|byju|telegram|http|@\w+"`) — **zero hits required**
- [ ] Validate 3 random trees by eye against their physical book TOC
- [ ] **Day 6 exit criterion (go/no-go for PageIndex strategy):** ≥7 of 9 trees look clean. If <7, fall back to TOC extraction + BM25 + LLM reranker (NOT vector RAG — embedder breaks offline story)
- [ ] Commit all 9 trees to the repo — never re-run indexing

### Day 7 — Apr 21 Tue — Rajasthan supplement + BM25 corpus
- [ ] Source Rajasthan-specific Geography content (RAS Pre PDFs, state supplements)
- [ ] Ingest into `database/textbooks/rajasthan_geography_supplement.json`
- [ ] Build BM25 index across ALL ingested trees
- [ ] Write `backend/retrieval/hybrid.py` — merge PageIndex + BM25, dedupe

### Day 8 — Apr 22 Wed — Terminology glossary + Hindi prompts 🎯
- [ ] Build `database/glossary/en_hi_geography.json` — 80–100 core terms (rivers, physiography, tribes, soils, crops)
- [ ] Write `backend/prompts/tutor_system_hi.md` — Hindi tutor persona
- [ ] Write `backend/tutor/hindi_output.py` — glossary injection
- [ ] Add `lang` parameter to `/ask` endpoint
- [ ] Frontend `LanguageToggle.tsx` — EN/HI switch

### Day 9 — Apr 23 Thu — Hindi quality validation 🎯
- [ ] Curate 30 real Hindi Geography questions from RPSC past papers
- [ ] Write `scripts/validate_hindi.py` — run all 30 through /ask
- [ ] Manually score each: correct / cited / natural Hindi?
- [ ] **Gate:** ≥80% pass. If fail → add Hindi NCERT parallel tree on Day 10

### Day 10 — Apr 24 Fri — Past paper parser
- [ ] Collect 5 years of RPSC past papers (RAS Pre + Patwari + REET)
- [ ] Write `scripts/parse_past_papers.py` — PDF → structured JSON
- [ ] Extract: question text, options, answer, year, section
- [ ] Save to `database/past_papers/*.json`

### Day 11 — Apr 25 Sat — Past paper → topic tagging
- [ ] Write classifier (Gemma few-shot) to tag each past question with `node_id`
- [ ] Run on all parsed past papers
- [ ] Build `database/patterns/geography_patterns.json` — question type frequency per topic
- [ ] Spot-check 20 tags for accuracy

### Day 12 — Apr 26 Sun — Buffer + integration testing
- [ ] Fix ingestion/retrieval/parsing bugs from Phase 2
- [ ] Run 50 random questions end-to-end, measure retrieval accuracy
- [ ] **Milestone:** Full NCERT + Rajasthan KB searchable in English + Hindi, past papers parsed

---

## Phase 3 — Adaptive Learning (Days 13–20, Apr 27–May 4)

### Day 13 — Apr 27 Mon — User state schema + FSRS 🎯
- [ ] Define `database/users/user_<id>.json` schema — knowledge_state, history, mastery
- [ ] Write `backend/utils/json_db.py` — safe read/write helpers
- [ ] Implement `backend/tests_engine/fsrs.py` — ease, interval, due date per node_id
- [ ] Unit test FSRS transitions

### Day 14 — Apr 28 Tue — Question generation pipeline 🎯
- [ ] Write `backend/prompts/mcq_gen_system.md` — MCQ generator persona
- [ ] Write `backend/tests_engine/question_gen.py` — few-shot with 3 past-paper examples matching topic+difficulty
- [ ] Generate 20 sample MCQs per chapter (live test)
- [ ] Save validated ones to `database/question_bank/geography_qbank.json`

### Day 15 — Apr 29 Wed — Question bank curation
- [ ] Manual review + fix of 100 generated MCQs
- [ ] Import 50 real past-paper MCQs directly into question bank
- [ ] Ensure every topic node has ≥3 questions

### Day 16 — Apr 30 Thu — Adaptive selector 🎯
- [ ] Write `backend/tests_engine/selector.py` — weighted sampling (60% weak / 30% due / 10% new)
- [ ] Write `backend/api/test.py` — POST /test/generate, /test/submit
- [ ] Write `backend/tests_engine/evaluator.py` — grade, update mastery, persist

### Day 17 — May 1 Fri — Onboarding quiz
- [ ] Curate 15-question onboarding quiz covering diverse topics
- [ ] Write `backend/api/user.py` — POST /user/onboarding
- [ ] Frontend onboarding flow: pick exam → pick language → 15Q quiz → home

### Day 18 — May 2 Sat — Test runner UI 🎯
- [ ] Frontend `app/test/page.tsx` — question card, options, progress bar
- [ ] Submit flow, result screen with per-topic breakdown
- [ ] Test full flow: onboarding → test → result

### Day 19 — May 3 Sun — Mastery dashboard
- [ ] Write `backend/api/mastery.py` — GET /mastery/heatmap
- [ ] Frontend `MasteryHeatmap.tsx` — topic grid colored by mastery
- [ ] Accuracy trend chart (recharts), study streak counter
- [ ] Frontend `app/dashboard/page.tsx`

### Day 20 — May 4 Mon — Socratic mode polish ✨
- [ ] Multi-turn chat history in /ask endpoint
- [ ] Frontend: persist chat session
- [ ] Tutor asks follow-up questions when student answer is shallow
- [ ] **Milestone:** Feature-complete MVP

---

## Phase 4 — Polish + Demo (Days 21–28, May 5–12)

### Day 21 — May 5 Tue — UI polish
- [ ] Tailwind/shadcn theme pass, consistent spacing
- [ ] Hindi-first defaults, font-family for Devanagari
- [ ] Empty states, loading skeletons, error toasts

### Day 22 — May 6 Wed — Offline validation 🎯
- [ ] Disconnect internet, run full flow: chat + test + dashboard
- [ ] Fix any network dependencies that sneak in
- [ ] Document offline startup: `ollama serve` → backend → frontend

### Day 23 — May 7 Thu — Performance + latency
- [ ] Profile /ask — identify slow steps
- [ ] Cache PageIndex traversals for common query patterns
- [ ] Target: <8s per chat answer, <3s per test question generation
- [ ] Measure on low-end hardware if possible

### Day 24 — May 8 Fri — End-to-end bug bash
- [ ] Run 20-question test sessions across 3 exam types
- [ ] Fix edge cases: empty answers, malformed JSON, retrieval misses
- [ ] Hindi output spot checks — 10 more questions

### Day 25 — May 9 Sat — Demo script 🎯
- [ ] Write `docs/demo_script.md` — exact flow for the 3-min video
- [ ] Rehearse on real hardware
- [ ] Prepare 5 scripted Hindi + 5 scripted English questions
- [ ] Prepare a "rural student" persona for video narrative

### Day 26 — May 10 Sun — Video recording 🎯
- [ ] Screen record demo flow (OBS / QuickTime)
- [ ] Record voiceover (EN + HI subtitles)
- [ ] Multiple takes, pick best

### Day 27 — May 11 Mon — Video editing
- [ ] Cut to ≤3 minutes
- [ ] Add title card, impact stats overlay, captions
- [ ] Background music (royalty-free)
- [ ] Export 1080p MP4

### Day 28 — May 12 Tue — Technical writeup 🎯
- [ ] Write `docs/writeup.md` — problem, approach, architecture, innovations, impact, results
- [ ] Include diagrams (architecture, data flow)
- [ ] Include impact stats with citations
- [ ] Max 2000 words

---

## Phase 5 — Submission (Days 29–33, May 13–18)

### Day 29 — May 13 Wed — Repo polish 🎯
- [ ] Write `README.md` — one-command setup, demo instructions, screenshots
- [ ] Clean up commit history, add LICENSE (MIT)
- [ ] Ensure `.gitignore` excludes `node_modules`, `__pycache__`, large PDFs
- [ ] Push to public GitHub repo

### Day 30 — May 14 Thu — Final polish pass
- [ ] Re-run demo from clean clone — does setup work?
- [ ] Fix any setup friction
- [ ] Update README with exact commands that worked
- [ ] Final writeup proofread

### Day 31 — May 15 Fri — Buffer 1
- [ ] Reserved for unexpected issues, re-recording video, final fixes

### Day 32 — May 16 Sat — Buffer 2
- [ ] Dry-run Kaggle submission
- [ ] Verify all 4 required components: code repo + demo + writeup + video
- [ ] Submit to Kaggle

### Day 33 — May 17 Sun — Final check
- [ ] Verify submission accepted on Kaggle
- [ ] Share public GitHub link
- [ ] **Submission deadline: May 18 Mon**

---

## Stretch Features (only if Phase 4 completes early)

- [ ] ✨ 14-day study plan generator
- [ ] ✨ Voice input via Gemma 4 multimodal
- [ ] ✨ PDF export of weekly progress
- [ ] ✨ Capacitor wrap into Android APK
- [ ] ✨ LoRA fine-tune on past papers (Unsloth prize track)

---

## Critical Path Summary

Days marked 🎯 are blockers for the MVP. If any slips, compress or drop stretch features. Days 9, 16, 22, 25, 26, 28, 29 are the most important — anything else can be trimmed.
