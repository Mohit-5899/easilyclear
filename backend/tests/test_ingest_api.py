"""Smoke tests for the ingest admin API.

Per spec docs/superpowers/specs/2026-05-04-admin-upload.md. We don't run
the full V2 pipeline here (network / API key / minutes of runtime), just
verify routing, validation, and the in-memory job store.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from fastapi.testclient import TestClient

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from server.main import app


def test_branding_options_lists_known_bundles():
    client = TestClient(app)
    resp = client.get("/ingest/branding-options")
    assert resp.status_code == 200
    body = resp.json()
    keys = [opt["key"] for opt in body]
    assert "springboard_rajasthan" in keys


def test_ingest_rejects_unknown_branding():
    client = TestClient(app)
    files = {"file": ("x.pdf", io.BytesIO(b"%PDF-1.4 dummy"), "application/pdf")}
    data = {
        "subject": "geography",
        "book_slug": "test",
        "book_name": "Test",
        "branding": "definitely_not_a_real_bundle",
    }
    resp = client.post("/ingest", files=files, data=data)
    assert resp.status_code == 422
    assert "unknown branding bundle" in resp.json()["detail"]


def test_ingest_rejects_non_pdf_extension():
    client = TestClient(app)
    files = {"file": ("notes.docx", io.BytesIO(b"x"), "application/octet-stream")}
    data = {"subject": "geography", "book_slug": "t", "book_name": "T"}
    resp = client.post("/ingest", files=files, data=data)
    assert resp.status_code == 422
    assert ".pdf or .txt" in resp.json()["detail"]


def test_get_unknown_job_returns_404():
    client = TestClient(app)
    resp = client.get("/ingest/nonexistent-job-id")
    assert resp.status_code == 404


def test_events_unknown_job_returns_404():
    client = TestClient(app)
    resp = client.get("/ingest/nonexistent-job-id/events")
    assert resp.status_code == 404
