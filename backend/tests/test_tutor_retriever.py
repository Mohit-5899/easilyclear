"""Tests for the tutor's BM25 retriever (spec 2026-05-02-tutor-chat.md)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from tutor.retriever import BM25Retriever, ParagraphHit, build_retriever_for_node


# Fixture: minimal in-memory paragraph corpus.
SAMPLE_PARAGRAPHS = [
    {"node_id": "geo/intro", "paragraph_id": 0, "page": 1,
     "text": "Rajasthan is in the north-west of India."},
    {"node_id": "geo/intro", "paragraph_id": 1, "page": 1,
     "text": "Tropic of Cancer passes through Banswara."},
    {"node_id": "geo/aravali", "paragraph_id": 2, "page": 5,
     "text": "Aravalli is the oldest fold mountain range in India."},
    {"node_id": "geo/aravali", "paragraph_id": 3, "page": 5,
     "text": "Gurushikhar in Sirohi at 1722 metres is the highest peak of Aravalli."},
    {"node_id": "geo/aravali", "paragraph_id": 4, "page": 6,
     "text": "Aravalli is called the planning region of Rajasthan because state budget targets tribal areas, mining, and river-valley projects in this region."},
]


def test_retriever_returns_top_k_by_relevance():
    r = BM25Retriever(SAMPLE_PARAGRAPHS)
    hits = r.search("highest peak Aravalli", k=2)
    assert len(hits) == 2
    # Top hit should be the Gurushikhar paragraph
    assert hits[0].paragraph_id == 3
    assert hits[0].score > 0


def test_retriever_returns_paragraph_hit_shape():
    r = BM25Retriever(SAMPLE_PARAGRAPHS)
    hits = r.search("Aravalli", k=1)
    assert isinstance(hits[0], ParagraphHit)
    assert hits[0].node_id.startswith("geo/")
    assert hits[0].page > 0
    assert "Aravalli" in hits[0].snippet or "aravalli" in hits[0].snippet.lower()


def test_retriever_no_matches_returns_empty():
    r = BM25Retriever(SAMPLE_PARAGRAPHS)
    hits = r.search("quantum mechanics", k=3)
    # BM25 ranks ALL docs even with zero matches; we filter score==0
    assert all(h.score > 0 for h in hits)


def test_empty_corpus_returns_empty():
    r = BM25Retriever([])
    assert r.search("anything", k=3) == []


def test_build_retriever_for_node_filters_to_subtree(tmp_path: Path):
    """build_retriever_for_node should walk a skill folder and load only
    the descendants of the selected node."""
    # Create a minimal skill folder structure
    book = tmp_path / "geography" / "test_book"
    book.mkdir(parents=True)
    (book / "SKILL.md").write_text(
        "---\nnode_id: geography/test_book\n---\n## Contents\n- chapter\n"
    )
    chap = book / "01-chapter"
    chap.mkdir()
    (chap / "SKILL.md").write_text(
        "---\nnode_id: geography/test_book/01-chapter\n---\n## Contents\n"
    )
    (chap / "01-leaf-a.md").write_text(
        "---\n"
        "node_id: geography/test_book/01-chapter/01-leaf-a\n"
        "source_pages: [3]\n"
        "---\n"
        "Aravalli is the oldest mountain.\n\nGurushikhar at 1722 metres.\n"
    )
    (chap / "02-leaf-b.md").write_text(
        "---\n"
        "node_id: geography/test_book/01-chapter/02-leaf-b\n"
        "source_pages: [4]\n"
        "---\n"
        "Lakes are saline or freshwater.\n"
    )

    retriever = build_retriever_for_node(
        skill_root=tmp_path,
        node_id="geography/test_book/01-chapter",
    )
    hits = retriever.search("Aravalli", k=3)
    # All hits should be from leaves under the selected chapter
    assert len(hits) >= 1
    assert all(h.node_id.startswith("geography/test_book/01-chapter") for h in hits)
