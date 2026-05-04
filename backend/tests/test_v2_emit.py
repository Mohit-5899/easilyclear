"""Tests for the v3 emit (subject-canonical, multi-source frontmatter).

Per spec docs/superpowers/specs/2026-05-04-subject-canonical-tree.md.
Asserts the on-disk shape: layout, frontmatter keys, brand-strip rules,
and the SubjectTreeExistsError guard.
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
from ingestion_v2.emit import (
    SubjectTreeExistsError,
    emit_skill_folder,
    slugify,
)


def _leaf(title: str, body: str, paragraph_refs: list[int], pages: list[int]) -> FilledNode:
    return FilledNode(
        title=title,
        description=f"Test leaf {title}",
        paragraph_refs=paragraph_refs,
        body=body,
        source_pages=pages,
    )


def _tree(*, root_body: str = "## Contents\n", chapters: list[FilledNode] | None = None) -> FilledTree:
    root = FilledNode(
        title="Test Subject",
        description="Test root",
        paragraph_refs=[],
        body=root_body,
        source_pages=[],
        children=list(chapters or []),
    )
    return FilledTree(root=root)


def _emit_default(tmp_path: Path, **overrides) -> Path:
    """Helper: emit a one-leaf tree with default kwargs."""
    chap = FilledNode(
        title="Chapter 1",
        description="ch1 desc",
        paragraph_refs=[],
        body="## Contents\n- one\n",
        source_pages=[],
        children=[
            _leaf("First Leaf", "Aravalli is the oldest mountain.\n\nGurushikhar is highest peak.",
                  paragraph_refs=[0, 1], pages=[18, 19]),
        ],
    )
    tree = _tree(chapters=[chap])
    return asyncio.run(emit_skill_folder(
        filled=tree,
        subject_slug=overrides.get("subject_slug", "test_subject"),
        book_metadata={"name": overrides.get("name", "Test Subject")},
        output_root=tmp_path,
        source_metadata=overrides.get("source_metadata", {
            "publisher": "Springboard Academy",
            "book_slug": "springboard_test",
            "authority_rank": 2,
        }),
        overwrite=overrides.get("overwrite", False),
    ))


def test_emit_writes_subject_folder_at_root(tmp_path: Path):
    folder = _emit_default(tmp_path)
    assert folder == tmp_path / "test_subject"
    # No book_slug subfolder!
    assert (folder / "SKILL.md").is_file()
    assert (folder / "01-chapter-1").is_dir()


def test_leaf_body_wrapped_with_source_header(tmp_path: Path):
    folder = _emit_default(tmp_path)
    leaf = folder / "01-chapter-1" / "01-first-leaf.md"
    post = frontmatter.load(leaf)
    assert post.content.startswith("## Source 1 (pages 18-19)")
    # Verbatim content preserved AFTER the header
    assert "Aravalli is the oldest mountain." in post.content


def test_leaf_frontmatter_has_sources_list(tmp_path: Path):
    folder = _emit_default(tmp_path)
    leaf = folder / "01-chapter-1" / "01-first-leaf.md"
    meta = frontmatter.load(leaf).metadata
    assert isinstance(meta.get("sources"), list)
    s = meta["sources"][0]
    assert s["source_id"] == 1
    assert s["publisher"] == "Springboard Academy"
    assert s["book_slug"] == "springboard_test"
    assert s["authority_rank"] == 2
    assert s["pages"] == [18, 19]
    assert s["paragraph_ids"] == [0, 1]
    # Legacy v2 fields must be GONE — they leaked publisher names.
    assert "source_book" not in meta
    assert "source_publisher" not in meta


def test_root_metadata_carries_subject_slug_not_book(tmp_path: Path):
    folder = _emit_default(tmp_path)
    meta = frontmatter.load(folder / "SKILL.md").metadata
    assert meta["node_id"] == "test_subject"
    assert meta["subject"] == "test_subject"
    assert meta["ingestion_version"] == "v3"
    # Sources is populated at the root too (single source for first ingest)
    assert meta["sources"][0]["publisher"] == "Springboard Academy"


def test_emit_refuses_to_overwrite_existing_tree(tmp_path: Path):
    _emit_default(tmp_path)
    # Second emit with overwrite=False must raise.
    with pytest.raises(SubjectTreeExistsError, match="already exists"):
        _emit_default(tmp_path)


def test_emit_overwrite_true_clobbers(tmp_path: Path):
    folder1 = _emit_default(tmp_path)
    sentinel = folder1 / "01-chapter-1" / "01-first-leaf.md"
    original_size = sentinel.stat().st_size
    # Overwrite with a tree that has different content.
    chap = FilledNode(
        title="Chapter 1", description="ch1 v2",
        paragraph_refs=[], body="## Contents\n", source_pages=[],
        children=[
            _leaf("First Leaf", "Banas is the longest river in Rajasthan.",
                  paragraph_refs=[0], pages=[42]),
        ],
    )
    asyncio.run(emit_skill_folder(
        filled=_tree(chapters=[chap]),
        subject_slug="test_subject",
        book_metadata={"name": "Test Subject"},
        output_root=tmp_path,
        source_metadata={
            "publisher": "Springboard Academy",
            "book_slug": "springboard_test",
            "authority_rank": 2,
        },
        overwrite=True,
    ))
    new_size = sentinel.stat().st_size
    assert new_size != original_size
    assert "Banas" in sentinel.read_text()


def test_no_brand_strings_in_body(tmp_path: Path):
    """Spec rule: publisher names live ONLY in frontmatter, never the body."""
    folder = _emit_default(tmp_path)
    leaf_body = (folder / "01-chapter-1" / "01-first-leaf.md").read_text()
    body_only = leaf_body.split("\n---\n", 2)[-1]
    # Body must mention "Source 1" but not "Springboard"
    assert "Source 1" in body_only
    assert "Springboard" not in body_only
    assert "Academy" not in body_only


def test_slugify_produces_kebab_lowercase_ascii():
    assert slugify("Aravalli Mountain Range") == "aravalli-mountain-range"
    assert slugify("Climate of Rajasthan!") == "climate-of-rajasthan"
    # Non-ASCII gets stripped
    assert slugify("Café & résumé") == "cafe-resume"
    # Empty / weird input falls back to a stable default
    assert slugify("") == "untitled"
    assert slugify("***") == "untitled"
