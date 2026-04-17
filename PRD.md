# PRD — Gemma Tutor for Rajasthan Govt Exam Aspirants

**Project codename:** Gemma Tutor (working name)
**Hackathon:** Gemma 4 Good Hackathon (Kaggle) — $200K prize pool
**Deadline:** 2026-05-18
**Team size:** Solo (1 person)
**Pilot subject:** Geography
**Track:** Future of Education

---

## 1. Problem Statement

Over 30 lakh students sit for Rajasthan government exams every year (Patwari, REET, RAS, RBSE 10/12, LDC, VDO). Selection rates are brutal — 0.2% for RAS, 0.5% for Patwari. Quality coaching costs ₹17k–₹1.5L per year plus living expenses in Jaipur/Sikar, pricing out the rural majority. Rural internet penetration in Rajasthan is 29.82 per 100 (TRAI 2024), making online coaching apps unusable where the aspirants actually live. Existing apps push identical content to every student — no personalization, no adaptive remediation, no on-device offline capability.

## 2. Solution

An offline-first, AI-powered personal tutor running Gemma 4 on-device that:

1. Teaches Geography from authoritative NCERT textbooks (Class 6 through Class 12) and RAS Prelims supplements
2. Answers doubts in natural Hindi or English with textbook page citations
3. Generates adaptive test series tuned to each student's weak topics using past exam patterns
4. Tracks mastery per topic over time using a spaced-repetition scheduler
5. Works fully offline after one-time content download
6. Costs nothing vs ₹1–2 lakh for coaching

## 3. Target User

**Primary:** Rural/tier-2 Rajasthan aspirant, age 18–28, Hindi-medium background, preparing for Patwari / REET / RAS Prelims / RBSE Class 10 or 12, limited budget for coaching, intermittent internet connectivity.

**Secondary:** Urban aspirants who want supplementary practice and personalized weak-area drills.

## 4. Goals and Non-Goals

### Goals (MVP, 33 days)
- Complete NCERT Geography Classes 6–12 ingested into searchable knowledge base **from official publishers only** (ncert.nic.in, rajeduboard.rajasthan.gov.in)
- Rajasthan-specific Geography content (from RAS Pre supplements) added **from official sources only**
- Functional chat tutor answering doubts with textbook citations
- Adaptive test generator producing MCQs tagged to weak topics
- Past-paper-informed question style (no LoRA, pure prompt engineering with few-shot)
- Per-user mastery tracking (FSRS-based)
- Hindi output quality validated on 30+ real questions
- Web app (Next.js) running locally with Ollama sidecar for Gemma 4
- Working offline demo, public GitHub repo, technical writeup, 3-minute video
- **Zero promotional content** in the knowledge base — four-layer cleaning pipeline (see `ARCHITECTURE.md §10`): source whitelist → regex cleaner → LLM cleanup pass → manual JSON review

### Non-Goals (explicitly deferred)
- Android APK (post-hackathon — Capacitor wrap)
- LoRA fine-tuning (prompt engineering first; revisit if time permits)
- Subjects beyond Geography (History, Polity, Economy — post-hackathon)
- Live web search tool (later stage — user-confirmed deferral)
- Cloud sync / multi-device (local-only for MVP)
- Voice input (Gemma 4 is multimodal, but defer to v2)
- MongoDB or any real database (JSON files only for MVP — swap later)
- **Ingestion from non-whitelisted sources** (Vedantu, Byju's, Utkarsh, Testbook, scribd, telegram mirrors, coaching PDFs) — source-hygiene rule, no exceptions. See `CLAUDE.md §3.1`.
- Hindi PDFs for MVP ingestion — **English-only textbook ingestion** (Gemma 4 still outputs Hindi answers via glossary-injected prompts). Avoids PyPDF2/PyMuPDF Devanagari extraction issues. Hindi PDFs are a post-MVP parallel tree if needed.

## 5. User Stories

### Core flow
1. **As a first-time user**, I open the app and pick my target exam (RBSE 10 / Patwari / REET / RAS Pre) and preferred language (Hindi / English). A 15-question onboarding quiz runs to seed my knowledge base.
2. **As a student**, I ask "चम्बल नदी का उद्गम कहाँ है?" in natural Hindi and get a tutor-style explanation citing NCERT Class 10 page 23, in Hindi.
3. **As a student preparing for Patwari**, I tap "Start adaptive test" and get a 20-question MCQ set biased toward my weak topics. Questions feel like real past papers.
4. **As a returning user**, I open the dashboard and see my mastery heatmap by topic, accuracy trend, and which topics are due for review.
5. **As a rural user on airplane mode**, I open the app and every feature still works — chat, test, dashboard — because Gemma runs locally via Ollama.

### Stretch flows
6. **As a student**, I ask "explain Aravalli formation like I am a 10th grader in Hindi" and get a Socratic back-and-forth.
7. **As a student**, I see a study plan for the next 14 days focused on my weakest 5 topics.

## 6. Success Metrics (Demo-Day)

- **Coverage:** All NCERT Geography Classes 6–12 ingested from ncert.nic.in, ≥95% of text content searchable
- **Source purity:** 100% of ingested books sourced from whitelisted official publishers; `grep -iE "vedantu|utkarsh|byju|telegram|http|@\w+"` over `database/textbooks/` returns **zero promotional residue**
- **Answer quality:** ≥80% of 30 curated Hindi test questions receive correct, cited, natural-Hindi answers
- **Retrieval accuracy:** ≥90% of questions return the correct textbook section on first retrieval
- **Offline:** Full flow (chat + test + dashboard) works with WiFi disabled
- **Latency:** Chat answer in ≤8 seconds on a MacBook with Gemma E4B via Ollama
- **Test adaptivity:** Generated tests biased ≥60% toward topics with mastery < 0.5
- **Repo quality:** Clean README, one-command setup, working demo script

## 7. Judging Alignment

| Criterion | Weight | Our pitch |
|---|---|---|
| Innovation | 30% | PageIndex vectorless hierarchical retrieval + Gemma 4 function-calling + past-paper pattern intelligence — nobody else will ship this stack |
| Impact | 30% | 30+ lakh annual Rajasthan aspirants, 0.2–0.5% selection, ₹1–2 lakh coaching cost, 29% rural internet penetration → quantified pain solved |
| Technical execution | 25% | End-to-end offline-capable pipeline (PDF → tree → on-device Gemma → adaptive tests → mastery dashboard) with cited answers |
| Accessibility | 15% | Offline-first, Hindi + English, free, runs on commodity hardware, bilingual UI |

## 8. Impact Data (for writeup and video)

- 24.76 lakh applicants for 53,749 Rajasthan peon jobs (2024) — includes PhDs, MBAs
- Patwari 2021: 10.41 lakh appeared for ~5,378 posts → 0.5% selection rate
- RAS: ~0.2% selection rate (1 in 450)
- REET 2024 Level-2: 11.55 lakh appeared
- RBSE 2024: 10.6 lakh (Class 10) + 8.66 lakh (Class 12)
- Rajasthan rural internet penetration: 29.82 per 100 (TRAI Mar 2024)
- 18.4 lakh registered unemployed in Rajasthan, 14.4 lakh are graduates
- Utkarsh offline Patwari coaching fee: ~₹17k + ₹60k living = ~₹77k minimum
- Median rural monthly household income in Rajasthan: under ₹10k

## 9. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| PageIndex retrieval latency (multi-step LLM calls) | High | Use smaller Gemma for traversal, 26B for final answer; cache common query patterns; stream answers |
| Hindi output quality below threshold | Medium | Terminology glossary injected into prompts; fallback to English if validation fails |
| Contaminated source PDFs (branded watermarks, coaching ads) | Medium | **Source whitelist + 4-layer cleaning pipeline** (CLAUDE.md §3.1, ARCHITECTURE.md §10); only official publishers allowed |
| PageIndex weak TOC on some textbooks | Medium | Day 6 exit criterion: inspect trees; hand-edit in flat JSON if needed; BM25 safety net as fallback |
| PageIndex vendoring bugs (no tests in upstream) | Medium | Vendor only 3 files, ~40 lines of edits; exercise with 1 real book on Day 2 before scaling |
| Scope creep in 33 days solo | High | Strict MVP scope; stretch features only after Day 25 |
| Ollama/Gemma too slow on judge's laptop | Medium | Benchmark before submission; smaller Gemma variant fallback; cache retrievals |
| Past-paper PDFs in weird formats | Medium | Manual curation of 3–5 papers if parser fails; fewer but higher-quality examples |

## 10. Deferred to Post-Hackathon

- Android APK wrapper (Capacitor or Tauri)
- LoRA fine-tuning on Rajasthan Geography QA (Unsloth prize track)
- Subjects beyond Geography (History, Polity, Economy, Current Affairs)
- MongoDB migration from JSON
- Multi-user cloud sync
- Web search tool for latest current affairs
- Voice input (Gemma 4 multimodal)
- TTS output for accessibility
- Teacher/parent dashboards
