"""Stage 1 — schema-constrained MCQ generation via Gemma 4 26B.

Per spec 2026-05-03-mock-test.md and research note 2026-05-01-mcq-generation.md.
Asks the LLM for a list of Question objects with response_format json_object;
parses + validates against our Pydantic schema. The shared
``ingestion_v2._json_utils.ensure_valid_json`` strips fences/prose around the
JSON payload.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from ingestion_v2._json_utils import ensure_valid_json
from llm.base import LLMClient, Message

from .models import Question


logger = logging.getLogger(__name__)


_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts_v2"


class _GeneratorOutput(BaseModel):
    questions: list[Question] = Field(default_factory=list)


def _read_prompt(filename: str) -> str:
    return (_PROMPT_DIR / filename).read_text(encoding="utf-8")


def _format_paragraphs_block(paragraphs: dict[int, str], char_cap: int = 800) -> str:
    """Render paragraphs as a numbered block. Truncates very long ones."""
    lines: list[str] = []
    for pid, text in paragraphs.items():
        body = text if len(text) <= char_cap else text[:char_cap].rstrip() + " […]"
        lines.append(f"[paragraph_id={pid}] {body}")
    return "\n\n".join(lines)


def _build_user_prompt(
    paragraphs: dict[int, str],
    node_id: str,
    n: int,
    difficulty_mix: tuple[int, int, int],
) -> str:
    easy, med, hard = difficulty_mix
    return (
        f"Generate {n} MCQs from the source paragraphs below.\n\n"
        f"Difficulty mix: {easy} easy, {med} medium, {hard} hard.\n\n"
        f"All questions must use ``source_node_id`` = \"{node_id}\".\n\n"
        f"# Source paragraphs\n\n{_format_paragraphs_block(paragraphs)}\n\n"
        f"Emit ONLY a JSON object: {{\"questions\": [...]}}"
    )


async def generate_questions(
    *,
    llm: LLMClient,
    model: str,
    node_id: str,
    paragraphs: dict[int, str],
    n: int = 13,
    difficulty_mix: tuple[int, int, int] = (4, 4, 5),
    max_tokens: int = 4096,
) -> list[Question]:
    """Run Stage 1 — return raw candidate questions (pre-verification).

    Generates ``n`` candidates so the downstream verifier+judge can drop
    rejects and we still have ~10 to ship. Caller filters.
    """
    system = _read_prompt("mcq_generator_system.md")
    user = _build_user_prompt(paragraphs, node_id, n, difficulty_mix)

    messages = [
        Message(role="system", content=system),
        Message(role="user", content=user),
    ]

    try:
        response = await llm.complete(
            messages,
            model=model,
            temperature=0.4,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
    except TypeError:
        response = await llm.complete(
            messages, model=model, temperature=0.4, max_tokens=max_tokens,
        )

    cleaned = ensure_valid_json(response.content)
    try:
        out = _GeneratorOutput.model_validate_json(cleaned)
    except ValidationError as exc:
        logger.warning("generator: schema validation failed (%s)", exc)
        # Drop to lenient parse — keep questions that DO validate.
        try:
            raw = json.loads(cleaned)
            kept: list[Question] = []
            for q in raw.get("questions", []):
                try:
                    kept.append(Question.model_validate(q))
                except ValidationError:
                    continue
            return kept
        except json.JSONDecodeError:
            raise exc
    return out.questions
