"""Stage 1 of the V2 pipeline — paragraph-level extraction.

Accepts either a ``.pdf`` file (PyMuPDF-backed) or a ``.txt`` file (the
pre-extracted text some users produce out-of-band). In both cases we apply
branding cleanup (see :mod:`text_cleanup`) **before** paragraph splitting so
multi-line headers/footers are caught whole.

Paragraph IDs are 0-indexed global sequence numbers. Page numbers are
1-indexed to match PDF conventions. ``.txt`` input has no page information;
every paragraph is tagged as page 1.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from pathlib import Path

import fitz  # PyMuPDF
from pydantic import BaseModel, Field

from .ocr import merge_ocr_with_native, ocr_page
from .text_cleanup import CleanupPattern, CleanupReport, clean_text


logger = logging.getLogger(__name__)


# Minimum paragraph length (chars) — filters page numbers, figure captions.
_MIN_PARAGRAPH_CHARS = 20

# Paragraph boundary: one-or-more blank lines.
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")


class ExtractionError(Exception):
    """Raised when a source file cannot be opened, parsed, or is unreadable."""


# Back-compat alias (V2 callers imported this name in earlier tasks).
PdfExtractionError = ExtractionError


class Paragraph(BaseModel):
    paragraph_id: int = Field(ge=0, description="0-indexed sequential paragraph ID")
    page: int = Field(ge=1, description="1-indexed source page number")
    text: str


class Bookmark(BaseModel):
    level: int = Field(ge=1, description="1 = top-level chapter, 2 = section, ...")
    title: str
    page: int = Field(ge=1, description="1-indexed target page")


class ExtractedDoc(BaseModel):
    paragraphs: list[Paragraph]
    bookmarks: list[Bookmark]
    page_count: int = Field(ge=0)
    cleanup_report: CleanupReport | None = None

    model_config = {"arbitrary_types_allowed": True}


def _normalize_paragraph_text(raw: str) -> str:
    """Collapse whitespace runs; preserve leading/trailing stripped form."""
    return " ".join(raw.split()).strip()


def _split_paragraphs(
    page_text: str, *, page_num: int, next_id: int
) -> tuple[list[Paragraph], int]:
    """Split cleaned text into paragraphs (blank-line boundaries).

    Returns ``(paragraphs, next_id_after)``.
    """
    paragraphs: list[Paragraph] = []
    current_id = next_id
    for chunk in _PARAGRAPH_SPLIT.split(page_text):
        cleaned = _normalize_paragraph_text(chunk)
        if len(cleaned) < _MIN_PARAGRAPH_CHARS:
            continue
        paragraphs.append(
            Paragraph(paragraph_id=current_id, page=page_num, text=cleaned)
        )
        current_id += 1
    return paragraphs, current_id


def _extract_bookmarks(doc: fitz.Document) -> list[Bookmark]:
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


def _extract_pdf(
    pdf_path: Path,
    source_patterns: list[CleanupPattern],
    *,
    use_ocr: bool = True,
) -> ExtractedDoc:
    try:
        doc = fitz.open(pdf_path)
    except (fitz.FileDataError, RuntimeError) as exc:
        raise ExtractionError(f"Failed to open PDF at {pdf_path}: {exc}") from exc

    try:
        paragraphs: list[Paragraph] = []
        next_id = 0
        aggregated_counts: dict[str, int] = {}
        aggregated_samples: dict[str, list[str]] = {}
        ocr_chars_recovered = 0

        for page_index, page in enumerate(doc, start=1):
            native = page.get_text("text") or ""
            # Stage 1.5 — page-level OCR. Recovers map labels, table cells,
            # section headers rendered as raster images. Merge BEFORE the
            # branding cleanup so OCR-introduced "SPRINGBOARD ACADEMY"
            # banners get stripped by the same regex pipeline.
            if use_ocr:
                try:
                    ocr_raw = ocr_page(page)
                    merged = merge_ocr_with_native(native, ocr_raw)
                    ocr_chars_recovered += max(0, len(merged) - len(native))
                    raw = merged
                except (OSError, RuntimeError) as exc:  # pragma: no cover - tesseract failure
                    logger.warning(
                        "extract: OCR failed on page %d (%s: %s); using native text only",
                        page_index, type(exc).__name__, exc,
                    )
                    raw = native
            else:
                raw = native
            if not raw or not raw.strip():
                continue
            report = clean_text(raw, source_patterns=source_patterns)
            for label, n in report.removals_by_category.items():
                aggregated_counts[label] = aggregated_counts.get(label, 0) + n
            for label, samples in report.sample_matches.items():
                existing = aggregated_samples.setdefault(label, [])
                for s in samples:
                    if len(existing) >= 5:
                        break
                    existing.append(s)
            page_paragraphs, next_id = _split_paragraphs(
                report.cleaned_text, page_num=page_index, next_id=next_id
            )
            paragraphs.extend(page_paragraphs)

        bookmarks = _extract_bookmarks(doc)
        page_count = doc.page_count
    finally:
        doc.close()

    if use_ocr:
        logger.info(
            "extract: OCR added %d chars across %d pages",
            ocr_chars_recovered, page_count,
        )

    combined_report = CleanupReport(
        cleaned_text="",
        removals_by_category=aggregated_counts,
        sample_matches=aggregated_samples,
    )
    return ExtractedDoc(
        paragraphs=paragraphs,
        bookmarks=bookmarks,
        page_count=page_count,
        cleanup_report=combined_report,
    )


def _extract_txt(
    txt_path: Path, source_patterns: list[CleanupPattern]
) -> ExtractedDoc:
    try:
        raw = txt_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ExtractionError(f"Failed to read text file at {txt_path}: {exc}") from exc

    report = clean_text(raw, source_patterns=source_patterns)
    paragraphs, _ = _split_paragraphs(
        report.cleaned_text, page_num=1, next_id=0
    )

    # .txt input has no page count from the source; use 1 if we produced
    # any content, else 0.
    page_count = 1 if paragraphs else 0

    return ExtractedDoc(
        paragraphs=paragraphs,
        bookmarks=[],
        page_count=page_count,
        cleanup_report=report,
    )


def extract_document(
    source_path: Path,
    *,
    source_patterns: Iterable[CleanupPattern] = (),
    use_ocr: bool = True,
) -> ExtractedDoc:
    """Extract paragraphs (+ bookmarks for PDF) from a .pdf or .txt file.

    Args:
        source_path: Absolute path to a ``.pdf`` or ``.txt`` file.
        source_patterns: Optional source-specific branding patterns applied
            in addition to :data:`GENERIC_PATTERNS`. See
            :mod:`ingestion_v2.text_cleanup`.

    Returns:
        ExtractedDoc with paragraph-level content, any available bookmarks,
        and a cleanup report summarizing what was stripped.

    Raises:
        ExtractionError: If the file can't be opened or parsed.
        TypeError: If ``source_path`` isn't a pathlib.Path.
    """
    if not isinstance(source_path, Path):
        raise TypeError(
            f"extract_document requires a pathlib.Path, got {type(source_path).__name__}"
        )
    if not source_path.exists():
        raise ExtractionError(f"Source file not found: {source_path}")

    patterns_list = list(source_patterns)
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        result = _extract_pdf(source_path, patterns_list, use_ocr=use_ocr)
    elif suffix == ".txt":
        result = _extract_txt(source_path, patterns_list)
    else:
        raise ExtractionError(
            f"Unsupported source type '{suffix}' (expected .pdf or .txt)"
        )

    if result.cleanup_report:
        total_removed = sum(result.cleanup_report.removals_by_category.values())
        if total_removed:
            logger.info(
                "extract: cleanup removed %d fragments across %d categories: %s",
                total_removed,
                len(result.cleanup_report.removals_by_category),
                result.cleanup_report.removals_by_category,
            )
    return result
