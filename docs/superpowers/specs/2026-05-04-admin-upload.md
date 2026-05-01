# Spec — Admin Upload UI (Day 25)

**Status**: draft · **Last updated**: 2026-05-01

## User story

An admin (in the demo: us) opens `/ingest`, drags in `RBSE_Class11_Geography.pdf`, picks the branding bundle from a dropdown, fills in subject/scope, clicks "Ingest". The page shows real-time progress through all 8 V2 pipeline stages (extraction, OCR, decompose, validate, refine, fill, emit). After ~10 minutes, the new skill folder is live on `/explorer`.

## Goals

- Replace `python scripts/ingest_v2.py …` CLI with browser UI for the demo
- Real-time stage progress (no polling — SSE)
- Resume from a stage if a later one fails (skip Stage 1.5 OCR if already cached, etc.)

## Non-goals

- Multi-tenant auth (no auth at all for hackathon — demo runs locally)
- Multi-file batch upload
- Edit existing skill folders post-ingest

## Architecture

```
Browser                       FastAPI                          Pipeline
───────                       ───────                          ────────
POST /api/ingest ─────► save PDF to /tmp/uploads/<job_id>/
(multipart)              insert IngestJob(state=queued)
       │                      │
       │                      ▼
       │                 spawn background task: run_pipeline_with_events
       │                      │
       ▼                      │   yields stage events to SSE channel
GET /api/ingest/<job_id>/events ◄─────┘
(SSE stream)
       │
       └─► UI updates 8 stage indicators
```

## API contract

### `POST /api/ingest` (multipart/form-data)

Fields:
- `file` (PDF, required)
- `subject` (string, default "geography")
- `book_slug` (string, required, kebab-or-snake-case)
- `book_name` (string, required)
- `scope` (string, default "rajasthan")
- `exam_coverage` (csv string, e.g., "ras_pre,patwari")
- `publisher` (string)
- `branding` (string, optional, must be in BRANDING_BUNDLES keys)

Response: `201 { "job_id": "uuid", "status_url": "/api/ingest/<job_id>/events" }`

### `GET /api/ingest/{job_id}/events`

`text/event-stream`. Event types:
- `{"event":"stage_start","stage":"extract","at":"2026-05-04T..."}`
- `{"event":"stage_progress","stage":"extract","message":"page 42/267","percent":15.7}`
- `{"event":"stage_complete","stage":"extract","summary":{"paragraphs":1061,"branding_stripped":1264}}`
- `{"event":"stage_error","stage":"decompose","error":"...","retriable":true}`
- `{"event":"pipeline_complete","skill_folder":"database/skills/.../","total_nodes":48,"coverage":1.0}`

### `GET /api/ingest/{job_id}` (status check, fallback to SSE)

`200 { "job_id": "...", "state": "running|complete|failed", "current_stage": "decompose", "started_at": "...", "completed_at": null }`

## File layout

```
backend/
├── api/
│   └── ingest.py           ← POST + SSE endpoint
├── ingestion_v2/
│   └── pipeline.py         ← MODIFIED to accept event_callback
└── tests/
    └── test_ingest_api.py

frontend/
└── src/
    └── app/
        └── ingest/
            ├── page.tsx
            ├── components/
            │   ├── UploadDropzone.tsx
            │   ├── BookMetadataForm.tsx
            │   ├── StageProgressList.tsx
            │   └── ResultPanel.tsx
            └── lib/use-ingest-events.ts    ← EventSource wrapper hook
```

## Pipeline modifications

`run_pipeline()` gains an optional `event_callback: Callable[[StageEvent], None] | None`. Each existing `logger.info("pipeline: stage X — ...")` is paired with `event_callback(StageEvent(...))`. No breaking changes to CLI use (callback defaults to None).

```python
async def run_pipeline(
    pdf_path: Path,
    ...,
    event_callback: Callable[[StageEvent], Awaitable[None]] | None = None,
) -> PipelineResult:
    ...
```

For SSE streaming, the API endpoint passes a callback that pushes events into an `asyncio.Queue` consumed by the SSE generator.

## Job storage

In-memory `dict[job_id, IngestJob]` for hackathon. Lost on restart. (Post-hackathon: SQLite or Redis.)

```python
class IngestJob(BaseModel):
    job_id: UUID
    state: Literal["queued", "running", "complete", "failed"]
    book_slug: str
    started_at: datetime
    completed_at: datetime | None = None
    skill_folder: Path | None = None
    error: str | None = None
```

## UI component tree

```
<IngestPage>
  ├── <UploadDropzone>            (idle: drag-drop area)
  ├── <BookMetadataForm>          (subject/slug/name/scope/branding)
  ├── <Button onClick={submit}>
  └── (after submit)
      ├── <StageProgressList>     (8 rows: pending/running/done/error)
      └── <ResultPanel>           (on complete: link to /explorer)
```

States:
- `idle` — show upload + form
- `uploading` — disable form, show "Uploading PDF..."
- `running` — disable form, show stage list with live progress
- `complete` — show result panel with link
- `failed` — show error, retry button

## Success criteria

- Upload Springboard PDF → see 8 stages stream → final skill folder matches the one produced via CLI (same `total_nodes`, `coverage`)
- Mid-pipeline failure (e.g., OpenRouter 429) shows clearly in UI; can retry without re-uploading
- Multiple parallel jobs don't crash (independent state)

## Edge cases

- **PDF too large** (>50MB): 413 with friendly message
- **Invalid branding bundle**: 422 with list of valid options
- **Slug already exists**: 409 with "skill folder already exists, choose a different slug"
- **SSE connection drops**: client reconnects to `/events?since=<last_event_id>` (out of scope; client just reloads and polls status)

## Testing (TDD)

- `test_ingest_api.py`:
  - 4 cases — happy POST returns job_id; SSE stream emits expected event sequence; invalid branding rejected; missing required fields rejected
  - Use mock pipeline that emits canned events; don't run real LLM in tests

## Open decisions

- **File storage location**: `/tmp/uploads/<job_id>/` — fine for hackathon, no security concerns
- **Stage replay** (resume from cached extraction): defer to post-hackathon
