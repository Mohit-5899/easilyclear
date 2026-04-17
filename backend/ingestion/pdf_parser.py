"""PDF text extraction using PyMuPDF.

Extracts per-page text from English-language PDFs (NCERT, Rajasthan Board).
Output feeds the content-cleaning layer and then the PageIndex tree builder.

Page numbers are 1-indexed (1..N) to match PageIndex's start_index/end_index
convention and NCERT's physical page numbers.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
from pydantic import BaseModel, Field


class PdfParseError(Exception):
    """Raised when a PDF cannot be opened or parsed."""


class PageText(BaseModel):
    """Extracted text for a single PDF page."""

    page_num: int = Field(ge=1, description="1-indexed physical page number")
    text: str
    char_count: int = Field(ge=0)


class PdfExtractionResult(BaseModel):
    """Result of extracting text from a full PDF document."""

    source_path: str
    page_count: int = Field(ge=0)
    total_chars: int = Field(ge=0)
    pages: list[PageText]


def _build_page_text(page_num: int, text: str) -> PageText:
    return PageText(page_num=page_num, text=text, char_count=len(text))


def extract_pages(pdf_path: Path) -> PdfExtractionResult:
    """Extract per-page text from a PDF at ``pdf_path``.

    Args:
        pdf_path: Absolute or relative ``pathlib.Path`` to the PDF file.

    Returns:
        A ``PdfExtractionResult`` with one ``PageText`` per physical page,
        1-indexed.

    Raises:
        PdfParseError: If the file is missing, cannot be opened, or is not a
            valid PDF.
    """
    if not isinstance(pdf_path, Path):
        raise TypeError(
            f"extract_pages requires a pathlib.Path, got {type(pdf_path).__name__}"
        )

    if not pdf_path.exists():
        raise PdfParseError(f"PDF file not found: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
    except (fitz.FileDataError, RuntimeError) as exc:
        raise PdfParseError(f"Failed to open PDF at {pdf_path}: {exc}") from exc

    try:
        pages: list[PageText] = []
        for index, page in enumerate(doc, start=1):
            text = page.get_text()
            pages.append(_build_page_text(page_num=index, text=text))
    except Exception as exc:  # pragma: no cover - defensive against fitz bugs
        raise PdfParseError(
            f"Failed to extract text from PDF at {pdf_path}: {exc}"
        ) from exc
    finally:
        doc.close()

    return PdfExtractionResult(
        source_path=str(pdf_path),
        page_count=len(pages),
        total_chars=sum(p.char_count for p in pages),
        pages=pages,
    )
