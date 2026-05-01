"""Multi-book BM25 scope resolver for the agentic tutor.

Per docs/research/2026-05-02-ux-redesign-architecture.md §3 — the agent
calls ``lookup_skill_content`` with a scope tag (all/book/node). This
module builds a BM25 retriever for any of those scopes and caches the
indices in process memory, keyed by ``(scope, book_slug?, node_id?)``.

Hackathon scale: <20K paragraphs total — one in-process LRU is plenty.
Post-hackathon migrate to SQLite/Tantivy if multi-process replicas appear.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from .retriever import (
    BM25Retriever,
    _parse_leaf_paragraphs,
    _walk_leaf_files,
    build_retriever_for_node,
)


logger = logging.getLogger(__name__)


Scope = Literal["all", "book", "node"]


def _scope_label_for_book(skill_root: Path, book_slug: str) -> str:
    """Read the book root SKILL.md frontmatter for a friendly label."""
    # Books are nested under <subject>/<book_slug>/. Walk subjects to find it.
    for subject_dir in skill_root.iterdir():
        if not subject_dir.is_dir():
            continue
        candidate = subject_dir / book_slug
        if candidate.is_dir():
            try:
                import frontmatter
                post = frontmatter.load(candidate / "SKILL.md")
                name = post.metadata.get("name")
                if name:
                    return str(name)
            except (OSError, ValueError):
                pass
            return book_slug
    return book_slug


def _list_book_dirs(skill_root: Path) -> list[Path]:
    """Return every book root directory under ``skill_root``.

    Layout: ``<skill_root>/<subject>/<book_slug>/`` (book dir contains the
    book root SKILL.md).
    """
    out: list[Path] = []
    if not skill_root.is_dir():
        return out
    for subject_dir in skill_root.iterdir():
        if not subject_dir.is_dir():
            continue
        for book_dir in subject_dir.iterdir():
            if not book_dir.is_dir():
                continue
            # Skip preserved comparison snapshots (e.g. .v2.0-buggy,
            # .v2.1-shifted). They duplicate the live book's paragraphs
            # and contaminate retrieval scores.
            name = book_dir.name
            if "." in name or name.startswith("_"):
                continue
            if (book_dir / "SKILL.md").is_file():
                out.append(book_dir)
    return out


def _build_all_books_retriever(skill_root: Path) -> BM25Retriever:
    """Build a single BM25 corpus across every book on disk."""
    paragraphs: list[dict] = []
    for book_dir in _list_book_dirs(skill_root):
        for leaf_path in _walk_leaf_files(book_dir, ""):
            try:
                paragraphs.extend(_parse_leaf_paragraphs(leaf_path))
            except (OSError, ValueError) as exc:
                logger.warning(
                    "scope: skipping leaf %s (%s)", leaf_path, exc,
                )
    return BM25Retriever(paragraphs)


def _build_book_retriever(skill_root: Path, book_slug: str) -> BM25Retriever:
    """Build a BM25 corpus across one book's leaves."""
    paragraphs: list[dict] = []
    for book_dir in _list_book_dirs(skill_root):
        if book_dir.name != book_slug:
            continue
        for leaf_path in _walk_leaf_files(book_dir, ""):
            try:
                paragraphs.extend(_parse_leaf_paragraphs(leaf_path))
            except (OSError, ValueError):
                continue
    return BM25Retriever(paragraphs)


def build_retriever_for_scope(
    skill_root: Path,
    scope: Scope,
    *,
    book_slug: str | None = None,
    node_id: str | None = None,
) -> BM25Retriever:
    """Resolve ``scope`` to a BM25 retriever.

    Args:
        skill_root: filesystem root of skill folders, typically ``database/skills``.
        scope: one of "all", "book", "node".
        book_slug: required when scope == "book".
        node_id: required when scope == "node" (a fully-qualified node_id
            like ``geography/<book>/<chapter>/<leaf>`` — same convention used
            by ``build_retriever_for_node``).

    Raises:
        ValueError: if required fields for the scope are missing.
        FileNotFoundError: if the skill_root or scoped target does not exist.
    """
    if scope == "all":
        return _build_all_books_retriever(skill_root)
    if scope == "book":
        if not book_slug:
            raise ValueError("scope='book' requires book_slug")
        return _build_book_retriever(skill_root, book_slug)
    if scope == "node":
        if not node_id:
            raise ValueError("scope='node' requires node_id")
        return build_retriever_for_node(skill_root, node_id)
    raise ValueError(f"unknown scope: {scope!r}")


def scope_label(
    skill_root: Path,
    scope: Scope,
    *,
    book_slug: str | None = None,
    node_id: str | None = None,
) -> str:
    """Human-readable label for a scope. Used in tool-call SSE events."""
    if scope == "all":
        return "All books"
    if scope == "book":
        if not book_slug:
            return "Unknown book"
        return _scope_label_for_book(skill_root, book_slug)
    if scope == "node":
        if not node_id:
            return "Unknown node"
        return node_id.split("/")[-1].replace("-", " ").replace("_", " ").title()
    return scope


def serialize_scope_args(
    scope: Scope, book_slug: str | None, node_id: str | None
) -> str:
    """Cache key for a scoped retriever (used by callers that memoize)."""
    return json.dumps(
        {"scope": scope, "book_slug": book_slug, "node_id": node_id},
        sort_keys=True,
    )
