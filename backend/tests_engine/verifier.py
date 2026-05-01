"""Stage 2 — deterministic answer-span verification.

For each question, ``answer_span`` must be a substring of at least one of
the source paragraphs cited via ``source_paragraph_ids``. Whitespace and
quote marks are normalized so PDF artifacts (curly quotes, double spaces,
non-breaking spaces) don't cause false rejects.

This is the load-bearing grounding check. Stage 3 (LLM judge) catches the
softer "is this single-correct?" failures.
"""

from __future__ import annotations

import re

from .models import Question


# Curly quotes → straight; tabs/non-break spaces → space.
_QUOTE_MAP = str.maketrans(
    {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u00a0": " "}
)
_WHITESPACE = re.compile(r"\s+")


def normalize_for_match(text: str) -> str:
    """Lowercase, normalize quotes, collapse whitespace."""
    return _WHITESPACE.sub(" ", text.translate(_QUOTE_MAP).lower()).strip()


def verify_spans(
    questions: list[Question],
    paragraph_index: dict[int, str],
) -> tuple[list[Question], list[tuple[Question, str]]]:
    """Filter questions whose ``answer_span`` is grounded in cited paragraphs.

    Args:
        questions: candidate MCQs from Stage 1.
        paragraph_index: ``{paragraph_id: text}`` for the leaf/subtree.

    Returns:
        ``(passing, rejected)`` — passing is a new list (immutable input);
        rejected pairs each dropped question with a one-line reason.
    """
    passing: list[Question] = []
    rejected: list[tuple[Question, str]] = []

    for q in questions:
        span_norm = normalize_for_match(q.answer_span)
        if not span_norm:
            rejected.append((q, "empty answer_span after normalization"))
            continue
        if not q.source_paragraph_ids:
            rejected.append((q, "no source_paragraph_ids"))
            continue

        matched = False
        missing_ids: list[int] = []
        for pid in q.source_paragraph_ids:
            text = paragraph_index.get(pid)
            if text is None:
                missing_ids.append(pid)
                continue
            if span_norm in normalize_for_match(text):
                matched = True
                break

        if matched:
            passing.append(q)
        else:
            reason = "answer_span not found in any cited paragraph"
            if missing_ids:
                reason += f" (unknown paragraph_ids: {missing_ids})"
            rejected.append((q, reason))

    return passing, rejected
