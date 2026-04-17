# CLAUDE.md — Engineering Guidelines

**Project:** Gemma Tutor — Personalized AI tutor for Rajasthan govt exam aspirants
**Hackathon:** Gemma 4 Good Hackathon (Kaggle), deadline 2026-05-18
**Owner:** Solo build

This file is the source of truth for how we work on this project. It overrides default behavior. Read it at the start of every session.

---

## 1. Core Principles

### 1.1 Think → Plan → Execute → Review
Never write code forcefully. Every meaningful change follows this sequence:

1. **Think** — Understand the problem. What are we trying to solve? Why? What is the smallest useful thing that would prove it works?
2. **Plan** — Write the plan down (even if short). List files that will change, decisions, tradeoffs, risks. If the plan is non-trivial, update `TASKS.md` or a session doc before touching code.
3. **Execute** — Implement the smallest slice that can be tested end-to-end. Prefer working vertical slices over horizontal layers.
4. **Review** — Read the diff. Does it match the plan? Does it violate SOLID? Is there dead code? Does it break anything else? Run the tests.

Skipping Think or Plan wastes more time than it saves. Skipping Review lets bugs compound.

### 1.2 Spec-Driven Development
- The PRD, ARCHITECTURE, and TASKS docs are the spec. Update the spec *before* the code, not after.
- If a decision changes mid-build, update the relevant doc in the same commit as the code change.
- New features start with: (a) a user story in `PRD.md`, (b) an API contract or schema in `ARCHITECTURE.md`, (c) tasks in `TASKS.md`, (d) code.
- When in doubt, write the spec first.

### 1.3 SOLID Principles
- **S — Single Responsibility:** One module, one reason to change. If a file is doing retrieval AND generation AND persistence, split it.
- **O — Open/Closed:** Extend via new modules, not by editing stable ones. Prefer composition over modification.
- **L — Liskov Substitution:** Subclasses and alternate implementations must be drop-in. Concretely: if we swap PageIndex for another retriever, the `Retriever` interface shouldn't leak PageIndex details into callers.
- **I — Interface Segregation:** Small, focused interfaces. No god-classes. `TutorClient` is separate from `TestEngine`.
- **D — Dependency Inversion:** High-level code depends on abstractions. `tutor/` depends on a `Retriever` protocol, not on `PageIndexClient` directly. This makes testing and swapping trivial.

### 1.4 Small Files, High Cohesion
- Target 200–400 lines per file, 800 hard max
- Extract utilities when files bloat
- Organize by domain (ingestion, retrieval, tutor, tests_engine), not by type (controllers, services, models)

### 1.5 No Premature Abstraction
- Three similar lines is better than a half-baked abstraction
- Only abstract when the second or third real caller appears
- Do not design for hypothetical future features
- Do not add backwards-compatibility shims on a 33-day hackathon build

### 1.6 Fail Fast, Trust Boundaries
- Validate only at system boundaries: API endpoints, user input, external data
- Trust internal module contracts — no defensive checks on things that can't happen
- Errors surface with real messages, not swallowed into None/empty

### 1.7 Know Your Tools Before Adding New Ones
When we adopt a library, we **learn its full feature surface** before reaching for a second one. Every redundant dependency is friction — more import lines, more versions to track, more places a future bug can hide, more cognitive load for a reader.

**The rule:** before `pip install X` or `npm install X`, ask:
1. Does the library we already use (Pydantic, FastAPI, Next.js, Zod, httpx, …) already do this?
2. If yes → use it. If no → add the new one.

**Pydantic is the canonical example** — people reach for separate libraries when Pydantic already handles:
- **Data validation** → don't add `attrs`, `marshmallow`, `cerberus`. Use `BaseModel`.
- **Settings / env config** → don't add `dynaconf`, `python-decouple`, raw `os.environ`. Use `pydantic-settings`.
- **JSON (de)serialization** → don't add `marshmallow`. Use `model_dump_json()` / `model_validate_json()`.
- **Type coercion** → don't add `cattrs`. Pydantic coerces by default; use `StrictInt`/`StrictStr` to opt out.
- **Field constraints** (min/max, regex, length) → don't add `validators`. Use `Field(..., ge=0, max_length=50, pattern=...)`.
- **Custom validators** → don't hand-roll. Use `@field_validator` / `@model_validator`.
- **Computed fields** → use `@computed_field`, not a property + extra serializer.
- **Discriminated unions** → use `Field(discriminator='type')`, not a manual dispatch.
- **Nested models, aliases, defaults, frozen, immutability** → all built in.

**On the frontend, Zod is the same story** — schema validation, type inference (`z.infer`), transforms, default values, discriminated unions, `.safeParse()` for non-throwing validation, `.brand<>()` for nominal types. Don't add Yup, Joi, io-ts, or ad-hoc type guards when Zod already covers it.

**Same for FastAPI** — dependency injection, background tasks, lifespan, middleware, request validation (via Pydantic), OpenAPI generation. Don't reach for `fastapi-utils` or similar without first checking that the feature isn't already core.

**Same for Next.js** — server components, data fetching, routing, middleware, metadata, image optimization, fonts, streaming. Don't add external routers, data fetchers, or image libraries without first ruling out the built-in.

**When in doubt:** spend 10 minutes reading the library's "features" page or changelog *before* adding a second dependency. That 10 minutes saves hours of reconciliation later.

---

## 2. Workflow

### 2.1 Daily Rhythm
Every working day:

1. **Start** — Open `TASKS.md`, find today's day, read the checklist. Open the previous `sessions/YYYY-MM-DD.md` to recall where things stood.
2. **Plan** — Create `sessions/<today>.md` from the template below. Write what you intend to do before doing it.
3. **Execute** — Work the checklist. Commit often with clear messages. Update the session doc as you go.
4. **Review** — End of day: mark completed items in `TASKS.md`, fill out the "What got done / What's pending / Decisions / Blockers" sections of the session doc. Commit.

### 2.2 Session Document Convention

**Location:** `sessions/YYYY-MM-DD.md` (one file per working day)

**Template:**
```markdown
# Session — YYYY-MM-DD (<Day of week>)

**Phase:** <phase name from TASKS.md>
**Day in plan:** Day N of 33
**Planned tasks:** <copy from TASKS.md>

## What got done
- <bullet> <bullet> <bullet>

## What's pending / slipped
- <items not completed and why>

## Decisions
- <any architectural or scope decisions made today>

## Blockers
- <anything stuck>

## Next session
- <what to start with tomorrow>
```

Keep each session doc to ~30–60 lines. These are a log, not a novel. Future-you (Day 33) will read backward through them to reconstruct the build.

### 2.3 Commit Messages
Format: `<type>: <description>`
Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

Examples:
- `feat: add PageIndex tree builder for NCERT Class 10`
- `fix: correct Hindi glossary injection in tutor prompt`
- `docs: update ARCHITECTURE with retrieval API contract`

One commit per logical unit of work. Spec updates go in the same commit as the code they describe.

---

## 3. Scope Discipline (read this when tempted)

The hackathon is won by a *working* end-to-end demo, not a half-built cathedral. Before adding any feature, ask:

1. Is it in `PRD.md` §4 Goals? → OK
2. Is it in `PRD.md` §4 Non-Goals? → Stop. Deferred.
3. Neither? → Write it down. Decide explicitly with this checklist:
   - Does it serve one of the judging criteria (Innovation / Impact / Tech / Accessibility)?
   - Can it be built in < 1 day without slipping the critical path?
   - Does it introduce new dependencies or make the demo harder to run?

**Explicitly deferred to post-hackathon** (from conversation on 2026-04-15):
- LoRA fine-tuning (prompt engineering + few-shot is sufficient for MVP)
- Android APK (Next.js web + Ollama is the hackathon target)
- Live web search tool (add in later stage)
- Subjects beyond Geography
- MongoDB migration (JSON files are the MVP storage)
- Voice input / TTS
- Multi-user cloud sync
- Hindi parallel knowledge base (English-canonical KB, Gemma outputs Hindi directly; Hindi tree only added if Day 9 validation fails)

### 3.1 Source Hygiene (non-negotiable)

**Ingest only from official publishers. No exceptions.**

| Source | Allowed? | Reason |
|---|---|---|
| `ncert.nic.in` | ✅ | Authoritative, no promotional content, English + Hindi official editions |
| `rajeduboard.rajasthan.gov.in/books` | ✅ | State-official, no ads |
| Vedantu, Byju's, Utkarsh, Testbook, Adda247, Drishti, scribd, telegram mirrors, coaching PDFs | ❌ **BANNED** | Branded, watermarked, legally grey, contaminates our knowledge base with promotional content |

**Why this matters:** If a scraped PDF has "Download from vedantu.com" watermarks or "Utkarsh App" footers, those strings end up in the PageIndex tree summaries → retrieved context → Gemma's answers. The tutor starts recommending third-party coaching institutes to students. Plus IP/copyright exposure for us.

**Pipeline enforcement:** every book in `database/textbooks/` carries a `source_url` and `source_authority` field in its JSON. Ingestion pipeline rejects any PDF whose source is not whitelisted. See `ARCHITECTURE.md §10`.

**Four-layer content cleaning** (also in `ARCHITECTURE.md §10`):
1. **Source hygiene** — only official publishers (handles 95% of the problem)
2. **Regex pre-filter** — strip URLs, handles, watermarks, coaching names after extraction, before PageIndex
3. **LLM cleaning pass** — targeted, only for pages flagged by the regex pass
4. **Manual JSON review** — grep the tree for residual contamination, hand-edit

---

## 4. Tech Stack (quick reference)

| Layer | Choice |
|---|---|
| Model runtime | Ollama + `gemma-4-e4b-it` (answers) and `gemma-4-e2b-it` (retrieval traversal) |
| Backend | Python + FastAPI |
| Retrieval | PageIndex (primary) + BM25 (fallback) |
| Frontend | Next.js 15 App Router + Tailwind + shadcn/ui |
| Database | JSON files in `database/` — swap to MongoDB post-hackathon if needed |
| Spaced repetition | FSRS per node_id |
| Language strategy | English-canonical KB, Gemma generates Hindi directly via glossary-injected prompts |

See `ARCHITECTURE.md` for full details, folder layout, and API contracts.

---

## 5. Folder Structure (quick reference)

```
gemma-4-good-hackathon/
├── CLAUDE.md           ← this file (engineering guidelines)
├── HACKATHON.md        ← competition requirements
├── PRD.md              ← product requirements
├── ARCHITECTURE.md     ← technical design
├── TASKS.md            ← day-by-day plan
├── README.md           ← setup + demo (Day 29)
├── backend/            ← Python / FastAPI
├── frontend/           ← Next.js
├── database/           ← JSON data layer
├── scripts/            ← one-off utilities
├── sessions/           ← daily session logs
└── docs/               ← design notes, writeup, demo script
```

---

## 6. Review Checklist (run before every commit)

- [ ] Does the code match the plan / spec?
- [ ] Are files under 800 lines?
- [ ] Does each module have a single responsibility?
- [ ] Are system boundaries the only place with validation?
- [ ] Is there any dead code, unused imports, commented-out blocks?
- [ ] Are error messages informative?
- [ ] Did the spec (PRD / ARCHITECTURE / TASKS) get updated if behavior changed?
- [ ] Did I update today's session doc?

---

## 7. When Stuck

If stuck for more than 30 minutes on one thing:
1. Write the problem down in today's session doc under "Blockers"
2. Walk away for 10 minutes
3. Come back and re-read the spec — did assumptions drift?
4. Try the simplest possible version that could work (throw away abstraction)
5. If still stuck, park it and move to the next task. Revisit with fresh eyes.

Do not grind. Grinding wastes days.
