"""End-to-end journey test — the API surfaces a student would hit.

Per spec docs/superpowers/specs/2026-05-02-tutor-chat.md and
2026-05-03-mock-test.md. We don't run real LLM calls; a mock client
returns canned responses so the test runs in <1s and the assertions
exercise routing, schemas, retrievers, and the in-memory test store.
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


GEN_RESPONSE = json.dumps({
    "questions": [
        {
            "prompt": "What is the highest peak of Aravalli?",
            "choices": {
                "A": "Gurushikhar", "B": "Kumbhalgarh",
                "C": "Taragarh", "D": "Saira",
            },
            "correct": "A",
            "answer_span": "Gurushikhar in Sirohi at 1722 metres",
            "source_node_id": "geography/test_book/01-chapter/01-leaf",
            "source_paragraph_ids": [1],
            "difficulty": "easy",
            "bloom_level": "remember",
            "explanation": "From the source.",
        },
    ]
})

JUDGE_ACCEPT = json.dumps({
    "verdict": "accept", "single_correct": True,
    "grounded": True, "leakage": False, "reason": "ok",
})


class _MockLLM:
    """Drives the journey test deterministically."""

    provider_name = "mock"

    def __init__(self) -> None:
        self.completion_calls = 0

    async def complete(self, messages, *, model, temperature=0.3, max_tokens=1024, **kwargs):
        self.completion_calls += 1
        # First call → MCQ generator. Subsequent → judge.
        content = GEN_RESPONSE if self.completion_calls == 1 else JUDGE_ACCEPT
        return LLMResponse(
            content=content, model=model, provider="mock",
            prompt_tokens=10, completion_tokens=20, raw=None,
        )

    async def stream(self, messages, *, model, temperature=0.3, max_tokens=1024) -> AsyncIterator[str]:
        for token in ["Gurushikhar ", "is the ", "highest peak [1]."]:
            yield token


@pytest.fixture
def app_with_corpus(tmp_path: Path):
    """Builds a tiny skill folder + injects mock LLM into FastAPI state."""
    from api.main import app

    book = tmp_path / "geography" / "test_book"
    book.mkdir(parents=True)
    (book / "SKILL.md").write_text(
        "---\nnode_id: geography/test_book\n---\n## Contents\n- chapter\n"
    )
    chap = book / "01-chapter"
    chap.mkdir()
    (chap / "SKILL.md").write_text(
        "---\nnode_id: geography/test_book/01-chapter\n---\n## Contents\n"
    )
    (chap / "01-leaf.md").write_text(
        "---\n"
        "node_id: geography/test_book/01-chapter/01-leaf\n"
        "name: A Test Leaf\n"
        "source_pages: [3]\n"
        "---\n"
        "Aravalli is the oldest fold mountain range in India.\n\n"
        "Gurushikhar in Sirohi at 1722 metres is the highest peak of Aravalli.\n"
    )

    app.state.llm = _MockLLM()
    app.state.skill_root_override = tmp_path
    yield app
    if hasattr(app.state, "skill_root_override"):
        del app.state.skill_root_override


def test_health_returns_ok(app_with_corpus):
    client = TestClient(app_with_corpus)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_full_journey_health_chat_test_grade(app_with_corpus):
    """End-to-end smoke: health → chat stream → generate test → grade."""
    client = TestClient(app_with_corpus)

    # 1. Health check
    assert client.get("/health").status_code == 200

    # 2. Tutor chat — must return SSE with text-delta events
    chat_resp = client.post(
        "/tutor/chat",
        json={
            "node_id": "geography/test_book/01-chapter/01-leaf",
            "messages": [{"role": "user", "content": "What is the highest peak of Aravalli?"}],
            "book_slug": "test_book",
        },
    )
    assert chat_resp.status_code == 200
    assert chat_resp.headers.get("x-vercel-ai-ui-message-stream") == "v1"
    chat_events = _parse_sse(chat_resp.text)
    chat_types = [e["type"] for e in chat_events]
    assert "text-delta" in chat_types
    assert chat_types[-1] == "finish"

    # 3. Generate a mock test on the same node
    test_resp = client.post(
        "/tests",
        json={
            "node_id": "geography/test_book/01-chapter/01-leaf",
            "n": 1,
            "difficulty_mix": [1, 0, 0],
        },
    )
    assert test_resp.status_code == 200
    test = test_resp.json()
    assert test["test_id"]
    assert len(test["questions"]) == 1
    q = test["questions"][0]
    assert q["correct"] == "A"
    assert "answer_span" in q

    # 4. Grade with the correct answer
    grade_resp = client.post(
        f"/tests/{test['test_id']}/grade",
        json={"answers": {q["id"]: "A"}},
    )
    assert grade_resp.status_code == 200
    grade = grade_resp.json()
    assert grade["score"] == 1
    assert grade["total"] == 1
    assert grade["details"][0]["is_correct"] is True


def test_grade_with_wrong_answer_lowers_score(app_with_corpus):
    client = TestClient(app_with_corpus)
    test_resp = client.post(
        "/tests",
        json={
            "node_id": "geography/test_book/01-chapter/01-leaf",
            "n": 1,
            "difficulty_mix": [1, 0, 0],
        },
    )
    test = test_resp.json()
    qid = test["questions"][0]["id"]

    grade = client.post(
        f"/tests/{test['test_id']}/grade",
        json={"answers": {qid: "C"}},  # wrong
    ).json()
    assert grade["score"] == 0
    assert grade["details"][0]["is_correct"] is False


def _parse_sse(body: str) -> list[dict]:
    out: list[dict] = []
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line.removeprefix("data: ").strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            out.append(json.loads(payload))
        except json.JSONDecodeError:
            pass
    return out
