"""Tests for tests_engine.models and tests_engine.verifier."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from tests_engine.models import Question
from tests_engine.verifier import verify_spans, normalize_for_match


def _q(**overrides) -> Question:
    base = dict(
        prompt="Which is the highest peak of Aravalli?",
        choices={"A": "Gurushikhar", "B": "Kumbhalgarh", "C": "Taragarh", "D": "Saira"},
        correct="A",
        answer_span="Gurushikhar (1722 Metres",
        source_node_id="geo/aravali",
        source_paragraph_ids=[3],
        difficulty="easy",
    )
    base.update(overrides)
    return Question(**base)


def test_question_requires_four_choices():
    with pytest.raises(ValidationError, match="choices must be exactly"):
        Question(
            prompt="What?",
            choices={"A": "x", "B": "y", "C": "z"},  # missing D
            correct="A",
            answer_span="x",
            source_node_id="n",
            source_paragraph_ids=[1],
        )


def test_question_rejects_empty_choice():
    with pytest.raises(ValidationError, match="choice"):
        Question(
            prompt="What?",
            choices={"A": "x", "B": "", "C": "z", "D": "w"},
            correct="A",
            answer_span="x",
            source_node_id="n",
            source_paragraph_ids=[1],
        )


def test_question_requires_at_least_one_paragraph_ref():
    with pytest.raises(ValidationError):
        _q(source_paragraph_ids=[])


def test_normalize_handles_curly_quotes_and_whitespace():
    a = "Gurushikhar  is\tthe\u00a0highest"
    b = "Gurushikhar is the highest"
    assert normalize_for_match(a) == normalize_for_match(b)


def test_verify_spans_keeps_grounded_question():
    paragraphs = {3: "Gurushikhar (1722 Metres Sirohi) is the highest peak of Aravalli."}
    passing, rejected = verify_spans([_q()], paragraphs)
    assert len(passing) == 1
    assert rejected == []


def test_verify_spans_drops_ungrounded_question():
    paragraphs = {3: "Aravalli is an ancient mountain range."}
    bad = _q(answer_span="Atlas Mountains")
    passing, rejected = verify_spans([bad], paragraphs)
    assert passing == []
    assert len(rejected) == 1
    assert "not found" in rejected[0][1]


def test_verify_spans_handles_missing_paragraph_id():
    paragraphs = {99: "irrelevant content"}
    bad = _q()  # references paragraph 3, not in index
    passing, rejected = verify_spans([bad], paragraphs)
    assert passing == []
    assert "unknown paragraph_ids" in rejected[0][1]


def test_verify_spans_normalizes_quote_styles():
    """Curly quotes in source vs straight in answer_span shouldn't fail."""
    paragraphs = {3: "It is called the \u201cgolden drop\u201d of winter rain."}
    q = _q(
        answer_span='"golden drop"',
        source_paragraph_ids=[3],
    )
    passing, rejected = verify_spans([q], paragraphs)
    assert len(passing) == 1
