# Demo Video Script — 3 minutes (target 2:55)

> Record at 1080p, 30fps. OBS or QuickTime; export `.mp4`, upload to YouTube as
> **Unlisted** (publishable later). Voiceover in clear English; consider Hindi
> subtitles via YouTube auto-translate (judge-friendly accessibility win).

## Pre-recording checklist

- [ ] Local stack up: `cd backend && uv run uvicorn server.main:app --port 8010 --reload` + `cd frontend && npm run dev` (port 3001)
- [ ] OR hosted demo URL working (Vercel deploy done)
- [ ] `OPENROUTER_API_KEY` set in `backend/.env` so chat + tests respond live
- [ ] Browser zoomed to 110% so text is legible at 1080p
- [ ] Hide bookmarks bar (`Cmd+Shift+B` in Chrome) for clean frame
- [ ] Close Slack / mail etc. (no notification banners)
- [ ] Have these tabs pre-loaded so cuts are clean:
  1. `http://localhost:3001/library/rajasthan_geography`
  2. `http://localhost:3001/chat`
  3. `http://localhost:3001/tests`
- [ ] Stopwatch / second display showing target timestamps

## Beat-by-beat

### 0:00 – 0:20 · Hook (20s)

**Visual:** Static hero card with Pooja's photo or stylized avatar, text overlay
"Pooja, 23 · RAS aspirant · Sikar district".
Cuts to a phone close-up of a watermarked PDF, then to ₹35,000 in cash.

**Voiceover:**
> Pooja is one of 1.6 million people who'll sit the Rajasthan
> Administrative Services exam. Coaching costs thirty-five thousand
> rupees a year — money her family doesn't have. Free PDFs are
> watermarked, fragmented, and partly in Hindi. Off-the-shelf chatbots
> hallucinate without citations.

### 0:20 – 0:50 · Library + source preservation (30s)

**Visual:**
- Open `/library/rajasthan_geography` — radial canvas appears, 13 chapter
  petals
- Hover a few petals to show subject scoping
- Click "Physiographic Divisions" → click "Aravalli Mountain Range" leaf
- The leaf opens; scroll to show `## Source 1 (pages 30-31)` header followed
  by verbatim paragraphs

**Voiceover:**
> Gemma Tutor ingests publisher-clean textbooks into a subject-canonical
> skill tree. Every leaf is verbatim source content — no LLM
> paraphrasing — with the publisher's exact paragraphs, page numbers,
> and a multi-source frontmatter for when a second source merges in.

### 0:50 – 1:30 · Agentic chat with citations (40s)

**Visual:**
- Click `/chat` in the sidebar
- Click the starter prompt **"Why is Aravalli called the planning region of Rajasthan?"**
- Watch the tool-call pill appear: `Searching Rajasthan Geography`
- Pill resolves: `Found 4 in Rajasthan Geography ✓`
- Streamed answer types in with `[1]` `[2]` citation markers
- Right rail shows source cards with snippets
- Hover a `[1]` marker → matching card highlights in the rail (cross-link)
- Hover the rail card → marker in the answer highlights

**Voiceover:**
> The chat is agentic. Gemma 4 is exposed as an agent with a single
> `lookup_skill_content` tool. The model decides when to retrieve and
> at what scope. Citations stream alongside text, cross-link to source
> paragraphs, and never name the publisher in the rendered UI — that
> stays in internal frontmatter for audit.

### 1:30 – 2:10 · Verifiable mock tests (40s)

**Visual:**
- Click `/tests` in the sidebar
- Click **"New test"** → modal opens, breadcrumb-picker shows
  "Physiographic Divisions › Aravalli Mountain Range"
- Pick that leaf, click "Generate"
- Loading state with the 3-stage progress (Generation → Span verify → Judge)
- 5 MCQs appear; click first question
- Answer; reveal correct answer with the `answer_span` highlighted in the
  source paragraph below
- Score screen at end

**Voiceover:**
> Mock tests are verifiable. Every "correct" answer carries an
> `answer_span` that must be a verbatim substring of the cited paragraph.
> Stage one generates ten candidates in JSON mode; stage two
> deterministically checks the substring exists; stage three is an LLM
> judge for single-correct and leakage. Reject rate budget thirty
> percent — we oversample to ship ten clean questions.

### 2:10 – 2:35 · Architecture flash (25s)

**Visual:**
- Cut to architecture diagram (`README.md` ASCII version, or a polished
  SVG export). Stages light up in sequence: Extract → OCR → Decompose →
  Validate → Title Refine → Merge → Content Fill → Emit
- Highlight Stage 6.5 — Merge — with NCERT + RBSE icons combining into
  one canonical tree

**Voiceover:**
> One Gemma 4 26B model does every job: ingestion, decomposition,
> title refinement, dedup judging, MCQ generation, MCQ judging, and the
> runtime agent. One prompt-engineering target, one quality bar. At
> 4-bit, the 26B model fits one A4000 — feasible for a state government
> to deploy on its own hardware.

### 2:35 – 2:55 · The pitch (20s)

**Visual:**
- Cut to text overlay: **Apache-2.0 · Self-hostable · ₹0 per student**
- GitHub URL on screen: `github.com/Mohit-5899/easilyclear`
- Then: live hosted URL (Vercel, populated post-deploy)

**Voiceover:**
> Open-source, Apache-2.0, runs on Ollama for offline study. Zero
> marginal cost per student. Ready to fork into Patwari, REET, or any
> state board's syllabus. Try it at the link below.

### 2:55 – 3:00 · End card (5s)

**Visual:** static end card with all three URLs + the Kaggle hackathon logo.

## Voiceover word count

Total ~370 words across 175 seconds — about 127 wpm, which lands as confident
but unhurried. Drop a sentence per beat if you slip past 3:00.

## Cut points if you're tight on time

In priority order — drop these to hit the cap:

1. The two hover cross-link demos in the chat section (saves 5s)
2. The 3-stage progress animation in the tests section (saves 4s)
3. Architecture flash trimmed to just merge stage (saves 8s)

## Filename convention

`gemma-tutor-demo-v1.mp4` for the upload, then `…-v2.mp4` etc. for re-cuts.
Keep the YouTube video unlisted until submission day; flip to public when you
paste the link into the Kaggle writeup.
