"""Stage 6.5 — cross-book dedup (spec docs/superpowers/specs/2026-05-05-dedup.md).

Hybrid algorithm per research note 2026-05-01-dedup.md:

  1. Embedding cosine prefilter (BGE-small-en-v1.5 by default)
     - sim < 0.80   → skip (different topics)
     - 0.80 ≤ sim < 0.92 → grey zone, escalate to LLM judge
     - sim ≥ 0.92   → auto-mark as duplicate
  2. Winner selection (deterministic):
     - source authority rank: NCERT (0) > RBSE (1) > coaching (2) > other (3)
     - longer body wins ties
     - smaller node_id (lex) wins remaining ties
  3. Loser leaf gets ``superseded_by: <winner_node_id>`` in YAML frontmatter.

Public API:
    Embedder Protocol      — duck-typed embedding model
    LeafLabel              — (book_slug, node_id, title, body, publisher)
    pick_winner            — deterministic winner-selection rule
    DedupReport, find_duplicates, apply_supersedes  — orchestration
"""

from __future__ import annotations

import logging
from typing import Literal, Protocol

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


# Authority ranks. Lower wins.
_AUTHORITY_RANK: dict[str, int] = {
    "ncert": 0,
    "rbse": 1,
    "rajasthan board of secondary education": 1,
    "springboard": 2,
    "springboard academy": 2,
    "coaching": 2,
}
_DEFAULT_RANK = 3


def _publisher_rank(publisher: str | None) -> int:
    if not publisher:
        return _DEFAULT_RANK
    return _AUTHORITY_RANK.get(publisher.strip().lower(), _DEFAULT_RANK)


class Embedder(Protocol):
    """Anything that maps a string to a fixed-length float vector."""

    def encode(self, text: str) -> list[float]: ...


class LeafLabel(BaseModel):
    """Minimal info needed to dedup one leaf."""

    book_slug: str
    node_id: str
    title: str
    body: str
    publisher: str = ""


Verdict = Literal["duplicate", "related", "different"]


class DuplicatePair(BaseModel):
    winner: LeafLabel
    loser: LeafLabel
    similarity: float = Field(ge=0.0, le=1.0)
    judge_verdict: Verdict | None = None


class DedupReport(BaseModel):
    duplicates: list[DuplicatePair] = Field(default_factory=list)
    related_count: int = 0
    different_count: int = 0


def cosine(a: list[float], b: list[float]) -> float:
    """Plain cosine similarity. No numpy dep — keep utilities light."""
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def pick_winner(a: LeafLabel, b: LeafLabel) -> tuple[LeafLabel, LeafLabel]:
    """Return ``(winner, loser)`` per spec rule.

    Tie-break: lower authority rank → longer body → smaller node_id.
    """
    rank_a = _publisher_rank(a.publisher)
    rank_b = _publisher_rank(b.publisher)
    if rank_a != rank_b:
        return (a, b) if rank_a < rank_b else (b, a)
    if len(a.body) != len(b.body):
        return (a, b) if len(a.body) > len(b.body) else (b, a)
    return (a, b) if a.node_id <= b.node_id else (b, a)


def _embed_signature(label: LeafLabel, body_chars: int = 500) -> str:
    """Build the string fed to the embedder — title + body head."""
    body = label.body[:body_chars]
    return f"{label.title}\n\n{body}".strip()


def find_duplicates(
    *,
    new_leaves: list[LeafLabel],
    existing_leaves: list[LeafLabel],
    embedder: Embedder,
    judge: "Judge | None" = None,
    auto_threshold: float = 0.92,
    grey_threshold: float = 0.80,
) -> DedupReport:
    """Compare new ingest's leaves against the existing corpus.

    Args:
        new_leaves: leaves from the book currently being ingested.
        existing_leaves: leaves already present in other books for this subject.
        embedder: anything with ``encode(text) -> list[float]``.
        judge: optional callable for the grey zone. If None, grey-zone pairs
            are NOT auto-marked duplicate (conservative: prefer false-negative
            over false-positive).

    Returns:
        DedupReport with duplicate pairs (winner/loser already chosen) and
        bucket counts.
    """
    if not new_leaves or not existing_leaves:
        return DedupReport()

    # Pre-embed everyone (same model → comparable space).
    new_vecs = {n.node_id: embedder.encode(_embed_signature(n)) for n in new_leaves}
    existing_vecs = {
        e.node_id: embedder.encode(_embed_signature(e)) for e in existing_leaves
    }

    duplicates: list[DuplicatePair] = []
    related_count = 0
    different_count = 0

    for n in new_leaves:
        nv = new_vecs[n.node_id]
        for e in existing_leaves:
            sim = cosine(nv, existing_vecs[e.node_id])
            if sim < grey_threshold:
                different_count += 1
                continue
            if sim < auto_threshold:
                if judge is None:
                    related_count += 1
                    continue
                verdict = judge(n, e)
                if verdict == "duplicate":
                    winner, loser = pick_winner(n, e)
                    duplicates.append(
                        DuplicatePair(
                            winner=winner, loser=loser,
                            similarity=sim, judge_verdict=verdict,
                        )
                    )
                elif verdict == "related":
                    related_count += 1
                else:
                    different_count += 1
            else:
                winner, loser = pick_winner(n, e)
                duplicates.append(
                    DuplicatePair(
                        winner=winner, loser=loser, similarity=sim,
                    )
                )

    return DedupReport(
        duplicates=duplicates,
        related_count=related_count,
        different_count=different_count,
    )


# Judge type alias (forward reference).
class Judge(Protocol):
    def __call__(self, new_leaf: LeafLabel, existing_leaf: LeafLabel) -> Verdict: ...
