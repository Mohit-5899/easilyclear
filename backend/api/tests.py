"""Mock test API endpoints — POST /tests, POST /tests/{id}/grade.

Per spec docs/superpowers/specs/2026-05-03-mock-test.md.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from config import get_settings
from llm.base import LLMClient
from tests_engine.models import Choice, MockTest
from tests_engine.orchestrator import build_mock_test
from tutor.retriever import build_retriever_for_node


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/tests", tags=["tests"])

_DEFAULT_SKILL_ROOT = (
    Path(__file__).resolve().parent.parent.parent / "database" / "skills"
)


# In-memory test store. Per spec — fine for hackathon, not production.
_TEST_STORE: dict[str, MockTest] = {}


class CreateTestRequest(BaseModel):
    node_id: str = Field(min_length=1)
    book_slug: str | None = None
    n: int = Field(default=10, ge=1, le=20)
    difficulty_mix: tuple[int, int, int] = (4, 3, 3)


class GradeRequest(BaseModel):
    answers: dict[str, Choice]


class GradeDetail(BaseModel):
    question_id: str
    user: Choice | None
    correct: Choice
    is_correct: bool
    explanation: str


class GradeResponse(BaseModel):
    score: int
    total: int
    details: list[GradeDetail]


def _get_skill_root(app_state) -> Path:
    override = getattr(app_state, "skill_root_override", None)
    if override is not None:
        return Path(override)
    return _DEFAULT_SKILL_ROOT


def _collect_paragraphs_for_node(skill_root: Path, node_id: str) -> list[dict]:
    """Reuse the BM25 retriever's loader to enumerate paragraphs.

    The retriever exposes ``_paragraphs`` (private but stable) — we call
    ``build_retriever_for_node`` and read its corpus directly. Avoids
    re-implementing the walker.
    """
    retriever = build_retriever_for_node(skill_root, node_id)
    return list(getattr(retriever, "_paragraphs", []))


@router.post("", response_model=MockTest)
async def create_test(req: CreateTestRequest, request: Request) -> MockTest:
    settings = get_settings()
    llm: LLMClient = request.app.state.llm
    skill_root = _get_skill_root(request.app.state)

    try:
        paragraphs = _collect_paragraphs_for_node(skill_root, req.node_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if not paragraphs:
        raise HTTPException(
            status_code=400,
            detail="not enough source content under this node to generate a test",
        )

    sum_mix = sum(req.difficulty_mix)
    oversample = max(req.n + 3, sum_mix)

    test = await build_mock_test(
        llm=llm,
        generator_model=settings.model_ingestion,
        judge_model=settings.model_ingestion,
        node_id=req.node_id,
        paragraphs=paragraphs,
        book_slug=req.book_slug,
        n=req.n,
        oversample_n=oversample,
        difficulty_mix=req.difficulty_mix,
    )
    _TEST_STORE[test.test_id] = test
    return test


@router.get("/{test_id}", response_model=MockTest)
async def get_test(test_id: str) -> MockTest:
    test = _TEST_STORE.get(test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="test not found")
    return test


@router.post("/{test_id}/grade", response_model=GradeResponse)
async def grade_test(test_id: str, req: GradeRequest) -> GradeResponse:
    test = _TEST_STORE.get(test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="test not found")

    details: list[GradeDetail] = []
    score = 0
    for q in test.questions:
        user_answer = req.answers.get(q.id)
        is_correct = user_answer == q.correct
        if is_correct:
            score += 1
        details.append(
            GradeDetail(
                question_id=q.id,
                user=user_answer,
                correct=q.correct,
                is_correct=is_correct,
                explanation=q.explanation,
            )
        )
    return GradeResponse(score=score, total=len(test.questions), details=details)
