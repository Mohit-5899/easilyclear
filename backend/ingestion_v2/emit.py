"""Stage 8 of the V2 pipeline — emit the skill folder (v3 schema).

Per docs/superpowers/specs/2026-05-04-subject-canonical-tree.md.

Layout:
    <output_root>/<subject_slug>/
        SKILL.md                              ← subject root
        01-<chapter-slug>/
            SKILL.md                          ← chapter (internal node)
            01-<leaf-slug>.md                 ← leaf (multi-source body)
            02-<leaf-slug>.md
        02-<chapter-slug>/
            ...

Leaf bodies are wrapped with `## Source N (pages X-Y)` headers. Frontmatter
carries a `sources: [...]` list. Brand names live in `sources[].publisher`
only — never rendered to the student's UI.

For first-ingest of a subject this produces a single-source tree
(`source_id: 1` everywhere). Multi-source merging is the merge.py stage
that runs BEFORE emit when an existing subject tree is on disk.
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
_INGESTION_VERSION = "v3"


def slugify(text: str) -> str:
    """Lowercase, ASCII-only, kebab-case slug. Capped at 60 chars."""
    if not text:
        return "untitled"
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    if not slug:
        return "untitled"
    if len(slug) > _SLUG_MAX_LEN:
        slug = slug[:_SLUG_MAX_LEN].rstrip("-")
    return slug


def _content_hash(body: str) -> str:
    return f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_pages(pages: list[int]) -> str:
    """Render a page list as 'pages 18-19' or 'page 18'."""
    cleaned = sorted({p for p in pages if isinstance(p, int) and p > 0})
    if not cleaned:
        return "pages unknown"
    if len(cleaned) == 1:
        return f"page {cleaned[0]}"
    return f"pages {cleaned[0]}-{cleaned[-1]}"


def _wrap_leaf_body(body: str, pages: list[int]) -> str:
    """Prefix the verbatim leaf body with a `## Source 1 (...)` header.

    Idempotent — if the body already starts with a `## Source ` header
    we leave it alone (avoids double-wrapping during re-emit).
    """
    stripped = body.strip()
    if stripped.startswith("## Source "):
        return stripped + "\n"
    return f"## Source 1 ({_format_pages(pages)})\n\n{stripped}\n"


def _dump_frontmatter(body: str, metadata: dict[str, Any]) -> str:
    return frontmatter.dumps(frontmatter.Post(content=body, **metadata))


def _write_md(path: Path, body: str, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_frontmatter(body, metadata), encoding="utf-8")


def _build_root_metadata(
    root: FilledNode,
    subject_slug: str,
    book_metadata: dict[str, Any],
    source_metadata: dict[str, Any],
    ingested_at: str,
) -> dict[str, Any]:
    return {
        "name": book_metadata.get("name") or root.title,
        "description": root.description,
        "node_id": subject_slug,
        "depth": 0,
        "subject": subject_slug,
        "subject_scope": book_metadata.get("scope", "unknown"),
        "exam_coverage": book_metadata.get("exam_coverage", []),
        "ingested_at": ingested_at,
        "ingestion_version": _INGESTION_VERSION,
        "content_hash": _content_hash(root.body),
        "sources": [
            {
                "source_id": 1,
                "publisher": source_metadata.get("publisher", "unknown"),
                "book_slug": source_metadata.get("book_slug", ""),
                "authority_rank": int(source_metadata.get("authority_rank", 3)),
                "ingested_at": ingested_at,
            }
        ],
    }


def _build_internal_metadata(
    node: FilledNode,
    *,
    parent_node_id: str,
    node_id: str,
    depth: int,
    position: int,
    subject_slug: str,
    ingested_at: str,
) -> dict[str, Any]:
    return {
        "name": node.title,
        "description": node.description,
        "node_id": node_id,
        "parent": parent_node_id,
        "depth": depth,
        "order": position,
        "subject": subject_slug,
        "ingested_at": ingested_at,
        "ingestion_version": _INGESTION_VERSION,
        "content_hash": _content_hash(node.body),
    }


def _build_leaf_metadata(
    node: FilledNode,
    *,
    parent_node_id: str,
    node_id: str,
    depth: int,
    position: int,
    wrapped_body: str,
    paragraph_ids: list[int],
    subject_slug: str,
    source_metadata: dict[str, Any],
    ingested_at: str,
) -> dict[str, Any]:
    return {
        "name": node.title,
        "description": node.description,
        "node_id": node_id,
        "parent": parent_node_id,
        "depth": depth,
        "order": position,
        "subject": subject_slug,
        "ingested_at": ingested_at,
        "ingestion_version": _INGESTION_VERSION,
        "content_hash": _content_hash(wrapped_body),
        "sources": [
            {
                "source_id": 1,
                "publisher": source_metadata.get("publisher", "unknown"),
                "book_slug": source_metadata.get("book_slug", ""),
                "pages": list(node.source_pages),
                "paragraph_ids": paragraph_ids,
                "authority_rank": int(source_metadata.get("authority_rank", 3)),
                "ingested_at": ingested_at,
            }
        ],
        "related_skills": [],
        "superseded_by": None,
    }


def _unique_slug(base: str, used: set[str]) -> str:
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
    subject_slug: str,
    source_metadata: dict[str, Any],
    ingested_at: str,
) -> None:
    slug = _unique_slug(slugify(node.title), used_slugs_in_parent)
    prefix = f"{position:02d}-{slug}"
    node_id = f"{parent_node_id}/{prefix}"

    if node.children:
        chapter_dir = parent_dir / prefix
        chapter_dir.mkdir(parents=True, exist_ok=True)
        metadata = _build_internal_metadata(
            node, parent_node_id=parent_node_id, node_id=node_id,
            depth=depth, position=position, subject_slug=subject_slug,
            ingested_at=ingested_at,
        )
        _write_md(chapter_dir / "SKILL.md", node.body, metadata)
        child_used: set[str] = set()
        for child_idx, child in enumerate(node.children, start=1):
            _emit_subtree(
                node=child, parent_dir=chapter_dir,
                parent_node_id=node_id, depth=depth + 1, position=child_idx,
                used_slugs_in_parent=child_used,
                subject_slug=subject_slug, source_metadata=source_metadata,
                ingested_at=ingested_at,
            )
        return

    paragraph_ids = list(node.paragraph_refs)
    wrapped = _wrap_leaf_body(node.body, node.source_pages)
    metadata = _build_leaf_metadata(
        node, parent_node_id=parent_node_id, node_id=node_id,
        depth=depth, position=position, wrapped_body=wrapped,
        paragraph_ids=paragraph_ids,
        subject_slug=subject_slug, source_metadata=source_metadata,
        ingested_at=ingested_at,
    )
    _write_md(parent_dir / f"{prefix}.md", wrapped, metadata)


class SubjectTreeExistsError(RuntimeError):
    """Raised when a subject canonical tree already exists on disk.

    Per spec, the merge stage (P2.5) must run BEFORE emit when this fires.
    For now we refuse to clobber so future ingestions can't silently
    overwrite a populated subject tree. Once merge.py lands, the pipeline
    will route through it instead of calling emit_skill_folder directly.
    """


async def emit_skill_folder(
    filled: FilledTree,
    subject_slug: str,
    book_metadata: dict[str, Any],
    output_root: Path,
    *,
    source_metadata: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> Path:
    """Write the filled tree as a v3 subject-canonical skill folder.

    Args:
        filled: tree from Stage 7.
        subject_slug: canonical slug, e.g. ``"rajasthan_geography"``.
        book_metadata: free-form dict; ``name`` / ``scope`` / ``exam_coverage``
            land in the root SKILL.md frontmatter.
        output_root: usually ``<repo>/database/skills``.
        source_metadata: per-source provenance — ``publisher``, ``book_slug``,
            ``authority_rank``. Used to populate the leaves' ``sources[]``.
        overwrite: if True, an existing subject folder is removed before
            writing. Default False — refuses to overwrite (call merge.py
            in that case to combine sources).

    Raises:
        SubjectTreeExistsError: subject folder exists and overwrite=False.
    """
    ingested_at = _now_iso()
    src_meta = source_metadata or {}
    subject_folder = output_root / subject_slug

    if subject_folder.exists():
        if not overwrite:
            raise SubjectTreeExistsError(
                f"subject folder already exists at {subject_folder}. "
                f"Pass overwrite=True to clobber, or route through "
                f"merge.py to add this as an additional source."
            )
        logger.info("emit: removing existing folder at %s", subject_folder)
        shutil.rmtree(subject_folder)
    subject_folder.mkdir(parents=True, exist_ok=True)

    root_metadata = _build_root_metadata(
        root=filled.root, subject_slug=subject_slug,
        book_metadata=book_metadata, source_metadata=src_meta,
        ingested_at=ingested_at,
    )
    _write_md(subject_folder / "SKILL.md", filled.root.body, root_metadata)

    used_slugs: set[str] = set()
    for idx, child in enumerate(filled.root.children, start=1):
        _emit_subtree(
            node=child, parent_dir=subject_folder,
            parent_node_id=subject_slug, depth=1, position=idx,
            used_slugs_in_parent=used_slugs,
            subject_slug=subject_slug, source_metadata=src_meta,
            ingested_at=ingested_at,
        )

    logger.info("emit: wrote skill folder at %s", subject_folder)
    return subject_folder
