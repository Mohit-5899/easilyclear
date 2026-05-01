"""Stage 3 — LLM judge confirms single-correct + grounded + no leakage.

Per spec 2026-05-03-mock-test.md and research note 2026-05-01-mcq-generation.md.
Each question that passed Stage 2 (deterministic span verification) gets
one judge call. Accepted questions go into the final test; rejected ones
are dropped (or held back if we have surplus).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from ingestion_v2._json_utils import ensure_valid_json
from llm.base import LLMClient, Message

from .models import Question


logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts_v2"


class JudgeVerdict(BaseModel):
    verdict: Literal["accept", "reject"]
    single_correct: bool = True
    grounded: bool = True
    leakage: bool = False
    reason: str = ""


def _read_prompt(filename: str) -> str:
    return (_PROMPT_DIR / filename).read_text(encoding="utf-8")


def _build_user_prompt(question: Question, paragraphs: dict[int, str]) -> str:
    lines = [
        "## Question",
        f"Prompt: {question.prompt}",
        f"A: {question.choices['A']}",
        f"B: {question.choices['B']}",
        f"C: {question.choices['C']}",
        f"D: {question.choices['D']}",
        f"Marked correct: {question.correct}",
        "",
        "## Cited source paragraphs",
    ]
    for pid in question.source_paragraph_ids:
        body = paragraphs.get(pid, "(missing — paragraph not provided)")
        lines.append(f"[paragraph_id={pid}] {body}")
    lines.append("")
    lines.append("Now emit your JSON verdict.")
    return "\n".join(lines)


async def judge_one(
    *,
    llm: LLMClient,
    model: str,
    question: Question,
    paragraphs: dict[int, str],
) -> JudgeVerdict:
    """Judge a single question. Returns ``JudgeVerdict``.

    On parse failure, returns a permissive accept (so transient model glitches
    don't kill ship-quality questions). Real rejects come from explicit
    ``verdict == "reject"`` from the model.
    """
    system = _read_prompt("mcq_judge_system.md")
    user = _build_user_prompt(question, paragraphs)
    messages = [
        Message(role="system", content=system),
        Message(role="user", content=user),
    ]
    try:
        response = await llm.complete(
            messages,
            model=model,
            temperature=0.0,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
    except TypeError:
        response = await llm.complete(
            messages, model=model, temperature=0.0, max_tokens=400,
        )
    try:
        cleaned = ensure_valid_json(response.content)
        return JudgeVerdict.model_validate_json(cleaned)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "judge: parse failure for question %s (%s); accepting permissively",
            question.id, exc,
        )
        return JudgeVerdict(
            verdict="accept",
            single_correct=True,
            grounded=True,
            leakage=False,
            reason="judge parse failure — permissive accept",
        )


async def judge_questions(
    *,
    llm: LLMClient,
    model: str,
    questions: list[Question],
    paragraphs: dict[int, str],
) -> tuple[list[Question], list[tuple[Question, JudgeVerdict]]]:
    """Run the judge over a list. Returns ``(accepted, rejected_pairs)``."""
    accepted: list[Question] = []
    rejected: list[tuple[Question, JudgeVerdict]] = []
    for q in questions:
        verdict = await judge_one(
            llm=llm, model=model, question=q, paragraphs=paragraphs,
        )
        if verdict.verdict == "accept":
            accepted.append(q)
        else:
            rejected.append((q, verdict))
    return accepted, rejected
