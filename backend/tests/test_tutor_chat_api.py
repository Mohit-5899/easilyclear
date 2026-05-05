"""Integration test for POST /tutor/chat endpoint (spec 2026-05-02-tutor-chat.md).

Uses TestClient with a mock LLM injected into app.state. Verifies the route
produces a valid AI SDK UI Message Stream and the response headers carry
the protocol marker the Next.js client expects.
"""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from llm.base import LLMResponse


class _FakeLLM:
    provider_name = "fake"

    def __init__(self, deltas: list[str]) -> None:
        self._deltas = deltas

    async def complete(self, *args, **kwargs) -> LLMResponse:
        raise NotImplementedError

    async def stream(self, messages, *, model, temperature=0.3, max_tokens=1024) -> AsyncIterator[str]:
        for d in self._deltas:
            yield d


@pytest.fixture
def app_with_skill_root(tmp_path: Path):
    from server.main import app

    # Build a tiny skill folder
    book = tmp_path / "geography" / "tinybook"
    book.mkdir(parents=True)
    (book / "SKILL.md").write_text(
        "---\nnode_id: geography/tinybook\n---\n## Contents\n"
    )
    chap = book / "01-chapter"
    chap.mkdir()
    (chap / "SKILL.md").write_text(
        "---\nnode_id: geography/tinybook/01-chapter\n---\n## Contents\n"
    )
    (chap / "01-leaf.md").write_text(
        "---\n"
        "node_id: geography/tinybook/01-chapter/01-leaf\n"
        "name: A Test Leaf\n"
        "source_pages: [3]\n"
        "---\n"
        "Aravalli is the oldest mountain range.\n\nGurushikhar at 1722 metres.\n"
    )

    # Inject mock LLM and skill_root override
    app.state.llm = _FakeLLM(["Aravalli ", "is the oldest [1]."])
    app.state.skill_root_override = tmp_path
    yield app
    if hasattr(app.state, "skill_root_override"):
        del app.state.skill_root_override


def test_chat_returns_ai_sdk_stream_header(app_with_skill_root):
    client = TestClient(app_with_skill_root)
    resp = client.post(
        "/tutor/chat",
        json={
            "node_id": "geography/tinybook/01-chapter/01-leaf",
            "messages": [{"role": "user", "content": "What is Aravalli?"}],
            "book_slug": "tinybook",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("x-vercel-ai-ui-message-stream") == "v1"
    assert "text/event-stream" in resp.headers.get("content-type", "")


def test_chat_streams_text_and_citations(app_with_skill_root):
    client = TestClient(app_with_skill_root)
    resp = client.post(
        "/tutor/chat",
        json={
            "node_id": "geography/tinybook/01-chapter/01-leaf",
            "messages": [{"role": "user", "content": "What is Aravalli?"}],
            "book_slug": "tinybook",
        },
    )
    body = resp.text
    # SSE frames
    events = []
    for line in body.splitlines():
        if line.startswith("data: ") and not line.endswith("[DONE]"):
            chunk = line.removeprefix("data: ").strip()
            if chunk and chunk != "[DONE]":
                events.append(json.loads(chunk))

    types = [e["type"] for e in events]
    assert types[0] == "start-step"
    assert "text-delta" in types
    assert types[-1] == "finish"


def test_chat_rejects_missing_node_id(app_with_skill_root):
    client = TestClient(app_with_skill_root)
    resp = client.post(
        "/tutor/chat",
        json={
            "messages": [{"role": "user", "content": "x"}],
            "book_slug": "tinybook",
        },
    )
    assert resp.status_code == 422  # Pydantic validation
