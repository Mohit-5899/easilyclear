"""Layer 2 + 3 of the 4-layer content cleaning pipeline.

See ARCHITECTURE.md §10 and CLAUDE.md §3.1 for the rationale. This module
strips promotional contamination (coaching institute names, URLs, watermarks,
copyright footers, injected pagination) from text that was extracted from a
PDF, BEFORE it reaches the PageIndex tree builder. Layer 2 is a cheap regex
pre-filter; layer 3 is a targeted LLM pass invoked via the :class:`LLMClient`
abstraction in ``llm/base.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from llm.base import LLMClient, Message

# ---------------------------------------------------------------------------
# Promotional regex patterns (layer 2)
# ---------------------------------------------------------------------------
# Each entry: (compiled_pattern, category_label). All patterns are case
# insensitive. Order matters only for reporting — the whole list is applied
# sequentially and matches are removed via ``re.sub``.
PROMOTIONAL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # 1. Explicit URLs
    (re.compile(r"https?://\S+", re.IGNORECASE), "url"),
    # 2. Bare domains starting with www.
    (re.compile(r"\bwww\.[a-z0-9\-]+\.[a-z]{2,}\S*\b", re.IGNORECASE), "bare_domain"),
    # 3. Coaching institute names + the rest of their line (captures the
    #    typical "Visit Vedantu for best NCERT solutions" promo tail).
    (
        re.compile(
            r"\b(?:vedantu|utkarsh|byjus?|testbook|adda247|drishti|"
            r"khan\s*global|unacademy|physicswallah|pw)\b[^\n]*",
            re.IGNORECASE,
        ),
        "coaching_name",
    ),
    # 4. Social handles / email local parts prefixed with @
    (re.compile(r"@[a-zA-Z0-9_]{4,}", re.IGNORECASE), "social_handle"),
    # 5. "Downloaded from ..." watermark lines
    (re.compile(r"downloaded\s+from[^\n]*", re.IGNORECASE), "downloaded_from"),
    # 6. Injected pagination — "Page 23 of 187"
    (re.compile(r"\bpage\s+\d+\s+of\s+\d+\b", re.IGNORECASE), "pagination"),
    # 7. Copyright footer lines
    (re.compile(r"\u00a9\s*\d{4}[^\n]*", re.IGNORECASE), "copyright"),
    # 8. Telegram / WhatsApp / YouTube join-channel solicitations
    (
        re.compile(
            r"(?:join|subscribe)[^\n]*(?:telegram|whatsapp|youtube|channel)[^\n]*",
            re.IGNORECASE,
        ),
        "social_join",
    ),
    # 9. Bare email addresses (catches contacts like info@khanglobalstudies.com
    #    that survive the social-handle pattern when the local part is short).
    (
        re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
        "email",
    ),
)

# Collapses runs of 3+ blank lines down to 2 so excisions do not leave gaps.
_BLANK_LINE_RUN = re.compile(r"(?:[ \t]*\n){3,}")


class CleanResult(BaseModel):
    """Outcome of a regex cleaning pass over a chunk of extracted text."""

    cleaned_text: str
    was_suspicious: bool
    stripped_fragments: list[str] = Field(default_factory=list)
    category_counts: dict[str, int] = Field(default_factory=dict)


def regex_clean(text: str) -> CleanResult:
    """Apply layer 2 (regex) cleaning to a block of extracted text.

    Returns a :class:`CleanResult` recording the cleaned output, a suspicion
    flag, every removed substring (for audit/debug), and per-category counts.
    """
    stripped_fragments: list[str] = []
    category_counts: dict[str, int] = {}
    working = text

    for pattern, label in PROMOTIONAL_PATTERNS:
        matches = pattern.findall(working)
        if not matches:
            continue
        for m in matches:
            stripped_fragments.append(m if isinstance(m, str) else str(m))
        category_counts[label] = category_counts.get(label, 0) + len(matches)
        working = pattern.sub("", working)

    # Collapse 3+ consecutive blank lines down to exactly 2.
    working = _BLANK_LINE_RUN.sub("\n\n", working)

    return CleanResult(
        cleaned_text=working,
        was_suspicious=bool(stripped_fragments),
        stripped_fragments=stripped_fragments,
        category_counts=category_counts,
    )


# ---------------------------------------------------------------------------
# LLM cleaning pass (layer 3)
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT_PATH = (
    Path(__file__).parent.parent / "prompts" / "text_cleaner_system.md"
)
_SYSTEM_PROMPT: str = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()


async def llm_clean(text: str, client: LLMClient, model: str) -> str:
    """Apply layer 3 (LLM) cleaning to text flagged by the regex pass.

    The caller passes an injected :class:`LLMClient` (never a concrete
    provider — see CLAUDE.md §1.7 and llm/factory.py). Temperature is pinned
    to 0.0 so the model makes deterministic, mechanical edits.
    """
    max_tokens = min(len(text) // 2 + 500, 4096)
    response = await client.complete(
        messages=[
            Message(role="system", content=_SYSTEM_PROMPT),
            Message(role="user", content=text),
        ],
        model=model,
        temperature=0.0,
        max_tokens=max_tokens,
    )
    return response.content.strip()
