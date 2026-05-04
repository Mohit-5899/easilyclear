"""One-shot migration: book-keyed tree → subject-canonical tree.

Per docs/superpowers/specs/2026-05-04-subject-canonical-tree.md Phase 1.

Reads:
    database/skills/<old_subject>/<book_slug>/

Writes:
    database/skills/<new_subject>/

Per-leaf rewrites:
    - Body becomes "## Source 1 (pages X-Y)\\n\\n<original verbatim body>"
    - Frontmatter gets a `sources: [{source_id, publisher, book_slug, pages,
      paragraph_ids, authority_rank, content_hash}]` list
    - Drops top-level fields that are now inside `sources[]`
    - Bumps `ingestion_version` to v3
    - Rewrites `node_id` to drop the `/<book_slug>/` segment

After a successful migration the old subject folder is removed (per
user decision 2026-05-04). Re-runs are safe — the script is idempotent
on the destination.

Usage:
    python scripts/migrate_to_subject_canonical.py \\
        --old-subject geography \\
        --book-slug springboard_rajasthan_geography \\
        --new-subject rajasthan_geography \\
        --publisher 'Springboard Academy' \\
        --authority-rank 2
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter


logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SKILLS_ROOT = _REPO_ROOT / "database" / "skills"

# Splits paragraphs on blank-line boundaries (matches V2 ingestion convention).
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _content_hash(body: str) -> str:
    return f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"


def _split_paragraphs(body: str) -> list[str]:
    """Same logic as ingestion_v2.extract — kept here so the script has zero
    backend imports."""
    return [
        chunk.strip()
        for chunk in _PARAGRAPH_SPLIT.split(body)
        if len(chunk.strip()) >= 20
    ]


def _format_pages(pages: list[int]) -> str:
    """Render a page list as 'pages 18-19' or 'page 18'."""
    if not pages:
        return "pages unknown"
    if len(pages) == 1:
        return f"page {pages[0]}"
    sorted_pages = sorted(set(pages))
    return f"pages {sorted_pages[0]}-{sorted_pages[-1]}"


def _rewrite_node_id(old_id: str, old_subject: str, book_slug: str, new_subject: str) -> str:
    """Drop the `/<book_slug>/` segment + swap subject prefix.

    geography/springboard_rajasthan_geography/02-physiographic-divisions/03-aravali
        →
    rajasthan_geography/02-physiographic-divisions/03-aravali
    """
    old_prefix = f"{old_subject}/{book_slug}"
    if not old_id.startswith(old_prefix):
        return old_id
    suffix = old_id[len(old_prefix):]  # leading '/...' or empty
    if suffix == "":
        return new_subject
    return f"{new_subject}{suffix}"


def _derive_subject_display_name(slug: str) -> str:
    """Turn ``rajasthan_geography`` → ``Rajasthan Geography``.

    Used as the brand-free fallback for the root SKILL.md ``name`` field
    when the caller does not pass ``--subject-name``. Per spec 2026-05-04,
    the root name surfaces on the radial canvas as the central node label
    so it MUST be brand-free.
    """
    return slug.replace("_", " ").replace("-", " ").title()


def _migrate_root_skill(
    src: Path,
    dst: Path,
    *,
    old_subject: str,
    book_slug: str,
    new_subject: str,
    publisher: str,
    authority_rank: int,
    book_metadata: dict[str, Any],
    ingested_at: str,
    subject_name: str | None = None,
) -> None:
    """Rewrite the top-level SKILL.md for the subject root.

    Spec 2026-05-04 brand-strip rule: the existing v2 root ``name`` field
    typically contains the publisher name (e.g. ``Springboard Academy —
    Rajasthan Geography``). We REPLACE it with a brand-free subject name,
    NOT carry it forward, so the canvas root label stays clean.
    """
    post = frontmatter.load(src)
    body = post.content
    canonical_name = (
        subject_name
        or book_metadata.get("subject_name")
        or _derive_subject_display_name(new_subject)
    )
    new_metadata: dict[str, Any] = {
        "name": canonical_name,
        "description": post.metadata.get("description", ""),
        "node_id": new_subject,
        "depth": 0,
        "subject": new_subject,
        "subject_scope": post.metadata.get("subject_scope", "unknown"),
        "exam_coverage": post.metadata.get("exam_coverage", []),
        "ingested_at": ingested_at,
        "ingestion_version": "v3",
        "content_hash": _content_hash(body),
        "sources": [
            {
                "source_id": 1,
                "publisher": publisher,
                "book_slug": book_slug,
                "authority_rank": authority_rank,
                "ingested_at": post.metadata.get("ingested_at", ingested_at),
            }
        ],
    }
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(frontmatter.dumps(frontmatter.Post(content=body, **new_metadata)), encoding="utf-8")


def _migrate_skill_md(
    src: Path,
    dst: Path,
    *,
    old_subject: str,
    book_slug: str,
    new_subject: str,
    ingested_at: str,
) -> None:
    """Rewrite a chapter SKILL.md (internal node — no source body, just contents outline)."""
    post = frontmatter.load(src)
    body = post.content
    old_node_id = str(post.metadata.get("node_id", ""))
    new_node_id = _rewrite_node_id(old_node_id, old_subject, book_slug, new_subject)
    parent_old = str(post.metadata.get("parent", ""))
    parent_new = (
        _rewrite_node_id(parent_old, old_subject, book_slug, new_subject)
        if parent_old else new_subject
    )

    new_metadata: dict[str, Any] = {
        "name": post.metadata.get("name", ""),
        "description": post.metadata.get("description", ""),
        "node_id": new_node_id,
        "parent": parent_new,
        "depth": post.metadata.get("depth", 1),
        "order": post.metadata.get("order", 1),
        "subject": new_subject,
        "ingested_at": ingested_at,
        "ingestion_version": "v3",
        "content_hash": _content_hash(body),
    }
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(frontmatter.dumps(frontmatter.Post(content=body, **new_metadata)), encoding="utf-8")


def _migrate_leaf(
    src: Path,
    dst: Path,
    *,
    old_subject: str,
    book_slug: str,
    new_subject: str,
    publisher: str,
    authority_rank: int,
    ingested_at: str,
) -> None:
    """Rewrite a leaf .md with multi-source frontmatter + `## Source 1` body wrapper."""
    post = frontmatter.load(src)
    original_body = post.content.strip()

    # Compute paragraph IDs from the existing body (deterministic).
    paragraphs = _split_paragraphs(original_body)
    paragraph_ids = list(range(len(paragraphs)))

    pages = post.metadata.get("source_pages") or []
    if not isinstance(pages, list):
        pages = [pages]

    # Wrap body with the source header. Only one source at this stage.
    new_body = f"## Source 1 ({_format_pages(pages)})\n\n{original_body}\n"

    old_node_id = str(post.metadata.get("node_id", ""))
    new_node_id = _rewrite_node_id(old_node_id, old_subject, book_slug, new_subject)
    parent_old = str(post.metadata.get("parent", ""))
    parent_new = (
        _rewrite_node_id(parent_old, old_subject, book_slug, new_subject)
        if parent_old else new_subject
    )

    new_metadata: dict[str, Any] = {
        "name": post.metadata.get("name", ""),
        "description": post.metadata.get("description", ""),
        "node_id": new_node_id,
        "parent": parent_new,
        "depth": post.metadata.get("depth", 2),
        "order": post.metadata.get("order", 1),
        "subject": new_subject,
        "ingested_at": ingested_at,
        "ingestion_version": "v3",
        "content_hash": _content_hash(new_body),
        "sources": [
            {
                "source_id": 1,
                "publisher": publisher,
                "book_slug": book_slug,
                "pages": pages,
                "paragraph_ids": paragraph_ids,
                "authority_rank": authority_rank,
                "content_hash": post.metadata.get("content_hash", ""),
                "ingested_at": post.metadata.get("ingested_at", ingested_at),
            }
        ],
        "related_skills": post.metadata.get("related_skills", []),
        "superseded_by": None,
    }
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(frontmatter.dumps(frontmatter.Post(content=new_body, **new_metadata)), encoding="utf-8")


def migrate_book_to_subject(
    *,
    old_subject: str,
    book_slug: str,
    new_subject: str,
    publisher: str,
    authority_rank: int,
    book_metadata: dict[str, Any],
    skills_root: Path = _SKILLS_ROOT,
    subject_name: str | None = None,
) -> Path:
    """Run the migration. Returns the new subject folder path."""
    src_root = skills_root / old_subject / book_slug
    dst_root = skills_root / new_subject
    if not src_root.is_dir():
        raise FileNotFoundError(f"source folder not found: {src_root}")

    if dst_root.exists():
        logger.info("removing existing destination %s", dst_root)
        shutil.rmtree(dst_root)
    dst_root.mkdir(parents=True)

    ingested_at = _now_iso()

    # 1. Root SKILL.md
    src_root_md = src_root / "SKILL.md"
    if src_root_md.is_file():
        _migrate_root_skill(
            src_root_md,
            dst_root / "SKILL.md",
            old_subject=old_subject,
            book_slug=book_slug,
            new_subject=new_subject,
            publisher=publisher,
            authority_rank=authority_rank,
            book_metadata=book_metadata,
            ingested_at=ingested_at,
            subject_name=subject_name,
        )

    # 2. Walk every other .md
    for src_md in src_root.rglob("*.md"):
        if src_md == src_root_md:
            continue
        rel = src_md.relative_to(src_root)
        dst_md = dst_root / rel
        if src_md.name == "SKILL.md":
            _migrate_skill_md(
                src_md, dst_md,
                old_subject=old_subject, book_slug=book_slug,
                new_subject=new_subject, ingested_at=ingested_at,
            )
        else:
            _migrate_leaf(
                src_md, dst_md,
                old_subject=old_subject, book_slug=book_slug,
                new_subject=new_subject,
                publisher=publisher, authority_rank=authority_rank,
                ingested_at=ingested_at,
            )

    leaf_count = sum(1 for _ in dst_root.rglob("*.md") if _.name != "SKILL.md")
    skill_count = sum(1 for _ in dst_root.rglob("SKILL.md"))
    logger.info(
        "migrated %s/%s → %s (%d leaves, %d SKILL.md)",
        old_subject, book_slug, new_subject, leaf_count, skill_count,
    )
    return dst_root


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--old-subject", default="geography")
    p.add_argument("--book-slug", required=True)
    p.add_argument("--new-subject", required=True)
    p.add_argument(
        "--subject-name", default=None,
        help="Brand-free display name for the subject root (e.g. "
             "'Rajasthan Geography'). Surfaces as the canvas central "
             "node label and the library card title. If omitted, "
             "derives from --new-subject by replacing _/- with spaces "
             "and title-casing. NEVER use the publisher's own book "
             "title here — that re-introduces the brand leak fixed "
             "during the 2026-05-04 QA sweep.",
    )
    p.add_argument("--publisher", required=True)
    p.add_argument(
        "--authority-rank", type=int, required=True,
        help="0=NCERT, 1=RBSE/state, 2=coaching, 3=other",
    )
    p.add_argument(
        "--delete-old", action="store_true",
        help="Remove the old <skills_root>/<old_subject>/<book_slug>/ tree "
             "after a successful migration. Per spec 2026-05-04 we delete "
             "the entire <old_subject>/ when this is the only book in it.",
    )
    p.add_argument(
        "--delete-old-subject", action="store_true",
        help="After migration, also delete the entire old subject folder "
             "(skills_root/<old_subject>/). Use only when migrating the "
             "last book under that subject.",
    )
    return p.parse_args()


def _main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s: %(message)s",
        stream=sys.stdout,
    )
    args = _parse_args()
    book_metadata = {"publisher": args.publisher}

    dst = migrate_book_to_subject(
        old_subject=args.old_subject,
        book_slug=args.book_slug,
        new_subject=args.new_subject,
        publisher=args.publisher,
        authority_rank=args.authority_rank,
        book_metadata=book_metadata,
        subject_name=args.subject_name,
    )
    print(f"\n✓ migrated to {dst}")

    if args.delete_old:
        old_book = _SKILLS_ROOT / args.old_subject / args.book_slug
        if old_book.exists():
            shutil.rmtree(old_book)
            print(f"✓ removed {old_book}")

    if args.delete_old_subject:
        old_subj = _SKILLS_ROOT / args.old_subject
        if old_subj.exists():
            shutil.rmtree(old_subj)
            print(f"✓ removed {old_subj}")

    return 0


if __name__ == "__main__":
    sys.exit(_main())
