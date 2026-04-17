"""Tests for ingestion.text_cleaner (layers 2 + 3 of the cleaning pipeline).

Layer 2 (regex) tests are synchronous. Layer 3 (LLM) tests use the existing
``MockLLMClient`` from ``llm/mock.py`` so the suite runs offline.
"""

from __future__ import annotations

import pytest

from ingestion.text_cleaner import (
    PROMOTIONAL_PATTERNS,
    CleanResult,
    _SYSTEM_PROMPT,
    llm_clean,
    regex_clean,
)
from llm.mock import MockLLMClient


CLEAN_SAMPLES: tuple[str, ...] = (
    "The Aravalli range is one of the oldest mountain systems in the world.",
    "India's monsoon season typically lasts from June to September.",
    "Chapter 3 discusses the drainage systems of peninsular India.",
    "Resources can be classified into renewable and non-renewable categories.",
    "The Thar Desert covers large parts of western Rajasthan.",
    "Sustainable development balances economic growth with environmental protection.",
    "Major rivers originating in the Himalayas include the Ganga and the Brahmaputra.",
    "The Deccan Plateau has rich reserves of iron ore and bauxite.",
    "Agriculture remains the primary occupation of rural Indian households.",
    "Forests play a crucial role in maintaining biodiversity.",
)

DIRTY_SAMPLES: tuple[str, ...] = (
    "Visit https://vedantu.com for more NCERT solutions!",
    "Download from www.byjus.com - best NCERT class 10 content",
    "Utkarsh Classes: Best coaching for Rajasthan government exams",
    "Join our Telegram channel @rajasthan_exams for daily updates",
    "\u00a9 2024 Testbook.com - all rights reserved",
    "Page 23 of 187",
    "Subscribe to Drishti IAS YouTube channel for RAS preparation",
    "Downloaded from scribd.com/doc/12345",
    "Adda247 offers live classes for Patwari aspirants",
    "Contact us at info@khanglobalstudies.com for admissions",
)


# ---------------------------------------------------------------------------
# Regex layer tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sample", CLEAN_SAMPLES)
def test_clean_text_unchanged(sample: str) -> None:
    """Educational prose passes through the regex cleaner untouched."""
    result = regex_clean(sample)

    assert isinstance(result, CleanResult)
    assert result.was_suspicious is False
    assert result.cleaned_text == sample
    assert result.stripped_fragments == []
    assert result.category_counts == {}


@pytest.mark.parametrize("sample", DIRTY_SAMPLES)
def test_clean_text_dirty(sample: str) -> None:
    """Contaminated lines are flagged suspicious and strip at least one fragment."""
    result = regex_clean(sample)

    assert result.was_suspicious is True
    assert len(result.stripped_fragments) >= 1
    assert len(result.category_counts) >= 1
    # Every count must be a positive int.
    assert all(v >= 1 for v in result.category_counts.values())


def test_mixed_content() -> None:
    """A promo line wedged between educational lines is removed; the rest survives."""
    text = (
        "The Aravalli range is one of the oldest mountain systems in the world.\n"
        "Visit https://vedantu.com for more NCERT solutions!\n"
        "India's monsoon season typically lasts from June to September."
    )

    result = regex_clean(text)

    assert result.was_suspicious is True
    assert "Aravalli range" in result.cleaned_text
    assert "monsoon season" in result.cleaned_text
    assert "vedantu" not in result.cleaned_text.lower()
    assert "https://" not in result.cleaned_text


def test_collapses_blank_lines() -> None:
    """Runs of 3+ blank lines collapse to exactly 2 blank lines."""
    text = "Paragraph one.\n\n\n\n\n\nParagraph two."

    result = regex_clean(text)

    # Exactly one "\n\n\n" (two blank lines worth of separator) should remain,
    # i.e. two consecutive newlines collapsing to a single paragraph break.
    assert "\n\n\n\n" not in result.cleaned_text
    assert result.cleaned_text == "Paragraph one.\n\nParagraph two."


def test_promotional_patterns_metadata() -> None:
    """PROMOTIONAL_PATTERNS is a non-empty tuple of (pattern, label) pairs."""
    assert isinstance(PROMOTIONAL_PATTERNS, tuple)
    assert len(PROMOTIONAL_PATTERNS) >= 8
    for entry in PROMOTIONAL_PATTERNS:
        assert len(entry) == 2
        assert isinstance(entry[1], str) and entry[1]


# ---------------------------------------------------------------------------
# LLM layer tests
# ---------------------------------------------------------------------------


def test_llm_clean_loads_system_prompt() -> None:
    """The module-level _SYSTEM_PROMPT is populated at import time."""
    assert isinstance(_SYSTEM_PROMPT, str)
    assert len(_SYSTEM_PROMPT) > 0
    assert "textbook" in _SYSTEM_PROMPT.lower()


@pytest.mark.asyncio
async def test_llm_clean_uses_mock_client() -> None:
    """llm_clean routes through the injected LLMClient abstraction."""
    client = MockLLMClient()
    dirty = "Visit https://vedantu.com for NCERT solutions"

    out = await llm_clean(dirty, client=client, model="gemma-4-e4b-it")

    assert isinstance(out, str)
    assert len(out) > 0
