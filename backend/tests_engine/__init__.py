"""Mock test generator (spec docs/superpowers/specs/2026-05-03-mock-test.md).

Generates verifiable MCQs from a hierarchical skill subtree. 3-stage
pipeline (per research docs/research/2026-05-01-mcq-generation.md):

  1. Schema-constrained generation via Gemma 4 26B with response_format
     json_object
  2. Deterministic span verification — answer_span must be a substring of
     one of the cited paragraphs
  3. LLM-judge single-correct check + closed-book leakage probe

Public API:
    Question, MockTest                 — Pydantic models
    generate_questions                 — Stage 1
    verify_spans                       — Stage 2 (deterministic)
    judge_questions                    — Stage 3 (LLM)
    build_mock_test                    — orchestrator (all 3 stages)
"""

from .models import Choice, Difficulty, BloomLevel, Question, MockTest
from .verifier import verify_spans, normalize_for_match

__all__ = [
    "Choice",
    "Difficulty",
    "BloomLevel",
    "Question",
    "MockTest",
    "verify_spans",
    "normalize_for_match",
]
