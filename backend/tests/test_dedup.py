"""Tests for the cross-book dedup module (spec 2026-05-05-dedup.md)."""

from __future__ import annotations

import sys
from pathlib import Path

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from ingestion_v2.dedup import (
    LeafLabel,
    cosine,
    find_duplicates,
    pick_winner,
)


# ---------- pick_winner ----------


def _leaf(book: str, nid: str, title: str, body: str, pub: str) -> LeafLabel:
    return LeafLabel(book_slug=book, node_id=nid, title=title, body=body, publisher=pub)


def test_winner_uses_authority_rank_first():
    ncert = _leaf("ncert", "n/a", "X", "x" * 100, "NCERT")
    coaching = _leaf("springboard", "s/a", "X", "x" * 1000, "Springboard Academy")
    winner, loser = pick_winner(ncert, coaching)
    assert winner == ncert
    assert loser == coaching


def test_winner_falls_back_to_longer_body_on_authority_tie():
    a = _leaf("ncert_a", "x/a", "T", "short", "NCERT")
    b = _leaf("ncert_b", "x/b", "T", "much longer body content " * 10, "NCERT")
    winner, _ = pick_winner(a, b)
    assert winner == b


def test_winner_node_id_breaks_remaining_ties():
    a = _leaf("a", "x/aaa", "T", "same", "NCERT")
    b = _leaf("b", "x/bbb", "T", "same", "NCERT")
    winner, _ = pick_winner(a, b)
    assert winner == a  # x/aaa < x/bbb


def test_winner_unknown_publisher_loses_to_known():
    nf = _leaf("a", "x/a", "T", "x" * 100, "Random Author")
    rb = _leaf("b", "x/b", "T", "x" * 50, "RBSE")
    winner, _ = pick_winner(nf, rb)
    assert winner == rb


# ---------- cosine ----------


def test_cosine_identical_vectors():
    assert abs(cosine([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) - 1.0) < 1e-9


def test_cosine_orthogonal():
    assert abs(cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9


def test_cosine_handles_zero_vector():
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


# ---------- find_duplicates ----------


class _StaticEmbedder:
    """Maps a string to a hand-picked vector via prefix lookup."""

    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self._m = mapping

    def encode(self, text: str) -> list[float]:
        for prefix, vec in self._m.items():
            if text.startswith(prefix):
                return list(vec)
        return [0.0, 0.0, 0.0]


def test_high_similarity_pairs_become_duplicates():
    new = [_leaf("rbse", "rbse/aravali", "Aravalli", "Aravalli is...", "RBSE")]
    old = [_leaf("springboard", "sb/aravali", "Aravalli", "Aravalli is...", "Springboard")]
    embedder = _StaticEmbedder({
        "Aravalli\n\nAravalli is...": [1.0, 0.0],  # both signatures identical
    })
    report = find_duplicates(
        new_leaves=new, existing_leaves=old, embedder=embedder,
    )
    assert len(report.duplicates) == 1
    pair = report.duplicates[0]
    # RBSE wins over Springboard
    assert pair.winner.book_slug == "rbse"
    assert pair.loser.book_slug == "springboard"
    assert pair.similarity > 0.99


def test_below_grey_threshold_buckets_as_different():
    new = [_leaf("a", "a/x", "Aravalli formation", "geology", "RBSE")]
    old = [_leaf("b", "b/y", "Lakes of Rajasthan", "salt", "RBSE")]
    embedder = _StaticEmbedder({
        "Aravalli formation\n\ngeology": [1.0, 0.0],
        "Lakes of Rajasthan\n\nsalt": [0.0, 1.0],
    })
    report = find_duplicates(
        new_leaves=new, existing_leaves=old, embedder=embedder,
    )
    assert report.duplicates == []
    assert report.different_count == 1


def test_grey_zone_without_judge_is_related_not_duplicate():
    """No judge supplied → conservative: do not auto-mark grey-zone pairs."""
    new = [_leaf("a", "a/x", "T", "b1", "RBSE")]
    old = [_leaf("b", "b/y", "T", "b2", "RBSE")]
    # Build vectors with cosine ~0.85 (in grey zone)
    embedder = _StaticEmbedder({
        "T\n\nb1": [0.85, 0.527],   # roughly normalized to give grey-zone sim
        "T\n\nb2": [1.0, 0.0],
    })
    report = find_duplicates(
        new_leaves=new, existing_leaves=old, embedder=embedder,
    )
    assert report.duplicates == []
    assert report.related_count == 1


def test_grey_zone_with_judge_can_promote_to_duplicate():
    new = [_leaf("rbse", "rb/x", "T", "b1", "RBSE")]
    old = [_leaf("sb", "sb/y", "T", "b2", "Springboard")]
    embedder = _StaticEmbedder({
        "T\n\nb1": [0.85, 0.527],
        "T\n\nb2": [1.0, 0.0],
    })
    judge_calls: list[tuple[str, str]] = []

    def judge(new_leaf, existing_leaf):
        judge_calls.append((new_leaf.book_slug, existing_leaf.book_slug))
        return "duplicate"

    report = find_duplicates(
        new_leaves=new, existing_leaves=old, embedder=embedder, judge=judge,
    )
    assert len(judge_calls) == 1
    assert len(report.duplicates) == 1
    assert report.duplicates[0].winner.book_slug == "rbse"
