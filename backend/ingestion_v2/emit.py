"""Stage 8 of the V2 pipeline — emit the skill folder.

Writes the FilledTree to disk as an Anthropic-Skills-style folder:

    <output_root>/<subject>/<book_slug>/
        SKILL.md                              (root)
        01-<slug>/
            SKILL.md                          (chapter internal node)
            01-<slug>.md                      (leaf)
            02-<slug>.md
        02-<slug>/
            ...

Existing folder at that path is deleted and rewritten from scratch — this
is a build artifact, not a mutable resource.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter

from .content_fill import FilledNode, FilledTree


logger = logging.getLogger(__name__)


_SLUG_MAX_LEN = 60


def slugify(text: str) -> str:
    """Lowercase, ASCII-only, kebab-case slug. Capped at 60 chars."""
    if not text:
        return "untitled"
    # Normalize unicode, drop accents, keep ASCII.
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_only = ascii_only.lower()
    # Replace runs of non-alphanumeric with a single hyphen.
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only)
    slug = slug.strip("-")
    if not slug:
        return "untitled"
    if len(slug) > _SLUG_MAX_LEN:
        slug = slug[:_SLUG_MAX_LEN].rstrip("-")
    return slug


def _content_hash(body: str) -> str:
    """Stable sha256 of the markdown body, used for re-ingestion diffing."""
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dump_frontmatter(body: str, metadata: dict[str, Any]) -> str:
    """Render a full .md file as YAML frontmatter + body, using
    python-frontmatter for correct escaping."""
    post = frontmatter.Post(content=body, **metadata)
    return frontmatter.dumps(post)


def _write_md(path: Path, body: str, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_frontmatter(body, metadata), encoding="utf-8")


def _build_root_metadata(
    root: FilledNode,
    subject: str,
    book_slug: str,
    book_metadata: dict[str, Any],
    ingested_at: str,
) -> dict[str, Any]:
    return {
        "name": book_metadata.get("name") or root.title,
        "description": root.description,
        "node_id": f"{subject}/{book_slug}",
        "depth": 0,
        "subject": subject,
        "source_book": book_slug,
        "subject_scope": book_metadata.get("scope", "unknown"),
        "exam_coverage": book_metadata.get("exam_coverage", []),
        "source_publisher": book_metadata.get("publisher", "unknown"),
        "source_url": book_metadata.get("source_url", ""),
        "ingested_at": ingested_at,
        "ingestion_version": "v2",
        "content_hash": _content_hash(root.body),
    }


def _build_child_metadata(
    node: FilledNode,
    parent_node_id: str,
    depth: int,
    position: int,
    slug: str,
    subject: str,
    book_slug: str,
    ingested_at: str,
) -> dict[str, Any]:
    node_id = f"{parent_node_id}/{position:02d}-{slug}"
    return {
        "name": node.title,
        "description": node.description,
        "node_id": node_id,
        "parent": parent_node_id,
        "depth": depth,
        "order": position,
        "subject": subject,
        "source_book": book_slug,
        "source_pages": node.source_pages,
        "ingested_at": ingested_at,
        "ingestion_version": "v2",
        "content_hash": _content_hash(node.body),
        "related_skills": [],
        "superseded_by": None,
    }


def _unique_slug(base: str, used: set[str]) -> str:
    """Return a slug that isn't already in `used`. Appends -2, -3, ... as needed."""
    if base not in used:
        used.add(base)
        return base
    counter = 2
    while True:
        candidate = f"{base}-{counter}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        counter += 1


def _emit_subtree(
    node: FilledNode,
    *,
    parent_dir: Path,
    parent_node_id: str,
    depth: int,
    position: int,
    used_slugs_in_parent: set[str],
    subject: str,
    book_slug: str,
    ingested_at: str,
) -> None:
    """Write one child node and recurse. `position` is 1-indexed sibling order."""
    slug = _unique_slug(slugify(node.title), used_slugs_in_parent)
    prefix = f"{position:02d}-{slug}"
    node_id = f"{parent_node_id}/{prefix}"

    metadata = _build_child_metadata(
        node=node,
        parent_node_id=parent_node_id,
        depth=depth,
        position=position,
        slug=slug,
        subject=subject,
        book_slug=book_slug,
        ingested_at=ingested_at,
    )
    # Override node_id with the positional form:
    metadata["node_id"] = node_id

    if node.children:
        # Internal node → directory with SKILL.md and children files.
        chapter_dir = parent_dir / prefix
        chapter_dir.mkdir(parents=True, exist_ok=True)
        _write_md(chapter_dir / "SKILL.md", node.body, metadata)

        child_used: set[str] = set()
        for child_idx, child in enumerate(node.children, start=1):
            _emit_subtree(
                node=child,
                parent_dir=chapter_dir,
                parent_node_id=node_id,
                depth=depth + 1,
                position=child_idx,
                used_slugs_in_parent=child_used,
                subject=subject,
                book_slug=book_slug,
                ingested_at=ingested_at,
            )
    else:
        # Leaf → a single .md file next to siblings.
        _write_md(parent_dir / f"{prefix}.md", node.body, metadata)


async def emit_skill_folder(
    filled: FilledTree,
    subject: str,
    book_slug: str,
    book_metadata: dict[str, Any],
    output_root: Path,
) -> Path:
    """Write the filled tree as a skill folder. Returns the book's folder path.

    The target folder (`<output_root>/<subject>/<book_slug>/`) is deleted if
    it already exists so every emit is a fresh write.
    """
    ingested_at = _now_iso()
    book_folder = output_root / subject / book_slug

    if book_folder.exists():
        logger.info("emit: removing existing folder at %s", book_folder)
        shutil.rmtree(book_folder)
    book_folder.mkdir(parents=True, exist_ok=True)

    root_metadata = _build_root_metadata(
        root=filled.root,
        subject=subject,
        book_slug=book_slug,
        book_metadata=book_metadata,
        ingested_at=ingested_at,
    )
    _write_md(book_folder / "SKILL.md", filled.root.body, root_metadata)

    parent_node_id = f"{subject}/{book_slug}"
    used_slugs: set[str] = set()
    for idx, child in enumerate(filled.root.children, start=1):
        _emit_subtree(
            node=child,
            parent_dir=book_folder,
            parent_node_id=parent_node_id,
            depth=1,
            position=idx,
            used_slugs_in_parent=used_slugs,
            subject=subject,
            book_slug=book_slug,
            ingested_at=ingested_at,
        )

    logger.info("emit: wrote skill folder at %s", book_folder)
    return book_folder
