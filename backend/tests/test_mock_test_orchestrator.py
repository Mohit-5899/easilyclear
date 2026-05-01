"""End-to-end tests for the mock test orchestrator with a mock LLM."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from llm.base import LLMResponse
from tests_engine.orchestrator import build_mock_test


# Fixtures: minimal paragraph corpus and canned LLM responses.
PARAS = [
    {"paragraph_id": 1, "text": "Aravalli is the oldest fold mountain range in India."},
    {"paragraph_id": 2, "text": "Gurushikhar in Sirohi at 1722 metres is the highest peak of Aravalli."},
    {"paragraph_id": 3, "text": "Aravalli is called the planning region because state budget targets tribal areas, mining, and river-valley projects."},
]


GOOD_GEN_RESPONSE = json.dumps({
    "questions": [
        {
            "prompt": "What is the highest peak of Aravalli?",
            "choices": {"A": "Gurushikhar", "B": "Kumbhalgarh", "C": "Taragarh", "D": "Saira"},
            "correct": "A",
            "answer_span": "Gurushikhar in Sirohi at 1722 metres is the highest peak of Aravalli",
            "source_node_id": "geo/aravali",
            "source_paragraph_ids": [2],
            "difficulty": "easy",
            "bloom_level": "remember",
            "explanation": "From the source.",
        },
        {
            "prompt": "Why is Aravalli called the planning region?",
            "choices": {
                "A": "It is the oldest mountain",
                "B": "Budget targets tribal areas, mining, and river-valley projects",
                "C": "It runs north-east to south-west",
                "D": "It contains Mount Abu",
            },
            "correct": "B",
            "answer_span": "state budget targets tribal areas, mining, and river-valley projects",
            "source_node_id": "geo/aravali",
            "source_paragraph_ids": [3],
            "difficulty": "medium",
            "bloom_level": "understand",
            "explanation": "Source explicitly says so.",
        },
        # An ungrounded one that should be dropped at Stage 2.
        {
            "prompt": "What is the area of Rajasthan in km²?",
            "choices": {"A": "342239", "B": "200000", "C": "500000", "D": "100000"},
            "correct": "A",
            "answer_span": "342,239 sq km",  # NOT in any paragraph
            "source_node_id": "geo/aravali",
            "source_paragraph_ids": [1, 2, 3],
            "difficulty": "easy",
            "bloom_level": "remember",
            "explanation": "x",
        },
    ]
})


JUDGE_ACCEPT = json.dumps({
    "verdict": "accept", "single_correct": True, "grounded": True, "leakage": False,
    "reason": "ok",
})


class _MockLLM:
    provider_name = "mock"

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, messages, *, model, temperature=0.3, max_tokens=1024, **kwargs):
        # First call (generator) returns GOOD_GEN_RESPONSE.
        # Subsequent calls (judge per question) return JUDGE_ACCEPT.
        self.calls += 1
        if self.calls == 1:
            content = GOOD_GEN_RESPONSE
        else:
            content = JUDGE_ACCEPT
        return LLMResponse(
            content=content, model=model, provider="mock",
            prompt_tokens=10, completion_tokens=20, raw=None,
        )

    async def stream(self, *args, **kwargs):
        raise NotImplementedError


def test_orchestrator_drops_ungrounded_and_keeps_good():
    llm = _MockLLM()
    test = asyncio.run(build_mock_test(
        llm=llm,
        generator_model="m",
        judge_model="m",
        node_id="geo/aravali",
        paragraphs=PARAS,
        n=10,
        oversample_n=3,
        difficulty_mix=(1, 1, 1),
    ))

    # 2 of 3 candidates are grounded; both should be accepted by the
    # mock judge.
    assert len(test.questions) == 2
    titles = [q.prompt for q in test.questions]
    assert any("highest peak" in t for t in titles)
    assert any("planning region" in t for t in titles)
    # The ungrounded "area of Rajasthan" question should NOT survive.
    assert not any("area of Rajasthan" in t for t in titles)


def test_orchestrator_includes_metadata():
    llm = _MockLLM()
    test = asyncio.run(build_mock_test(
        llm=llm,
        generator_model="m",
        judge_model="m",
        node_id="geo/aravali",
        paragraphs=PARAS,
        book_slug="my_book",
        n=10,
        oversample_n=3,
    ))
    assert test.node_id == "geo/aravali"
    assert test.book_slug == "my_book"
    assert test.generated_at  # ISO timestamp set
    assert test.elapsed_seconds >= 0


def test_orchestrator_raises_on_empty_paragraphs():
    llm = _MockLLM()
    with pytest.raises(ValueError, match="no paragraphs"):
        asyncio.run(build_mock_test(
            llm=llm,
            generator_model="m",
            judge_model="m",
            node_id="geo/aravali",
            paragraphs=[],
            n=10,
        ))
