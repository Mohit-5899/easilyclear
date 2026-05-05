"""Stage 6.5b — merge a freshly-ingested source INTO an existing subject tree.

Per docs/superpowers/specs/2026-05-04-subject-canonical-tree.md §6.

The companion to ``dedup.py``: dedup *finds* duplicates between a proposed
ingest and an existing tree; merge *applies* the result by writing files.
For each leaf in the proposed (incoming) tree:

    matched = best_match(leaf, existing_subject_tree)  # cosine + optional Gemma judge
    if matched (sim >= auto_threshold OR judge says "duplicate"):
        APPEND new source to that leaf's frontmatter sources[]
        APPEND a new "## Source N (pages X-Y)" section to its body
    else:
        chapter = match_chapter(leaf, existing_chapters)  # slug-similarity (LLM optional)
        if chapter:
            ADD as a new leaf .md under that chapter
        else:
            CREATE a new chapter directory + the leaf inside it

The first-source case is still handled by ``emit.emit_skill_folder`` —
``merge_into_subject_tree`` is only called when the subject directory
already exists on disk.

Public API:
    load_existing_subject(subject_dir) -> ExistingSubject
    append_source_to_leaf(leaf_path, source_id, source_metadata, pages,
                          paragraph_ids, body_text)
    match_chapter_by_slug(title, existing_chapters)
    merge_into_subject_tree(filled, subject_dir, source_metadata,
                            embedder, judge=None, chapter_classifier=None)
                            -> MergeReport
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import frontmatter
from pydantic import BaseModel, Field

from .content_fill import FilledNode, FilledTree
from .dedup import Embedder, LeafLabel, _embed_signature, cosine
from .emit import (
    _build_internal_metadata,
    _build_leaf_metadata,
    _content_hash,
    _dump_frontmatter,
    _format_pages,
    _now_iso,
    _unique_slug,
    _write_md,
    slugify,
)


logger = logging.getLogger(__name__)


# Default cosine threshold above which we treat a pair as a duplicate without
# consulting the judge. Matches dedup.find_duplicates' default; extracted as a
# module-level constant so callers can tune it from one place.
_AUTO_DUPLICATE_THRESHOLD = 0.92


# ---------------------------------------------------------------------------
# Existing-tree introspection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExistingLeaf:
    """A leaf already on disk inside the subject tree."""

    label: LeafLabel
    path: Path           # absolute path to the .md file
    sources: list[dict[str, Any]]  # parsed frontmatter sources[] list
    chapter_dir: Path    # parent directory (the chapter folder)


@dataclass(frozen=True)
class ExistingChapter:
    """A chapter (internal node directory) already on disk."""

    title: str
    slug: str            # the kebab-case slug from the directory name
    path: Path           # absolute path to the chapter directory
    node_id: str


@dataclass(frozen=True)
class ExistingSubject:
    leaves: list[ExistingLeaf]
    chapters: list[ExistingChapter]
    subject_slug: str
    subject_dir: Path


_CHAPTER_DIR_RE = re.compile(r"^(\d{2})-(.+)$")


def _read_md(path: Path) -> tuple[dict[str, Any], str]:
    post = frontmatter.load(path)
    return dict(post.metadata), post.content


def load_existing_subject(subject_dir: Path) -> ExistingSubject:
    """Walk ``subject_dir`` and surface every chapter + leaf already on disk.

    Used by the merge stage to know what shape the canonical tree is in
    before we add a new source. Order: chapter directories sorted by
    their numeric prefix, leaves sorted by file name.
    """
    if not subject_dir.exists():
        raise FileNotFoundError(f"subject directory does not exist: {subject_dir}")

    chapters: list[ExistingChapter] = []
    leaves: list[ExistingLeaf] = []
    subject_slug = subject_dir.name

    chapter_dirs = sorted(
        (p for p in subject_dir.iterdir() if p.is_dir()),
        key=lambda p: p.name,
    )
    for chap_dir in chapter_dirs:
        if not _CHAPTER_DIR_RE.match(chap_dir.name):
            continue
        skill_md = chap_dir / "SKILL.md"
        if not skill_md.exists():
            logger.warning("merge: chapter dir missing SKILL.md: %s", chap_dir)
            continue
        meta, _body = _read_md(skill_md)
        chapters.append(
            ExistingChapter(
                title=str(meta.get("name", chap_dir.name)),
                slug=chap_dir.name.split("-", 1)[1] if "-" in chap_dir.name else chap_dir.name,
                path=chap_dir,
                node_id=str(meta.get("node_id", f"{subject_slug}/{chap_dir.name}")),
            )
        )

        leaf_files = sorted(
            (p for p in chap_dir.iterdir() if p.is_file() and p.suffix == ".md" and p.name != "SKILL.md"),
            key=lambda p: p.name,
        )
        for leaf_path in leaf_files:
            lmeta, lbody = _read_md(leaf_path)
            sources = list(lmeta.get("sources") or [])
            primary_publisher = ""
            primary_book_slug = ""
            if sources:
                primary_publisher = str(sources[0].get("publisher", ""))
                primary_book_slug = str(sources[0].get("book_slug", ""))
            label = LeafLabel(
                book_slug=primary_book_slug,
                node_id=str(lmeta.get("node_id", "")),
                title=str(lmeta.get("name", "")),
                body=lbody,
                publisher=primary_publisher,
            )
            leaves.append(
                ExistingLeaf(
                    label=label, path=leaf_path,
                    sources=sources, chapter_dir=chap_dir,
                )
            )

    return ExistingSubject(
        leaves=leaves, chapters=chapters,
        subject_slug=subject_slug, subject_dir=subject_dir,
    )


# ---------------------------------------------------------------------------
# Append-source-to-existing-leaf
# ---------------------------------------------------------------------------


def append_source_to_leaf(
    leaf_path: Path,
    *,
    source_metadata: dict[str, Any],
    pages: list[int],
    paragraph_ids: list[int],
    source_body: str,
    ingested_at: str | None = None,
) -> int:
    """Append a new source entry to an existing leaf .md file.

    Mutates the file in place: adds the new entry to ``sources[]`` (with
    ``source_id = max(existing) + 1``), appends a new ``## Source N``
    section to the body, and refreshes ``content_hash`` + ``ingested_at``.

    Returns the assigned ``source_id`` so callers can log it.
    """
    meta, body = _read_md(leaf_path)
    sources = list(meta.get("sources") or [])
    next_id = max((int(s.get("source_id", 0)) for s in sources), default=0) + 1
    when = ingested_at or _now_iso()

    new_entry: dict[str, Any] = {
        "source_id": next_id,
        "publisher": source_metadata.get("publisher", "unknown"),
        "book_slug": source_metadata.get("book_slug", ""),
        "pages": list(pages),
        "paragraph_ids": list(paragraph_ids),
        "authority_rank": int(source_metadata.get("authority_rank", 3)),
        "ingested_at": when,
    }
    sources.append(new_entry)

    section = f"\n\n## Source {next_id} ({_format_pages(pages)})\n\n{source_body.strip()}\n"
    new_body = body.rstrip() + section

    meta["sources"] = sources
    meta["content_hash"] = _content_hash(new_body)
    meta["ingested_at"] = when

    leaf_path.write_text(_dump_frontmatter(new_body, meta), encoding="utf-8")
    return next_id


# ---------------------------------------------------------------------------
# Adding new leaves / chapters
# ---------------------------------------------------------------------------


def _next_leaf_position(chapter_dir: Path) -> int:
    """Compute the next two-digit prefix for a new leaf in this chapter."""
    used: list[int] = []
    for p in chapter_dir.iterdir():
        if p.is_file() and p.suffix == ".md" and p.name != "SKILL.md":
            m = re.match(r"^(\d{2})-", p.name)
            if m:
                used.append(int(m.group(1)))
    return (max(used) + 1) if used else 1


def _next_chapter_position(subject_dir: Path) -> int:
    used: list[int] = []
    for p in subject_dir.iterdir():
        if p.is_dir():
            m = _CHAPTER_DIR_RE.match(p.name)
            if m:
                used.append(int(m.group(1)))
    return (max(used) + 1) if used else 1


def add_leaf_to_chapter(
    chapter: ExistingChapter,
    leaf: FilledNode,
    *,
    subject_slug: str,
    source_metadata: dict[str, Any],
    ingested_at: str | None = None,
) -> Path:
    """Emit a single new leaf .md under an existing chapter directory."""
    when = ingested_at or _now_iso()
    used: set[str] = {p.stem.split("-", 1)[1] for p in chapter.path.glob("*.md")
                     if "-" in p.stem and p.name != "SKILL.md"}
    slug = _unique_slug(slugify(leaf.title), used)
    position = _next_leaf_position(chapter.path)
    prefix = f"{position:02d}-{slug}"
    node_id = f"{chapter.node_id}/{prefix}"

    body = (
        f"## Source 1 ({_format_pages(leaf.source_pages)})\n\n"
        f"{leaf.body.strip()}\n"
    )
    metadata = _build_leaf_metadata(
        leaf,
        parent_node_id=chapter.node_id,
        node_id=node_id,
        depth=2,
        position=position,
        wrapped_body=body,
        paragraph_ids=list(leaf.paragraph_refs),
        subject_slug=subject_slug,
        source_metadata=source_metadata,
        ingested_at=when,
    )
    out = chapter.path / f"{prefix}.md"
    _write_md(out, body, metadata)
    return out


def create_new_chapter(
    subject_dir: Path,
    chapter_node: FilledNode,
    *,
    subject_slug: str,
    source_metadata: dict[str, Any],
    ingested_at: str | None = None,
) -> tuple[Path, list[Path]]:
    """Emit a brand-new chapter directory + all its leaves.

    Returns (chapter_dir, [leaf_paths]).
    """
    when = ingested_at or _now_iso()
    used_chapters = {p.name.split("-", 1)[1] for p in subject_dir.iterdir()
                     if p.is_dir() and "-" in p.name}
    slug = _unique_slug(slugify(chapter_node.title), used_chapters)
    position = _next_chapter_position(subject_dir)
    prefix = f"{position:02d}-{slug}"
    chapter_dir = subject_dir / prefix
    chapter_dir.mkdir(parents=True, exist_ok=True)
    node_id = f"{subject_slug}/{prefix}"

    chapter_meta = _build_internal_metadata(
        chapter_node,
        parent_node_id=subject_slug,
        node_id=node_id,
        depth=1,
        position=position,
        subject_slug=subject_slug,
        ingested_at=when,
    )
    _write_md(chapter_dir / "SKILL.md", chapter_node.body, chapter_meta)

    chapter = ExistingChapter(
        title=chapter_node.title, slug=slug,
        path=chapter_dir, node_id=node_id,
    )
    leaf_paths: list[Path] = []
    leaves = chapter_node.children if chapter_node.children else [chapter_node]
    for leaf in leaves:
        if leaf.children:
            # Defer recursive subtrees — V3 trees are flat (chapter → leaf only).
            logger.warning(
                "merge: nested subtree under '%s' flattened to leaves only",
                chapter_node.title,
            )
            for grand in leaf.children:
                leaf_paths.append(
                    add_leaf_to_chapter(
                        chapter, grand,
                        subject_slug=subject_slug,
                        source_metadata=source_metadata,
                        ingested_at=when,
                    )
                )
            continue
        leaf_paths.append(
            add_leaf_to_chapter(
                chapter, leaf,
                subject_slug=subject_slug,
                source_metadata=source_metadata,
                ingested_at=when,
            )
        )

    return chapter_dir, leaf_paths


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _flatten_leaves(node: FilledNode) -> list[FilledNode]:
    """Collect FilledNode leaves in document order."""
    if not node.children:
        return [node]
    out: list[FilledNode] = []
    for child in node.children:
        out.extend(_flatten_leaves(child))
    return out


def _filled_to_label(
    leaf: FilledNode, source_metadata: dict[str, Any]
) -> LeafLabel:
    return LeafLabel(
        book_slug=str(source_metadata.get("book_slug", "")),
        node_id=f"_proposed/{slugify(leaf.title)}",
        title=leaf.title,
        body=leaf.body,
        publisher=str(source_metadata.get("publisher", "")),
    )


def match_chapter_by_slug(
    title: str, chapters: list[ExistingChapter]
) -> ExistingChapter | None:
    """Pick the chapter whose slug shares the most kebab tokens with ``title``.

    Deterministic fallback used when no LLM-backed classifier is supplied.
    Returns None if every chapter scores 0 — caller should then create a new
    chapter rather than force-fit.
    """
    if not chapters:
        return None
    candidate_slug = slugify(title)
    candidate_tokens = set(candidate_slug.split("-"))
    if not candidate_tokens:
        return None

    best: ExistingChapter | None = None
    best_score = 0
    for ch in chapters:
        ch_tokens = set(ch.slug.split("-"))
        score = len(candidate_tokens & ch_tokens)
        if score > best_score:
            best_score = score
            best = ch
    return best if best_score >= 1 else None


class _ChapterClassifier(Protocol):
    def __call__(
        self, leaf: FilledNode, chapters: list[ExistingChapter]
    ) -> ExistingChapter | None: ...


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class _Judge(Protocol):
    def __call__(
        self, new_leaf: LeafLabel, existing_leaf: LeafLabel
    ) -> str: ...


class MergeAction(BaseModel):
    """One leaf decision recorded by ``merge_into_subject_tree``."""

    leaf_title: str
    action: str  # "appended" | "added_leaf" | "added_chapter"
    target_path: str
    similarity: float | None = None
    source_id: int | None = None


class MergeReport(BaseModel):
    appended: int = 0
    added_leaves: int = 0
    added_chapters: int = 0
    actions: list[MergeAction] = Field(default_factory=list)


def merge_into_subject_tree(
    filled: FilledTree,
    subject_dir: Path,
    *,
    source_metadata: dict[str, Any],
    embedder: Embedder,
    judge: Callable[[LeafLabel, LeafLabel], str] | None = None,
    chapter_classifier: _ChapterClassifier | None = None,
    auto_threshold: float = _AUTO_DUPLICATE_THRESHOLD,
    grey_threshold: float = 0.80,
) -> MergeReport:
    """Merge a freshly-ingested ``FilledTree`` into the existing subject tree on disk.

    Args:
        filled: tree from Stage 7 (content-filled).
        subject_dir: existing subject directory (must already exist; raises if not).
        source_metadata: ``{publisher, book_slug, authority_rank}`` for the
            new source. Same shape that ``emit.emit_skill_folder`` consumes.
        embedder: encodes a string to a fixed-length vector. Used to find
            near-duplicate leaves.
        judge: optional LLM-backed callable for the cosine grey zone (0.80-0.92).
            If None, grey-zone leaves are conservatively treated as new.
        chapter_classifier: optional LLM-backed callable to pick a chapter for a
            non-duplicate leaf. If None or it returns None, falls back to
            ``match_chapter_by_slug``. If neither finds a chapter, a new
            chapter is created.
        auto_threshold: cosine ≥ this auto-marks as duplicate (default 0.92).
        grey_threshold: cosine ≥ this enters the judge zone (default 0.80).

    Returns:
        MergeReport with per-leaf actions and counts.
    """
    existing = load_existing_subject(subject_dir)
    subject_slug = existing.subject_slug
    when = _now_iso()

    # Pre-compute embeddings for existing leaves once.
    existing_vecs: dict[str, list[float]] = {}
    for el in existing.leaves:
        existing_vecs[el.label.node_id] = embedder.encode(_embed_signature(el.label))

    proposed_leaves = _flatten_leaves(filled.root)
    report = MergeReport()

    for new_leaf in proposed_leaves:
        new_label = _filled_to_label(new_leaf, source_metadata)
        new_vec = embedder.encode(_embed_signature(new_label))

        best_match: ExistingLeaf | None = None
        best_sim = 0.0
        for el in existing.leaves:
            sim = cosine(new_vec, existing_vecs[el.label.node_id])
            if sim > best_sim:
                best_sim = sim
                best_match = el

        is_duplicate = False
        if best_match is not None:
            if best_sim >= auto_threshold:
                is_duplicate = True
            elif best_sim >= grey_threshold and judge is not None:
                verdict = judge(new_label, best_match.label)
                is_duplicate = verdict == "duplicate"

        if is_duplicate and best_match is not None:
            sid = append_source_to_leaf(
                best_match.path,
                source_metadata=source_metadata,
                pages=list(new_leaf.source_pages),
                paragraph_ids=list(new_leaf.paragraph_refs),
                source_body=new_leaf.body,
                ingested_at=when,
            )
            report.appended += 1
            report.actions.append(MergeAction(
                leaf_title=new_leaf.title, action="appended",
                target_path=str(best_match.path), similarity=best_sim,
                source_id=sid,
            ))
            continue

        # Not a duplicate — find a chapter to host this new leaf.
        chapter: ExistingChapter | None = None
        if chapter_classifier is not None:
            chapter = chapter_classifier(new_leaf, existing.chapters)
        if chapter is None:
            chapter = match_chapter_by_slug(new_leaf.title, existing.chapters)

        if chapter is not None:
            out = add_leaf_to_chapter(
                chapter, new_leaf,
                subject_slug=subject_slug,
                source_metadata=source_metadata,
                ingested_at=when,
            )
            report.added_leaves += 1
            report.actions.append(MergeAction(
                leaf_title=new_leaf.title, action="added_leaf",
                target_path=str(out), similarity=best_sim or None,
            ))
            continue

        # Fall through: create a brand-new chapter housing just this leaf.
        chap_dir, leaf_paths = create_new_chapter(
            existing.subject_dir, new_leaf,
            subject_slug=subject_slug,
            source_metadata=source_metadata,
            ingested_at=when,
        )
        report.added_chapters += 1
        report.actions.append(MergeAction(
            leaf_title=new_leaf.title, action="added_chapter",
            target_path=str(chap_dir),
        ))
        # Refresh local view so subsequent leaves can target this chapter.
        existing = load_existing_subject(subject_dir)

    return report
