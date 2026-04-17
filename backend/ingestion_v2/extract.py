"""Stage 1 of the V2 pipeline — paragraph-level PDF extraction.

Uses PyMuPDF's block-level layout extraction so each paragraph is a natural
text unit (not a whole page). Also pulls the PDF's table of contents, which
Stage 2 uses when available to seed a chapter-level pre-structure for Gemma.

Paragraph IDs are 0-indexed global sequence numbers. Page numbers are
1-indexed to match PDF conventions.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
from pydantic import BaseModel, Field


# Minimum paragraph length (chars) — filters out page numbers, headers,
# figure captions that are too short to carry semantic content.
_MIN_PARAGRAPH_CHARS = 20


class PdfExtractionError(Exception):
    """Raised when a PDF cannot be opened, parsed, or is unreadable."""


class Paragraph(BaseModel):
    """A single paragraph extracted from the PDF."""

    paragraph_id: int = Field(ge=0, description="0-indexed sequential paragraph ID")
    page: int = Field(ge=1, description="1-indexed source page number")
    text: str


class Bookmark(BaseModel):
    """A PDF table-of-contents entry."""

    level: int = Field(ge=1, description="1 = top-level chapter, 2 = section, ...")
    title: str
    page: int = Field(ge=1, description="1-indexed target page")


class ExtractedDoc(BaseModel):
    """Full extraction result for one PDF."""

    paragraphs: list[Paragraph]
    bookmarks: list[Bookmark]
    page_count: int = Field(ge=0)


def _extract_page_paragraphs(
    page: fitz.Page,
    page_num: int,
    next_paragraph_id: int,
) -> tuple[list[Paragraph], int]:
    """Extract paragraph-sized text blocks from a single PDF page.

    PyMuPDF's ``get_text("blocks")`` returns layout-aware blocks in roughly
    reading order. Each block's text is treated as a candidate paragraph,
    which we then filter for minimum length.
    """
    blocks = page.get_text("blocks")
    paragraphs: list[Paragraph] = []
    current_id = next_paragraph_id

    for block in blocks:
        # Each block is a tuple: (x0, y0, x1, y1, text, block_no, block_type).
        # block_type == 0 is a text block; ignore image/other blocks.
        if len(block) < 7:
            continue
        block_type = block[6]
        if block_type != 0:
            continue

        raw_text = block[4] if isinstance(block[4], str) else ""
        # Collapse internal whitespace runs while preserving single newlines
        # (often meaningful in PDFs for list items).
        cleaned = " ".join(raw_text.split())
        if len(cleaned) < _MIN_PARAGRAPH_CHARS:
            continue

        paragraphs.append(
            Paragraph(paragraph_id=current_id, page=page_num, text=cleaned)
        )
        current_id += 1

    return paragraphs, current_id


def _extract_bookmarks(doc: fitz.Document) -> list[Bookmark]:
    """Pull the PDF's outline (TOC). Returns empty list if none present."""
    try:
        toc = doc.get_toc()
    except Exception:
        return []

    bookmarks: list[Bookmark] = []
    for entry in toc:
        if not isinstance(entry, (list, tuple)) or len(entry) < 3:
            continue
        level, title, page = entry[0], entry[1], entry[2]
        if not isinstance(level, int) or level < 1:
            continue
        if not isinstance(page, int) or page < 1:
            continue
        title_str = str(title).strip() if title is not None else ""
        if not title_str:
            continue
        bookmarks.append(Bookmark(level=level, title=title_str, page=page))
    return bookmarks


def extract_document(pdf_path: Path) -> ExtractedDoc:
    """Extract paragraphs + bookmarks from a PDF.

    Args:
        pdf_path: Absolute path to a PDF file.

    Returns:
        ExtractedDoc with paragraph-level content and any available bookmarks.

    Raises:
        PdfExtractionError: If the file can't be opened or parsed.
    """
    if not isinstance(pdf_path, Path):
        raise TypeError(
            f"extract_document requires a pathlib.Path, got {type(pdf_path).__name__}"
        )
    if not pdf_path.exists():
        raise PdfExtractionError(f"PDF file not found: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
    except (fitz.FileDataError, RuntimeError) as exc:
        raise PdfExtractionError(f"Failed to open PDF at {pdf_path}: {exc}") from exc

    try:
        paragraphs: list[Paragraph] = []
        next_id = 0
        for page_index, page in enumerate(doc, start=1):
            page_paragraphs, next_id = _extract_page_paragraphs(
                page=page, page_num=page_index, next_paragraph_id=next_id
            )
            paragraphs.extend(page_paragraphs)
        bookmarks = _extract_bookmarks(doc)
        page_count = doc.page_count
    finally:
        doc.close()

    return ExtractedDoc(
        paragraphs=paragraphs,
        bookmarks=bookmarks,
        page_count=page_count,
    )
