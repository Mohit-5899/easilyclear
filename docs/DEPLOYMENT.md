# Deployment — Vercel (frontend + backend)

> Two Vercel projects, one repo. Frontend talks to backend via `NEXT_PUBLIC_API_BASE_URL`. Free tier covers the hackathon demo (1M Function invocations / 100 GB-hours / 100 GB bandwidth per month — judges won't dent that).

## Prereqs

- Vercel account linked to GitHub (the repo `Mohit-5899/easilyclear` is already connected)
- Local `vercel` CLI installed (`npm i -g vercel`)
- `OPENROUTER_API_KEY` in hand (paid OpenRouter account; free tier 429s out under load)

## One-time setup

### 1. Backend project (FastAPI on Python Fluid Compute)

```bash
cd backend
vercel link            # pick "Create new project", name e.g. "gemma-tutor-api"
vercel env add OPENROUTER_API_KEY production
vercel env add LLM_PROVIDER production       # value: openrouter
vercel env add MODEL_ANSWER production       # value: google/gemma-4-26b-a4b-it
vercel env add MODEL_RETRIEVAL production    # value: google/gemma-4-26b-a4b-it
vercel env add MODEL_INGESTION production    # value: google/gemma-4-26b-a4b-it
vercel deploy --prod
```

The backend deploy reads `vercel.json`, which routes every incoming path to `api/index.py`. That file imports the FastAPI app from `server.main:app` and Vercel's ASGI runtime takes it from there.

Note the production URL printed at the end (e.g. `https://gemma-tutor-api.vercel.app`).

### 2. Frontend project (Next.js)

```bash
cd ../frontend
vercel link            # pick "Create new project", name e.g. "gemma-tutor"
vercel env add NEXT_PUBLIC_API_BASE_URL production   # paste the backend URL
vercel deploy --prod
```

That's it — open the frontend URL in a browser.

## Subsequent deploys

After this PR merges, every push to `main` auto-deploys both projects (Vercel watches the GitHub branch). Preview deploys land on every PR.

If you ever need a manual production redeploy:

```bash
cd backend  && vercel deploy --prod
cd frontend && vercel deploy --prod
```

## Constraints to remember

- **Ingest pipeline (~8 min) won't run on Vercel.** Function `maxDuration` is 300s. The pre-ingested `database/skills/rajasthan_geography/` tree ships with the repo, which is what the hosted demo serves. New ingests run locally via the README quickstart.
- **Filesystem is read-only** in Functions (except `/tmp`). All read-only routes work; admin write paths will fail in production. The admin UI is `?admin=1`-gated so judges won't trip them.
- **Mock test in-memory store** resets across cold starts. Within a single test session (~5 min) it holds; that's enough for demo flows.

## CORS

The Next.js proxy routes (`frontend/src/app/api/*`) forward to the backend, so the browser only ever talks to the same origin as the frontend. No CORS config needed on the backend.

## Cost ceiling

Free tier covers everything except OpenRouter usage (which is independent of Vercel). Estimated usage during the demo window:

- Function invocations: <500 / week from judge traffic — well under 1M / month free
- GB-hours: <0.5 — well under 100
- Bandwidth: <1 GB — well under 100

OpenRouter cost per Q&A is ~$0.01–0.05 depending on context length; per mock test ~$0.10–0.30.
