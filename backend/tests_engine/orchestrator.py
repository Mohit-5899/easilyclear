"""Mock test orchestrator — runs Stages 1→3 and assembles a MockTest.

Per spec docs/superpowers/specs/2026-05-03-mock-test.md.

Flow:
    1. Build a paragraph index for the selected node's subtree
    2. Stage 1 — generate ``oversample_n`` candidate questions
    3. Stage 2 — deterministic span verification (drops ungrounded)
    4. Stage 3 — LLM judge (drops multi-correct / leakage)
    5. Trim to target ``n`` questions, return MockTest

Public API:
    build_mock_test(...) -> MockTest

Tested with a mock LLM in tests/test_mock_test_orchestrator.py.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from llm.base import LLMClient

from .generator import generate_questions
from .judge import judge_questions
from .models import MockTest, Question
from .verifier import verify_spans


logger = logging.getLogger(__name__)


def _build_paragraph_index_from_retriever_input(
    paragraphs: list[dict],
) -> dict[int, str]:
    """Flatten retriever-style paragraph list to ``{paragraph_id: text}``.

    Multiple leaves can share a paragraph_id (each leaf restarts at 0), so
    we key by ``(node_id, paragraph_id)`` — but for the verifier we need a
    single-key index. Caller supplies pre-flattened paragraphs already
    scoped to one leaf or one subtree where IDs are unique.
    """
    out: dict[int, str] = {}
    for p in paragraphs:
        pid = int(p["paragraph_id"])
        out[pid] = str(p["text"])
    return out


async def build_mock_test(
    *,
    llm: LLMClient,
    generator_model: str,
    judge_model: str,
    node_id: str,
    paragraphs: list[dict],
    book_slug: str | None = None,
    n: int = 10,
    oversample_n: int = 13,
    difficulty_mix: tuple[int, int, int] = (4, 4, 5),
) -> MockTest:
    """End-to-end mock test build.

    Args:
        llm: client used for both generator and judge calls.
        generator_model / judge_model: OpenRouter slugs (typically the same
            paid Gemma 4 26B for both — the prompts differ).
        node_id: the selected skill subtree root.
        paragraphs: list of dicts with ``paragraph_id`` (int) + ``text``
            keys, scoped to ``node_id``'s subtree.
        n: target number of questions in the final test.
        oversample_n: how many to generate at Stage 1 (extra absorbs
            verifier + judge rejects).
        difficulty_mix: ``(easy, medium, hard)`` count tuple summing to
            ``oversample_n``.

    Returns:
        MockTest with ``questions[:n]`` after all 3 stages pass.
    """
    started = time.monotonic()
    paragraph_index = _build_paragraph_index_from_retriever_input(paragraphs)

    if not paragraph_index:
        raise ValueError("no paragraphs supplied — cannot generate test")

    logger.info(
        "build_mock_test: stage 1 (generator, n=%d, mix=%s)",
        oversample_n, difficulty_mix,
    )
    candidates = await generate_questions(
        llm=llm,
        model=generator_model,
        node_id=node_id,
        paragraphs=paragraph_index,
        n=oversample_n,
        difficulty_mix=difficulty_mix,
    )
    logger.info("build_mock_test: stage 1 produced %d candidates", len(candidates))

    logger.info("build_mock_test: stage 2 (span verification)")
    grounded, span_rejected = verify_spans(candidates, paragraph_index)
    logger.info(
        "build_mock_test: stage 2 kept %d / dropped %d",
        len(grounded), len(span_rejected),
    )

    logger.info("build_mock_test: stage 3 (LLM judge)")
    accepted, judge_rejected = await judge_questions(
        llm=llm, model=judge_model, questions=grounded,
        paragraphs=paragraph_index,
    )
    logger.info(
        "build_mock_test: stage 3 accepted %d / rejected %d",
        len(accepted), len(judge_rejected),
    )

    final: list[Question] = accepted[:n]
    elapsed = time.monotonic() - started

    return MockTest(
        node_id=node_id,
        book_slug=book_slug,
        questions=final,
        generated_at=datetime.now(timezone.utc).isoformat(),
        elapsed_seconds=elapsed,
    )
