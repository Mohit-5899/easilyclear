"""Tests for tutor prompt assembly."""

from __future__ import annotations

import sys
from pathlib import Path

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from tutor.prompt import build_tutor_messages
from tutor.retriever import ParagraphHit


def _hit(node_id: str, pid: int, page: int, text: str, score: float = 1.0) -> ParagraphHit:
    return ParagraphHit(
        node_id=node_id, paragraph_id=pid, page=page, snippet=text, score=score
    )


def test_messages_have_system_and_user_roles():
    msgs = build_tutor_messages(
        question="What is Mawath?",
        node_title="Climate of Rajasthan",
        hits=[_hit("geo/climate", 0, 1, "Mawath is winter rain.")],
    )
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user"]


def test_user_message_contains_numbered_sources():
    hits = [
        _hit("geo/climate", 0, 1, "Mawath is winter rain from western disturbance."),
        _hit("geo/climate", 1, 2, "It is good for wheat crops."),
    ]
    msgs = build_tutor_messages(
        question="What is Mawath?",
        node_title="Climate",
        hits=hits,
    )
    user = msgs[1]["content"]
    assert "[1]" in user
    assert "[2]" in user
    assert "Mawath is winter rain" in user
    assert "western disturbance" in user
    assert "What is Mawath?" in user


def test_no_hits_still_produces_valid_messages():
    msgs = build_tutor_messages(
        question="random question",
        node_title="Climate",
        hits=[],
    )
    assert len(msgs) == 2
    # User message should still include the question
    assert "random question" in msgs[1]["content"]


def test_system_prompt_forbids_hallucination():
    msgs = build_tutor_messages(
        question="x", node_title="y", hits=[],
    )
    sys_msg = msgs[0]["content"].lower()
    assert "only" in sys_msg
    # Citation instruction present
    assert "[1]" in msgs[0]["content"] or "cite" in sys_msg
