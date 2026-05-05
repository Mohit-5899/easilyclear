"""Vercel Function entry — exposes the FastAPI ASGI app to Vercel.

Vercel auto-detects ``app`` exported at module level. The ``vercel.json``
rewrite sends every incoming path to ``/api/index``, so this one Function
handles the entire backend surface.

Local dev keeps using:
    uv run uvicorn server.main:app --host 127.0.0.1 --port 8010 --reload
"""

from __future__ import annotations

import sys
from pathlib import Path

# Vercel runs the Function with the entry file's directory on sys.path; the
# parent (`backend/`) holds our `server/`, `tutor/`, `llm/`, … packages,
# so add it explicitly so `from server.main import app` resolves.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from server.main import app  # noqa: E402  (sys.path tweak above is intentional)

__all__ = ["app"]
