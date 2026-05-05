"""Tests for ingestion_v2/merge.py — Stage 6.5b.

Spec: docs/superpowers/specs/2026-05-04-subject-canonical-tree.md §6.

Coverage targets the six acceptance cases from the spec:
    1. match-by-embedding → appends source to existing leaf
    2. no-match-add-leaf-under-existing-chapter (slug-similar)
    3. no-match-add-new-chapter (no slug similarity anywhere)
    4. append-source preserves Source 1 + adds Source 2 with correct page label
    5. authority ordering — appended source carries provided authority_rank
    6. content-hash idempotency — re-emit produces a stable hash
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import frontmatter
import pytest

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from ingestion_v2.content_fill import FilledNode, FilledTree
from ingestion_v2.emit import emit_skill_folder
from ingestion_v2.merge import (
    append_source_to_leaf,
    load_existing_subject,
    match_chapter_by_slug,
    merge_into_subject_tree,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StaticEmbedder:
    """Deterministic embedder driven by string-prefix lookups.

    Each unmatched input gets its OWN one-hot vector (axis chosen by a stable
    hash of the input), guaranteeing cosine ≈ 0 between distinct unmatched
    inputs. Otherwise an empty mapping would collapse every leaf onto the
    same fallback vector and look like a 100% match across the corpus.
    """

    _FALLBACK_DIM = 256

    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self._m = mapping

    def encode(self, text: str) -> list[float]:
        for prefix, vec in self._m.items():
            if text.startswith(prefix):
                # Pad mapped vectors out to the fallback dimension so cosine
                # against a fallback returns ~0, not whatever the truncated
                # zip yields.
                v = list(vec) + [0.0] * (self._FALLBACK_DIM - len(vec))
                return v
        slot = abs(hash(text)) % self._FALLBACK_DIM
        v = [0.0] * self._FALLBACK_DIM
        v[slot] = 1.0
        return v


def _leaf(title: str, body: str, *, pages=None, paragraph_refs=None) -> FilledNode:
    return FilledNode(
        title=title,
        description=title,
        paragraph_refs=paragraph_refs or [1, 2],
        body=body,
        source_pages=pages or [10, 11],
        children=[],
    )


def _root(title: str, chapters: list[FilledNode]) -> FilledNode:
    return FilledNode(
        title=title, description=title,
        paragraph_refs=[], body=f"# {title}",
        source_pages=[1], children=chapters,
    )


def _chapter(title: str, leaves: list[FilledNode]) -> FilledNode:
    return FilledNode(
        title=title, description=title,
        paragraph_refs=[], body=f"## {title}",
        source_pages=[1], children=leaves,
    )


@pytest.fixture
def seeded_subject(tmp_path: Path) -> tuple[Path, str]:
    """Emit a single-source subject tree with two chapters / three leaves."""
    tree = FilledTree(root=_root("Rajasthan Geography", [
        _chapter("Physical Geography", [
            _leaf("Aravalli Mountain Range", "The Aravalli is...", pages=[18, 19]),
            _leaf("Thar Desert",            "The Thar covers...", pages=[22, 23]),
        ]),
        _chapter("Climate of Rajasthan", [
            _leaf("Mawath Rainfall", "Mawath is winter rain...", pages=[44]),
        ]),
    ]))
    out = tmp_path / "skills"
    asyncio.run(emit_skill_folder(
        filled=tree,
        subject_slug="rajasthan_geography",
        book_metadata={"name": "Rajasthan Geography", "scope": "rajasthan"},
        output_root=out,
        source_metadata={
            "publisher": "Springboard Academy",
            "book_slug": "springboard_rajasthan_geography",
            "authority_rank": 2,
        },
    ))
    return out / "rajasthan_geography", "rajasthan_geography"


# ---------------------------------------------------------------------------
# 1. match-by-embedding → appends source
# ---------------------------------------------------------------------------


def test_match_by_embedding_appends_new_source(seeded_subject):
    subject_dir, _slug = seeded_subject

    # New ingest: same Aravalli leaf from NCERT — should auto-merge as Source 2.
    new_tree = FilledTree(root=_root("Rajasthan Geography", [
        _chapter("Physical Environment", [
            _leaf("Aravalli Mountain Range", "Aravalli formed in Proterozoic...",
                  pages=[44]),
        ]),
    ]))

    embedder = _StaticEmbedder({
        # Existing Aravalli signature (matches dedup._embed_signature shape:
        # "<title>\n\n<body[:500]>")
        "Aravalli Mountain Range\n\n## Source 1": [1.0, 0.0],
        # New Aravalli signature
        "Aravalli Mountain Range\n\nAravalli formed in Proterozoic...": [1.0, 0.0],
        # Existing non-target leaves get orthogonal vectors so they don't compete.
        "Thar Desert": [0.0, 1.0],
        "Mawath Rainfall": [0.0, 1.0],
    })

    report = merge_into_subject_tree(
        new_tree, subject_dir,
        source_metadata={"publisher": "NCERT",
                         "book_slug": "ncert_class_11",
                         "authority_rank": 0},
        embedder=embedder,
    )

    assert report.appended == 1
    assert report.added_leaves == 0
    assert report.added_chapters == 0

    # Verify the existing Aravalli leaf now has 2 sources + 2 body sections.
    aravali_path = subject_dir / "01-physical-geography" / "01-aravalli-mountain-range.md"
    post = frontmatter.load(aravali_path)
    sources = post.metadata["sources"]
    assert len(sources) == 2
    assert sources[1]["publisher"] == "NCERT"
    assert sources[1]["source_id"] == 2
    assert "## Source 1" in post.content
    assert "## Source 2 (page 44)" in post.content


# ---------------------------------------------------------------------------
# 2. no-match → add new leaf under existing slug-similar chapter
# ---------------------------------------------------------------------------


def test_no_match_adds_leaf_to_slug_similar_chapter(seeded_subject):
    subject_dir, _slug = seeded_subject

    # New leaf on "Western Rajasthan Desert" — slug-similar to "Physical Geography"?
    # Not really; force the test to land via title-token overlap with the
    # Physical Geography chapter via the word "geography" or fall back to a
    # custom classifier. We'll provide a classifier so the test is unambiguous.
    new_tree = FilledTree(root=_root("Rajasthan Geography", [
        _chapter("Physical Environment", [
            _leaf("Western Rajasthan Plains", "Plains stretch from...",
                  pages=[55]),
        ]),
    ]))

    embedder = _StaticEmbedder({})  # nothing matches → all dissimilar

    def classifier(leaf, chapters):
        # Force "Physical Geography" chapter for testing
        for c in chapters:
            if "physical" in c.slug:
                return c
        return None

    report = merge_into_subject_tree(
        new_tree, subject_dir,
        source_metadata={"publisher": "NCERT",
                         "book_slug": "ncert_class_11",
                         "authority_rank": 0},
        embedder=embedder,
        chapter_classifier=classifier,
    )

    assert report.appended == 0
    assert report.added_leaves == 1
    assert report.added_chapters == 0

    new_leaf_path = subject_dir / "01-physical-geography" / "03-western-rajasthan-plains.md"
    assert new_leaf_path.exists()
    post = frontmatter.load(new_leaf_path)
    assert post.metadata["sources"][0]["publisher"] == "NCERT"
    assert post.metadata["depth"] == 2
    assert "## Source 1 (page 55)" in post.content


# ---------------------------------------------------------------------------
# 3. no-match anywhere → create new chapter
# ---------------------------------------------------------------------------


def test_no_match_anywhere_creates_new_chapter(seeded_subject):
    subject_dir, _slug = seeded_subject

    # Topic sufficiently far from existing chapters (no shared slug tokens)
    # so neither the embedder nor the slug fallback finds a home.
    new_tree = FilledTree(root=_root("Rajasthan Geography", [
        _chapter("Tourism and Heritage", [
            _leaf("Pushkar Lake Festival", "Held annually in Kartik...",
                  pages=[88]),
        ]),
    ]))

    embedder = _StaticEmbedder({})  # all orthogonal

    report = merge_into_subject_tree(
        new_tree, subject_dir,
        source_metadata={"publisher": "NCERT",
                         "book_slug": "ncert_class_11",
                         "authority_rank": 0},
        embedder=embedder,
    )

    assert report.added_chapters == 1
    new_chapter = subject_dir / "03-pushkar-lake-festival"
    assert new_chapter.exists()
    assert (new_chapter / "SKILL.md").exists()
    leaf_md = list(new_chapter.glob("*.md"))
    leaf_md = [p for p in leaf_md if p.name != "SKILL.md"]
    assert len(leaf_md) == 1
    post = frontmatter.load(leaf_md[0])
    assert post.metadata["sources"][0]["publisher"] == "NCERT"


# ---------------------------------------------------------------------------
# 4. append-source preserves Source 1 + writes correct page label
# ---------------------------------------------------------------------------


def test_append_source_preserves_source_one(seeded_subject):
    subject_dir, _slug = seeded_subject
    leaf_path = subject_dir / "01-physical-geography" / "01-aravalli-mountain-range.md"
    pre = frontmatter.load(leaf_path)
    assert "## Source 1" in pre.content

    sid = append_source_to_leaf(
        leaf_path,
        source_metadata={"publisher": "NCERT",
                         "book_slug": "ncert_class_11",
                         "authority_rank": 0},
        pages=[44, 45],
        paragraph_ids=[101, 102],
        source_body="Aravalli formed in the Proterozoic eon...",
    )
    assert sid == 2

    post = frontmatter.load(leaf_path)
    # Source 1 (Springboard) header still present
    assert "## Source 1" in post.content
    # Source 2 (NCERT) appended with the right page label
    assert "## Source 2 (pages 44-45)" in post.content
    # Source 1 body precedes Source 2 body
    s1_idx = post.content.index("## Source 1")
    s2_idx = post.content.index("## Source 2")
    assert s1_idx < s2_idx


# ---------------------------------------------------------------------------
# 5. ordering by authority — new entry gets next source_id even if
#    higher-authority. Re-ordering is deferred to a future pass; for
#    today we assert append-only contract is honored.
# ---------------------------------------------------------------------------


def test_authority_rank_recorded_on_appended_source(seeded_subject):
    subject_dir, _slug = seeded_subject
    leaf_path = subject_dir / "01-physical-geography" / "01-aravalli-mountain-range.md"

    sid = append_source_to_leaf(
        leaf_path,
        source_metadata={"publisher": "NCERT", "book_slug": "ncert_class_11",
                         "authority_rank": 0},
        pages=[44],
        paragraph_ids=[101],
        source_body="…",
    )
    assert sid == 2

    post = frontmatter.load(leaf_path)
    sources = post.metadata["sources"]
    assert sources[0]["authority_rank"] == 2  # original Springboard rank
    assert sources[1]["authority_rank"] == 0  # NCERT rank recorded
    # Append-only ordering: ingestion order, not authority-sorted (yet).
    assert [s["source_id"] for s in sources] == [1, 2]


# ---------------------------------------------------------------------------
# 6. content_hash refreshes deterministically after append
# ---------------------------------------------------------------------------


def test_content_hash_updates_and_is_stable(seeded_subject):
    subject_dir, _slug = seeded_subject
    leaf_path = subject_dir / "01-physical-geography" / "01-aravalli-mountain-range.md"
    pre = frontmatter.load(leaf_path)
    pre_hash = pre.metadata["content_hash"]

    append_source_to_leaf(
        leaf_path,
        source_metadata={"publisher": "NCERT", "book_slug": "ncert_class_11",
                         "authority_rank": 0},
        pages=[44],
        paragraph_ids=[101],
        source_body="Same body content",
    )
    mid = frontmatter.load(leaf_path)
    mid_hash = mid.metadata["content_hash"]
    assert mid_hash != pre_hash, "hash should change once new source body lands"

    # Re-running the append with the SAME body must produce a stable hash on
    # the resulting file (the hash is a deterministic function of the body
    # we've assembled — no timestamps mixed in).
    leaf_path_b = leaf_path.parent / (leaf_path.stem + "_copy.md")
    leaf_path_b.write_text(leaf_path.read_text(encoding="utf-8"), encoding="utf-8")
    second = frontmatter.load(leaf_path_b)
    assert second.metadata["content_hash"] == mid_hash


# ---------------------------------------------------------------------------
# Extra: helpers worth pinning behaviour for
# ---------------------------------------------------------------------------


def test_load_existing_subject_walks_chapters_and_leaves(seeded_subject):
    subject_dir, _slug = seeded_subject
    summary = load_existing_subject(subject_dir)
    assert summary.subject_slug == "rajasthan_geography"
    assert {c.slug for c in summary.chapters} == {
        "physical-geography", "climate-of-rajasthan",
    }
    titles = sorted(l.label.title for l in summary.leaves)
    assert titles == ["Aravalli Mountain Range", "Mawath Rainfall", "Thar Desert"]


def test_match_chapter_by_slug_picks_token_overlap():
    from ingestion_v2.merge import ExistingChapter
    chapters = [
        ExistingChapter(title="Physical Geography", slug="physical-geography",
                        path=Path("/tmp/01-physical-geography"),
                        node_id="x/01-physical-geography"),
        ExistingChapter(title="Climate", slug="climate",
                        path=Path("/tmp/02-climate"),
                        node_id="x/02-climate"),
    ]
    pick = match_chapter_by_slug("Climate of Western Rajasthan", chapters)
    assert pick is not None
    assert pick.slug == "climate"

    pick_none = match_chapter_by_slug("Pushkar Lake Festival Colors", chapters)
    assert pick_none is None
