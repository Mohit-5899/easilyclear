"""Extraction-time branding cleanup for V2 (spec Addendum A.5).

Two pattern tiers:

**GENERIC_PATTERNS** — reusable across any book. Strips URLs, coaching-
institute names, emails, social handles, pagination, copyright, etc.

**Source-specific pattern bundles** — per-book regex sets that target a
publisher's unique header/footer/watermark shape. Register a new bundle
when ingesting a new source whose generic cleanup leaves visible residue.

The cleaner operates on raw document text **before** paragraph splitting,
so multi-line patterns (address blocks spanning two lines, for example)
match correctly.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CleanupPattern:
    pattern: re.Pattern[str]
    label: str


@dataclass
class CleanupReport:
    cleaned_text: str
    removals_by_category: dict[str, int] = field(default_factory=dict)
    sample_matches: dict[str, list[str]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Generic patterns (apply to every ingested document)
# ---------------------------------------------------------------------------
GENERIC_PATTERNS: tuple[CleanupPattern, ...] = (
    CleanupPattern(
        re.compile(r"https?://\S+", re.IGNORECASE), "url"
    ),
    CleanupPattern(
        re.compile(r"\bwww\.[a-z0-9\-]+\.[a-z]{2,}\S*\b", re.IGNORECASE),
        "bare_domain",
    ),
    CleanupPattern(
        re.compile(
            r"\b(?:vedantu|utkarsh|byjus?|testbook|adda247|drishti|"
            r"khan\s*global|unacademy|physicswallah|pw|springboard\s*academy)"
            r"\b[^\n]*",
            re.IGNORECASE,
        ),
        "coaching_name",
    ),
    CleanupPattern(
        re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
        "email",
    ),
    CleanupPattern(
        re.compile(r"@[a-zA-Z0-9_]{4,}"), "social_handle"
    ),
    CleanupPattern(
        re.compile(r"downloaded\s+from[^\n]*", re.IGNORECASE), "downloaded_from"
    ),
    CleanupPattern(
        re.compile(r"\bpage\s+\d+\s+of\s+\d+\b", re.IGNORECASE), "pagination"
    ),
    CleanupPattern(
        re.compile(r"\u00a9\s*\d{4}[^\n]*"), "copyright"
    ),
    CleanupPattern(
        re.compile(
            r"(?:join|subscribe)[^\n]*(?:telegram|whatsapp|youtube|channel)[^\n]*",
            re.IGNORECASE,
        ),
        "social_join",
    ),
)


# ---------------------------------------------------------------------------
# Source-specific pattern bundles
# ---------------------------------------------------------------------------

# Springboard Academy — Rajasthan Geography (RAS Pre) notes.
# See the raw .txt for the header/footer that repeats on every page.
SPRINGBOARD_RAJASTHAN_PATTERNS: tuple[CleanupPattern, ...] = (
    # 2-line address + phone block (header/footer on nearly every page).
    CleanupPattern(
        re.compile(
            r"A-1\s+Keshav\s+Vihar[^\n]*\n[^\n]*30201\d[^\n]*",
            re.IGNORECASE,
        ),
        "address_block",
    ),
    # Single-line fallback if the 2-line pattern misses one line (e.g. after
    # line-wrap differences between PDF exports).
    CleanupPattern(
        re.compile(r"A-1\s+Keshav\s+Vihar[^\n]*", re.IGNORECASE), "address_line"
    ),
    CleanupPattern(
        re.compile(r"Jaipur-\s*302018[^\n]*", re.IGNORECASE), "address_line"
    ),
    # "SPRINGBOARD ACADEMY 13" style page markers — often right-aligned on
    # their own line.
    CleanupPattern(
        re.compile(
            r"^\s*SPRINGBOARD\s+ACADEMY\s+\d+\s*$",
            re.IGNORECASE | re.MULTILINE,
        ),
        "page_marker",
    ),
    # "Raj. Geo.Notes (RAS Pre)" book footer.
    CleanupPattern(
        re.compile(r"Raj\.\s*Geo\.?\s*Notes\s*\(RAS\s*Pre\)", re.IGNORECASE),
        "book_footer",
    ),
    # Standalone phone-number trios (0141-3555948, 9636977490, 8955577492).
    CleanupPattern(
        re.compile(r"\b0?\d{3,4}[-\s]?\d{7,10}\b"), "phone_number"
    ),
    CleanupPattern(
        re.compile(r"\bMob\.?:\s*\d[\d,\s\-]{8,}"), "mobile_label"
    ),
)


# Registry for CLI lookup.
BRANDING_BUNDLES: dict[str, tuple[CleanupPattern, ...]] = {
    "springboard_rajasthan": SPRINGBOARD_RAJASTHAN_PATTERNS,
}


# ---------------------------------------------------------------------------
# Cleanup entry point
# ---------------------------------------------------------------------------

_EXCESS_BLANKS = re.compile(r"(?:[ \t]*\n){3,}")


def clean_text(
    text: str,
    *,
    source_patterns: Iterable[CleanupPattern] = (),
    include_generic: bool = True,
    sample_cap: int = 5,
) -> CleanupReport:
    """Apply generic + optional source-specific branding patterns to text.

    Args:
        text: Raw text from a document.
        source_patterns: Book-specific CleanupPatterns applied after the
            generic tier. Pass one of the bundles from ``BRANDING_BUNDLES``
            or your own list.
        include_generic: Apply ``GENERIC_PATTERNS`` first. Default True.
        sample_cap: Max match samples retained per category for audit log.

    Returns:
        CleanupReport with cleaned text + per-category counts + samples.
    """
    patterns: list[CleanupPattern] = []
    if include_generic:
        patterns.extend(GENERIC_PATTERNS)
    patterns.extend(source_patterns)

    working = text
    counts: dict[str, int] = {}
    samples: dict[str, list[str]] = {}

    for cp in patterns:
        matches = cp.pattern.findall(working)
        if not matches:
            continue
        string_matches = [m if isinstance(m, str) else str(m) for m in matches]
        counts[cp.label] = counts.get(cp.label, 0) + len(string_matches)
        existing_samples = samples.setdefault(cp.label, [])
        for s in string_matches:
            if len(existing_samples) >= sample_cap:
                break
            existing_samples.append(s.strip())
        working = cp.pattern.sub("", working)

    working = _EXCESS_BLANKS.sub("\n\n", working)
    return CleanupReport(
        cleaned_text=working,
        removals_by_category=counts,
        sample_matches=samples,
    )
