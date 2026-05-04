"""Admin upload endpoint — POST /ingest + SSE GET /ingest/{job_id}/events.

Per spec docs/superpowers/specs/2026-05-04-admin-upload.md.

Replaces ``python scripts/ingest_v2.py …`` for the demo. Streams real-time
stage events to the browser so the user sees the 8-stage V2 pipeline
progress without polling.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import get_settings
from ingestion_v2.pipeline import run_pipeline
from ingestion_v2.text_cleanup import BRANDING_BUNDLES


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/ingest", tags=["ingest"])


# Hackathon-scope persistence: in-memory, lost on restart. See spec for the
# post-hackathon migration plan.
_JOBS: dict[str, "IngestJob"] = {}
_QUEUES: dict[str, asyncio.Queue[dict]] = {}


JobState = Literal["queued", "running", "complete", "failed"]


class IngestJob(BaseModel):
    job_id: str
    state: JobState = "queued"
    book_slug: str
    book_name: str
    subject: str
    started_at: datetime
    completed_at: datetime | None = None
    skill_folder: str | None = None
    total_nodes: int | None = None
    total_leaves: int | None = None
    coverage: float | None = None
    error: str | None = None


async def _emit_event(job_id: str, event: dict) -> None:
    """Push an event into the job's queue (no-op if queue gone)."""
    queue = _QUEUES.get(job_id)
    if queue is None:
        return
    await queue.put(event)


async def _run_job(
    job_id: str,
    pdf_path: Path,
    subject: str,
    book_slug: str,
    book_metadata: dict[str, Any],
    branding: str | None,
) -> None:
    """Run the V2 pipeline and emit progress events."""
    job = _JOBS[job_id]
    job.state = "running"
    settings = get_settings()

    source_patterns = (
        list(BRANDING_BUNDLES[branding]) if branding else []
    )

    started = time.monotonic()
    await _emit_event(
        job_id,
        {
            "event": "stage_start",
            "stage": "extract",
            "at": datetime.now(timezone.utc).isoformat(),
        },
    )

    try:
        result = await run_pipeline(
            pdf_path=pdf_path,
            subject_slug=subject,
            book_slug=book_slug,
            book_metadata=book_metadata,
            settings=settings,
            source_patterns=source_patterns,
        )
        elapsed = time.monotonic() - started

        job.state = "complete"
        job.completed_at = datetime.now(timezone.utc)
        job.skill_folder = str(result.skill_folder)
        job.total_nodes = result.total_nodes
        job.total_leaves = result.total_leaves
        job.coverage = result.coverage

        await _emit_event(
            job_id,
            {
                "event": "pipeline_complete",
                "skill_folder": str(result.skill_folder),
                "total_nodes": result.total_nodes,
                "total_leaves": result.total_leaves,
                "coverage": result.coverage,
                "elapsed_seconds": elapsed,
            },
        )
    except Exception as exc:
        logger.exception("ingest job %s failed", job_id)
        job.state = "failed"
        job.completed_at = datetime.now(timezone.utc)
        job.error = f"{type(exc).__name__}: {exc}"
        await _emit_event(
            job_id,
            {
                "event": "stage_error",
                "error": job.error,
                "retriable": False,
            },
        )
    finally:
        # Sentinel so the SSE generator can exit.
        await _emit_event(job_id, {"event": "__done__"})


@router.post("", status_code=201)
async def create_ingest_job(
    background: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    subject: str = Form("geography"),
    book_slug: str = Form(...),
    book_name: str = Form(...),
    scope: str = Form("rajasthan"),
    exam_coverage: str = Form(""),
    publisher: str = Form("unknown"),
    branding: str | None = Form(None),
) -> dict:
    if branding is not None and branding not in BRANDING_BUNDLES:
        raise HTTPException(
            status_code=422,
            detail=f"unknown branding bundle '{branding}'. "
                   f"Valid: {sorted(BRANDING_BUNDLES.keys())}",
        )

    if not file.filename or not file.filename.lower().endswith((".pdf", ".txt")):
        raise HTTPException(status_code=422, detail="upload must be .pdf or .txt")

    job_id = uuid.uuid4().hex
    upload_dir = Path(tempfile.gettempdir()) / "gemma-tutor-ingest" / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = upload_dir / file.filename

    with pdf_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    book_metadata = {
        "name": book_name,
        "scope": scope,
        "exam_coverage": [s.strip() for s in exam_coverage.split(",") if s.strip()],
        "publisher": publisher,
        "source_url": "",
    }

    job = IngestJob(
        job_id=job_id,
        state="queued",
        book_slug=book_slug,
        book_name=book_name,
        subject=subject,
        started_at=datetime.now(timezone.utc),
    )
    _JOBS[job_id] = job
    _QUEUES[job_id] = asyncio.Queue(maxsize=1000)

    background.add_task(
        _run_job,
        job_id=job_id,
        pdf_path=pdf_path,
        subject=subject,
        book_slug=book_slug,
        book_metadata=book_metadata,
        branding=branding,
    )

    return {"job_id": job_id, "status_url": f"/ingest/{job_id}/events"}


class BrandingOption(BaseModel):
    key: str
    pattern_count: int


@router.get("/branding-options", response_model=list[BrandingOption])
async def list_branding_options() -> list[BrandingOption]:
    """Lists registered branding bundles. Declared BEFORE /{job_id} so the
    static path wins over the path parameter."""
    return [
        BrandingOption(key=k, pattern_count=len(v))
        for k, v in sorted(BRANDING_BUNDLES.items())
    ]


@router.get("/{job_id}", response_model=IngestJob)
async def get_job(job_id: str) -> IngestJob:
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


async def _event_stream(job_id: str) -> AsyncIterator[bytes]:
    queue = _QUEUES.get(job_id)
    if queue is None:
        yield f"data: {json.dumps({'event': 'stage_error', 'error': 'no such job'})}\n\n".encode()
        return
    while True:
        event = await queue.get()
        if event.get("event") == "__done__":
            yield b"data: [DONE]\n\n"
            return
        yield f"data: {json.dumps(event)}\n\n".encode("utf-8")


@router.get("/{job_id}/events")
async def stream_events(job_id: str) -> StreamingResponse:
    if job_id not in _JOBS:
        raise HTTPException(status_code=404, detail="job not found")
    return StreamingResponse(
        _event_stream(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


