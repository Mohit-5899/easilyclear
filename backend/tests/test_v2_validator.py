"""Tests for ProposedTree structural validator (spec Addendum A.9)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from ingestion_v2.multi_agent import ProposedNode, ProposedTree


def _root(*children: ProposedNode) -> dict:
    return {
        "title": "Book",
        "description": "x",
        "paragraph_start": None,
        "paragraph_end": None,
        "children": [c.model_dump() for c in children],
    }


def _leaf(title: str, start: int | None, end: int | None) -> ProposedNode:
    return ProposedNode(
        title=title,
        description="x",
        paragraph_start=start,
        paragraph_end=end,
        children=[],
    )


def test_valid_tree_with_two_leaves_passes():
    tree = ProposedTree(
        root=ProposedNode.model_validate(
            _root(_leaf("A", 0, 10), _leaf("B", 11, 20))
        )
    )
    assert len(tree.root.children) == 2


def test_null_start_is_rejected():
    with pytest.raises(ValidationError, match="null paragraph_start"):
        ProposedTree(
            root=ProposedNode.model_validate(
                _root(_leaf("OK", 0, 10), _leaf("STUB", None, None))
            )
        )


def test_inverted_range_is_rejected():
    with pytest.raises(ValidationError, match="end .* < start"):
        ProposedTree(
            root=ProposedNode.model_validate(
                _root(_leaf("Bad", 10, 5))
            )
        )


def test_overlapping_siblings_are_rejected():
    with pytest.raises(ValidationError, match="overlapping leaf ranges"):
        ProposedTree(
            root=ProposedNode.model_validate(
                _root(_leaf("A", 0, 10), _leaf("B", 8, 20))
            )
        )


def test_nested_leaf_with_null_is_rejected():
    """A leaf two levels deep must also satisfy the no-null rule."""
    inner_leaf = _leaf("Deep", None, None)
    chapter = ProposedNode(
        title="Ch1", description="x",
        paragraph_start=None, paragraph_end=None,
        children=[inner_leaf],
    )
    with pytest.raises(ValidationError, match="null paragraph_start"):
        ProposedTree(
            root=ProposedNode(
                title="Book", description="x",
                paragraph_start=None, paragraph_end=None,
                children=[chapter],
            )
        )
