# Gemma Tutor

Personalized AI tutor for Rajasthan government exam aspirants, built for the [Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/google-gemma-4-good-hackathon).

**Pilot subject:** Geography · **Target exams:** RBSE 10/12, Patwari, REET, RAS Prelims · **Languages:** Hindi + English · **Model:** Gemma 4 (via OpenRouter during build, Ollama for offline demo)

See [`HACKATHON.md`](./HACKATHON.md) for competition rules, [`PRD.md`](./PRD.md) for product spec, [`ARCHITECTURE.md`](./ARCHITECTURE.md) for technical design, [`TASKS.md`](./TASKS.md) for the day-by-day build plan, and [`CLAUDE.md`](./CLAUDE.md) for the engineering workflow.

## Repo layout

```
backend/     Python / FastAPI — LLM abstraction, retrieval, tutor, test engine
frontend/    Next.js 16 + Tailwind v4 + Zod — chat, test runner, dashboard
database/    JSON data layer — textbook trees, past papers, question bank, users
scripts/     One-off utilities (ingestion, validation)
sessions/    Daily build logs (one file per working day)
docs/        Demo script, writeup, design notes
```

## Run locally

### 1. Backend

```bash
cd backend
cp .env.example .env    # defaults to LLM_PROVIDER=mock (no key needed)
uv sync
uv run uvicorn api.main:app --host 127.0.0.1 --port 8010 --reload
```

- `GET http://127.0.0.1:8010/health`
- `POST http://127.0.0.1:8010/llm/test` with `{"prompt": "..."}`

### 2. Frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npx next dev -p 3010
```

Open `http://localhost:3010` — the page pings `/health` on mount and has a "Send to LLM" button that round-trips through the backend's `LLMClient` abstraction.

### 3. Switching LLM providers

Edit `backend/.env`:

| `LLM_PROVIDER` | Needs | Use case |
|---|---|---|
| `mock` | nothing | no-key dev, unit tests, fast feedback |
| `openrouter` | `OPENROUTER_API_KEY` | build phase (current) |
| `ollama` | local Ollama + Gemma 4 pulled | offline demo (Day 26+) |

No caller code changes — the factory in `backend/llm/factory.py` picks the implementation at startup.

## Status

**Day 1 (2026-04-15) complete:** Backend + frontend scaffolds, `LLMClient` abstraction with mock/OpenRouter/Ollama implementations, end-to-end round-trip verified, CORS, Zod validation at the frontend boundary.

See [`sessions/`](./sessions/) for daily progress logs.
