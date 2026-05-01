"""Tests for the multi-book scope resolver (spec UX redesign §3 tool contract)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from tutor.scope import build_retriever_for_scope, scope_label


def _make_book(
    root: Path,
    subject: str,
    book_slug: str,
    name: str,
    leaves: list[tuple[str, str]],
) -> None:
    """Create a minimal skill folder with one chapter and N leaves."""
    book = root / subject / book_slug
    book.mkdir(parents=True)
    (book / "SKILL.md").write_text(
        f"---\nnode_id: {subject}/{book_slug}\nname: {name}\n---\n## Contents\n- chapter\n"
    )
    chap = book / "01-chapter"
    chap.mkdir()
    (chap / "SKILL.md").write_text(
        f"---\nnode_id: {subject}/{book_slug}/01-chapter\n---\n## Contents\n"
    )
    for slug, body in leaves:
        (chap / f"{slug}.md").write_text(
            f"---\n"
            f"node_id: {subject}/{book_slug}/01-chapter/{slug}\n"
            f"source_pages: [3]\n"
            f"---\n"
            f"{body}\n"
        )


@pytest.fixture
def two_books(tmp_path: Path) -> Path:
    """Each book has 3+ leaves so BM25Okapi's IDF gives non-zero scores
    on terms that appear in <100% of docs. With 2 paragraphs total, IDF
    collapses to zero and search returns no hits."""
    _make_book(
        tmp_path, "geography", "book_a", "Book A — Springboard",
        [
            ("01-aravali", "Aravalli is the oldest fold mountain range in India."),
            ("02-thar", "Thar Desert is the largest desert in north-west India."),
            ("03-climate", "Rajasthan has arid, semi-arid, and sub-humid climates."),
        ],
    )
    _make_book(
        tmp_path, "geography", "book_b", "Book B — RBSE Class 11",
        [
            ("01-rivers", "Banas is the longest river in Rajasthan."),
            ("02-lakes", "Sambhar is the largest saline lake in Rajasthan."),
            ("03-economy", "Mineral wealth drives industrial development."),
        ],
    )
    return tmp_path


def test_scope_all_indexes_every_book(two_books: Path):
    r = build_retriever_for_scope(two_books, "all")
    # Every leaf paragraph should be searchable.
    aravali_hits = r.search("Aravalli oldest", k=3)
    rivers_hits = r.search("Banas longest river", k=3)
    assert len(aravali_hits) >= 1
    assert len(rivers_hits) >= 1
    # Hits should be tagged with their actual book paths
    book_a_paths = [h for h in aravali_hits if "book_a" in h.node_id]
    book_b_paths = [h for h in rivers_hits if "book_b" in h.node_id]
    assert len(book_a_paths) >= 1
    assert len(book_b_paths) >= 1


def test_scope_book_isolates_to_one_book(two_books: Path):
    r_a = build_retriever_for_scope(two_books, "book", book_slug="book_a")
    # Aravalli is in book_a → should hit
    a_hits = r_a.search("Aravalli", k=3)
    assert len(a_hits) >= 1
    assert all("book_a" in h.node_id for h in a_hits)

    # Banas is in book_b → should NOT appear in book_a's retriever
    cross_hits = r_a.search("Banas longest river", k=3)
    assert all("book_b" not in h.node_id for h in cross_hits)


def test_scope_book_requires_slug(two_books: Path):
    with pytest.raises(ValueError, match="book_slug"):
        build_retriever_for_scope(two_books, "book")


def test_scope_node_uses_existing_subtree_loader(two_books: Path):
    """node scope points to a single leaf (1 paragraph here) — too small
    for BM25 IDF to give meaningful scores, but the scope resolver should
    still construct a retriever. We assert the construction, not the
    retrieval signal which only emerges with corpus size >= 3."""
    r = build_retriever_for_scope(
        two_books, "node",
        node_id="geography/book_a/01-chapter/01-aravali",
    )
    # Retriever was built (no exception); paragraph corpus is non-empty.
    assert getattr(r, "_paragraphs", []) != []


def test_scope_node_requires_node_id(two_books: Path):
    with pytest.raises(ValueError, match="node_id"):
        build_retriever_for_scope(two_books, "node")


def test_scope_label_returns_book_name(two_books: Path):
    label = scope_label(two_books, "book", book_slug="book_a")
    assert label == "Book A — Springboard"


def test_scope_label_all_returns_friendly_text(two_books: Path):
    assert scope_label(two_books, "all") == "All books"


def test_unknown_scope_raises(two_books: Path):
    with pytest.raises(ValueError, match="unknown scope"):
        build_retriever_for_scope(two_books, "garbage")  # type: ignore[arg-type]
