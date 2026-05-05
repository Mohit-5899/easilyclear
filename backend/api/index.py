"""Vercel Function entry — exposes the FastAPI ASGI app to Vercel.

Vercel auto-detects ASGI apps (FastAPI / Starlette / etc.) when a single
top-level `app` is found. The `vercel.json` rewrite at the project root
forwards every incoming path to `/api/index`, so this one file handles
the entire backend surface (`/health`, `/tutor/agent_chat`, `/tests`, …).

For local dev, keep using:
    uv run uvicorn server.main:app --host 127.0.0.1 --port 8010 --reload

This file is touched only when Vercel boots the cold instance.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Vercel runs functions with the Function file's directory on sys.path; the
# parent (`backend/`) is what holds our `server/`, `tutor/`, `llm/`, …
# packages, so add it explicitly.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from server.main import app  # noqa: E402  (sys.path tweak above is intentional)

# Vercel's ASGI runtime expects `app` exported at module level.
__all__ = ["app"]
