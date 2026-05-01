"""Pydantic models for the mock test generator.

Schema follows spec 2026-05-03-mock-test.md and research note
2026-05-01-mcq-generation.md (MMLU-Pro-inspired with deterministic span
verification replacing expert review).
"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


Choice = Literal["A", "B", "C", "D"]
Difficulty = Literal["easy", "medium", "hard"]
BloomLevel = Literal["remember", "understand", "apply", "analyze"]


class Question(BaseModel):
    """One MCQ in a mock test.

    Invariants:
      * Exactly 4 choices keyed A/B/C/D
      * ``correct`` is one of A/B/C/D
      * ``answer_span`` is what Stage 2 (verifier) checks against the
        cited source paragraphs — must be a non-empty substring.
      * ``source_paragraph_ids`` lists the IDs the question is grounded
        in. Empty list → question is rejected by the verifier.
    """

    id: str = Field(default_factory=lambda: f"q-{uuid4().hex[:8]}")
    prompt: str = Field(min_length=8)
    choices: dict[Choice, str]
    correct: Choice
    answer_span: str = Field(min_length=3)
    source_node_id: str
    source_paragraph_ids: list[int] = Field(min_length=1)
    difficulty: Difficulty = "medium"
    bloom_level: BloomLevel = "understand"
    distractor_rationales: dict[Choice, str] = Field(default_factory=dict)
    explanation: str = ""

    @field_validator("choices")
    @classmethod
    def _choices_complete(cls, v: dict) -> dict:
        required = {"A", "B", "C", "D"}
        if set(v.keys()) != required:
            raise ValueError(f"choices must be exactly {required}, got {set(v.keys())}")
        for k, text in v.items():
            if not text or not str(text).strip():
                raise ValueError(f"choice {k} is empty")
        return v


class MockTest(BaseModel):
    """A generated test ready to be served to the student."""

    test_id: str = Field(default_factory=lambda: f"test-{uuid4().hex[:8]}")
    node_id: str
    book_slug: str | None = None
    questions: list[Question]
    generated_at: str  # ISO timestamp
    elapsed_seconds: float = Field(ge=0.0)
