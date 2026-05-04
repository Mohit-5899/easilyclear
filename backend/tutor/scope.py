"""Subject-canonical BM25 scope resolver for the agentic tutor.

Per docs/superpowers/specs/2026-05-04-subject-canonical-tree.md.

Layout (post-migration):
    <skill_root>/<subject_slug>/SKILL.md           ← subject root
    <skill_root>/<subject_slug>/01-<chapter>/...   ← chapters + leaves

Scope levels exposed to the agent:
    all     — every subject's canonical tree
    subject — one subject's canonical tree
    node    — one leaf or sub-tree (delegates to retriever.build_retriever_for_node)

Hackathon scale: <20K paragraphs total — one in-process index per call is
plenty. Post-hackathon, cache + invalidate on disk-mtime.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

from .retriever import (
    BM25Retriever,
    _parse_leaf_paragraphs,
    _walk_leaf_files,
    build_retriever_for_node,
)


logger = logging.getLogger(__name__)


Scope = Literal["all", "subject", "node"]


def _scope_label_for_subject(skill_root: Path, subject_slug: str) -> str:
    """Read the subject root SKILL.md frontmatter for a friendly label."""
    candidate = skill_root / subject_slug / "SKILL.md"
    if candidate.is_file():
        try:
            import frontmatter
            post = frontmatter.load(candidate)
            name = post.metadata.get("name")
            if name:
                return str(name)
        except (OSError, ValueError):
            pass
    # Fallback: prettify the slug.
    return subject_slug.replace("_", " ").replace("-", " ").title()


def _list_subject_dirs(skill_root: Path) -> list[Path]:
    """Return every subject canonical-tree root under ``skill_root``.

    A subject directory has a ``SKILL.md`` directly inside it (not nested
    under a book_slug). Hidden / dotted / underscored directories are
    skipped — that pattern reserves the namespace for archived snapshots
    (e.g. ``geography.v2.0-buggy``) without needing a separate exclusion list.
    """
    out: list[Path] = []
    if not skill_root.is_dir():
        return out
    for subject_dir in skill_root.iterdir():
        if not subject_dir.is_dir():
            continue
        name = subject_dir.name
        if name.startswith(".") or name.startswith("_") or "." in name:
            continue
        if (subject_dir / "SKILL.md").is_file():
            out.append(subject_dir)
    return out


def _build_all_subjects_retriever(skill_root: Path) -> BM25Retriever:
    """One BM25 corpus across every subject canonical tree on disk."""
    paragraphs: list[dict] = []
    for subject_dir in _list_subject_dirs(skill_root):
        for leaf_path in _walk_leaf_files(subject_dir, ""):
            try:
                paragraphs.extend(_parse_leaf_paragraphs(leaf_path))
            except (OSError, ValueError) as exc:
                logger.warning("scope: skipping leaf %s (%s)", leaf_path, exc)
    return BM25Retriever(paragraphs)


def _build_subject_retriever(
    skill_root: Path, subject_slug: str
) -> BM25Retriever:
    """BM25 corpus over one subject's leaves."""
    subject_dir = skill_root / subject_slug
    if not subject_dir.is_dir() or not (subject_dir / "SKILL.md").is_file():
        raise FileNotFoundError(f"subject not found: {subject_slug}")
    paragraphs: list[dict] = []
    for leaf_path in _walk_leaf_files(subject_dir, ""):
        try:
            paragraphs.extend(_parse_leaf_paragraphs(leaf_path))
        except (OSError, ValueError):
            continue
    return BM25Retriever(paragraphs)


def build_retriever_for_scope(
    skill_root: Path,
    scope: Scope,
    *,
    subject_slug: str | None = None,
    node_id: str | None = None,
) -> BM25Retriever:
    """Resolve ``scope`` to a BM25 retriever.

    Args:
        skill_root: filesystem root of skill folders (``database/skills``).
        scope: one of "all", "subject", "node".
        subject_slug: required when scope == "subject".
        node_id: required when scope == "node" (e.g.
            ``rajasthan_geography/02-physiographic-divisions/03-aravali``).

    Raises:
        ValueError: required field missing for the chosen scope.
        FileNotFoundError: skill_root, subject, or node does not exist.
    """
    if scope == "all":
        return _build_all_subjects_retriever(skill_root)
    if scope == "subject":
        if not subject_slug:
            raise ValueError("scope='subject' requires subject_slug")
        return _build_subject_retriever(skill_root, subject_slug)
    if scope == "node":
        if not node_id:
            raise ValueError("scope='node' requires node_id")
        return build_retriever_for_node(skill_root, node_id)
    raise ValueError(f"unknown scope: {scope!r}")


def scope_label(
    skill_root: Path,
    scope: Scope,
    *,
    subject_slug: str | None = None,
    node_id: str | None = None,
) -> str:
    """Human-readable label for a scope. Used in tool-call SSE events.

    Never returns publisher names — only subject titles or leaf names.
    """
    if scope == "all":
        return "All subjects"
    if scope == "subject":
        if not subject_slug:
            return "Unknown subject"
        return _scope_label_for_subject(skill_root, subject_slug)
    if scope == "node":
        if not node_id:
            return "Unknown node"
        return node_id.split("/")[-1].replace("-", " ").replace("_", " ").title()
    return scope


def serialize_scope_args(
    scope: Scope, subject_slug: str | None, node_id: str | None
) -> str:
    """Cache key for a scoped retriever (used by callers that memoize)."""
    return json.dumps(
        {"scope": scope, "subject_slug": subject_slug, "node_id": node_id},
        sort_keys=True,
    )
