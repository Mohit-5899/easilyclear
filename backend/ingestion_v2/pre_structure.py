"""Stage 2 of the V2 pipeline — pre-structure.

MVP scope (per plan): if the PDF has bookmarks (a TOC), split paragraphs by
bookmark level-1 page boundaries into candidate chapters. Else: emit a
single chapter containing all paragraphs and let the Proposer LLM discover
structure from scratch.

Full design uses sentence embeddings + HDBSCAN clustering; that's deferred
to V2.1.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .extract import Bookmark, ExtractedDoc


class CandidateChapter(BaseModel):
    """A seed chapter surfaced from PDF bookmarks (or the whole-document
    fallback). The Proposer can respect or override these boundaries."""

    title: str | None = Field(
        default=None,
        description="Bookmark title if available; None for unstructured fallback.",
    )
    paragraph_ids: list[int]
    page_range: tuple[int, int] = Field(
        description="(first_page, last_page) inclusive, 1-indexed."
    )


class DraftHierarchy(BaseModel):
    """Output of pre-structure. Used by the Proposer as a seed hint."""

    candidate_chapters: list[CandidateChapter]
    has_bookmark_structure: bool


def _level_one_bookmarks(bookmarks: list[Bookmark]) -> list[Bookmark]:
    """Filter bookmarks down to the top level, preserving order."""
    return [b for b in bookmarks if b.level == 1]


def _paragraphs_in_page_range(
    doc: ExtractedDoc, first_page: int, last_page: int
) -> list[int]:
    """Collect paragraph IDs whose source page is in [first_page, last_page]."""
    return [
        p.paragraph_id
        for p in doc.paragraphs
        if first_page <= p.page <= last_page
    ]


def _single_chapter_fallback(doc: ExtractedDoc) -> DraftHierarchy:
    """No bookmarks → emit one chapter spanning the whole doc."""
    if not doc.paragraphs:
        return DraftHierarchy(
            candidate_chapters=[], has_bookmark_structure=False
        )
    first_page = min(p.page for p in doc.paragraphs)
    last_page = max(p.page for p in doc.paragraphs)
    chapter = CandidateChapter(
        title=None,
        paragraph_ids=[p.paragraph_id for p in doc.paragraphs],
        page_range=(first_page, last_page),
    )
    return DraftHierarchy(
        candidate_chapters=[chapter], has_bookmark_structure=False
    )


def build_draft(doc: ExtractedDoc) -> DraftHierarchy:
    """Build a chapter-level draft hierarchy from the extracted document.

    Uses PDF bookmarks (level-1 entries) as chapter boundaries when present;
    otherwise returns a single-chapter fallback.
    """
    top_bookmarks = _level_one_bookmarks(doc.bookmarks)
    if not top_bookmarks:
        return _single_chapter_fallback(doc)

    # Ensure bookmarks are in page order — PyMuPDF usually returns them this
    # way but don't assume it.
    top_bookmarks = sorted(top_bookmarks, key=lambda b: b.page)

    total_pages = doc.page_count or (
        max((p.page for p in doc.paragraphs), default=0)
    )
    if total_pages == 0:
        return _single_chapter_fallback(doc)

    chapters: list[CandidateChapter] = []
    for idx, bookmark in enumerate(top_bookmarks):
        first_page = bookmark.page
        last_page = (
            top_bookmarks[idx + 1].page - 1
            if idx + 1 < len(top_bookmarks)
            else total_pages
        )
        if last_page < first_page:
            last_page = first_page
        paragraph_ids = _paragraphs_in_page_range(doc, first_page, last_page)
        # Skip empty chapters (bookmark pointed at a page we extracted
        # nothing from — e.g., cover images).
        if not paragraph_ids:
            continue
        chapters.append(
            CandidateChapter(
                title=bookmark.title,
                paragraph_ids=paragraph_ids,
                page_range=(first_page, last_page),
            )
        )

    if not chapters:
        return _single_chapter_fallback(doc)

    return DraftHierarchy(
        candidate_chapters=chapters, has_bookmark_structure=True
    )
