"""Tests for the subject-canonical scope resolver.

Per spec docs/superpowers/specs/2026-05-04-subject-canonical-tree.md.
Skill folders now live at ``<skill_root>/<subject>/``; the inner book_slug
layer is gone.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from tutor.scope import build_retriever_for_scope, scope_label


def _make_subject(
    root: Path,
    subject_slug: str,
    name: str,
    leaves: list[tuple[str, str]],
) -> None:
    """Build a subject-canonical tree (one chapter, N leaves) under ``root``.

    Each leaf .md uses v3 frontmatter with a single source. Body wrapped
    with `## Source 1 (page 3)` so retriever's paragraph parser skips
    that header (it's chrome, not content).
    """
    subj = root / subject_slug
    subj.mkdir(parents=True)
    (subj / "SKILL.md").write_text(
        f"---\nnode_id: {subject_slug}\nname: {name}\nsubject: {subject_slug}\n"
        f"---\n## Contents\n- chapter\n"
    )
    chap = subj / "01-chapter"
    chap.mkdir()
    (chap / "SKILL.md").write_text(
        f"---\nnode_id: {subject_slug}/01-chapter\nsubject: {subject_slug}\n"
        f"---\n## Contents\n"
    )
    for slug, body in leaves:
        (chap / f"{slug}.md").write_text(
            f"---\n"
            f"node_id: {subject_slug}/01-chapter/{slug}\n"
            f"subject: {subject_slug}\n"
            f"sources:\n"
            f"  - source_id: 1\n"
            f"    publisher: Test Publisher\n"
            f"    pages: [3]\n"
            f"    paragraph_ids: [0]\n"
            f"    authority_rank: 2\n"
            f"---\n"
            f"## Source 1 (page 3)\n\n"
            f"{body}\n"
        )


@pytest.fixture
def two_subjects(tmp_path: Path) -> Path:
    """Two subjects with 3 leaves each. BM25Okapi needs ≥3 docs for IDF."""
    _make_subject(
        tmp_path, "rajasthan_geography", "Rajasthan Geography",
        [
            ("01-aravali", "Aravalli is the oldest fold mountain range in India."),
            ("02-thar", "Thar Desert is the largest desert in north-west India."),
            ("03-climate", "Rajasthan has arid, semi-arid, and sub-humid climates."),
        ],
    )
    _make_subject(
        tmp_path, "rajasthan_history", "Rajasthan History",
        [
            ("01-mewar", "Mewar dynasty ruled the southern part of Rajasthan."),
            ("02-marwar", "Marwar covers the western desert region of Rajasthan."),
            ("03-amber", "Amber became the capital of the Kachhwaha rulers."),
        ],
    )
    return tmp_path


def test_scope_all_indexes_every_subject(two_subjects: Path):
    r = build_retriever_for_scope(two_subjects, "all")
    aravali_hits = r.search("Aravalli oldest", k=3)
    history_hits = r.search("Mewar dynasty", k=3)
    assert len(aravali_hits) >= 1
    assert len(history_hits) >= 1
    geo_paths = [h for h in aravali_hits if "rajasthan_geography" in h.node_id]
    hist_paths = [h for h in history_hits if "rajasthan_history" in h.node_id]
    assert len(geo_paths) >= 1
    assert len(hist_paths) >= 1


def test_scope_subject_isolates_to_one_subject(two_subjects: Path):
    r = build_retriever_for_scope(
        two_subjects, "subject", subject_slug="rajasthan_geography",
    )
    geo_hits = r.search("Aravalli", k=3)
    assert len(geo_hits) >= 1
    assert all("rajasthan_geography" in h.node_id for h in geo_hits)
    cross = r.search("Mewar dynasty", k=3)
    assert all("rajasthan_history" not in h.node_id for h in cross)


def test_scope_subject_requires_slug(two_subjects: Path):
    with pytest.raises(ValueError, match="subject_slug"):
        build_retriever_for_scope(two_subjects, "subject")


def test_scope_node_uses_existing_subtree_loader(two_subjects: Path):
    r = build_retriever_for_scope(
        two_subjects, "node",
        node_id="rajasthan_geography/01-chapter/01-aravali",
    )
    assert getattr(r, "_paragraphs", []) != []


def test_scope_node_requires_node_id(two_subjects: Path):
    with pytest.raises(ValueError, match="node_id"):
        build_retriever_for_scope(two_subjects, "node")


def test_scope_label_returns_subject_name(two_subjects: Path):
    label = scope_label(two_subjects, "subject", subject_slug="rajasthan_geography")
    assert label == "Rajasthan Geography"


def test_scope_label_all_returns_friendly_text(two_subjects: Path):
    assert scope_label(two_subjects, "all") == "All subjects"


def test_scope_label_never_leaks_publisher_name(two_subjects: Path):
    """Per spec 2026-05-04: brand-stripping is non-negotiable."""
    for slug in ("rajasthan_geography", "rajasthan_history"):
        label = scope_label(two_subjects, "subject", subject_slug=slug)
        assert "Test Publisher" not in label
        assert "publisher" not in label.lower()


def test_unknown_scope_raises(two_subjects: Path):
    with pytest.raises(ValueError, match="unknown scope"):
        build_retriever_for_scope(two_subjects, "garbage")  # type: ignore[arg-type]
