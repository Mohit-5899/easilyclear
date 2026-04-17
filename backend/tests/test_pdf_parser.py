"""Tests for ingestion.pdf_parser.

Test PDFs are generated in-memory via PyMuPDF inside each test so we do not
depend on any external fixture files.
"""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest
from pydantic import BaseModel

from ingestion.pdf_parser import (
    PageText,
    PdfExtractionResult,
    PdfParseError,
    extract_pages,
)


def _make_test_pdf(tmp_path: Path, pages_content: list[str]) -> Path:
    """Create a minimal PDF with one page per string in ``pages_content``."""
    doc = fitz.open()
    for content in pages_content:
        page = doc.new_page()
        page.insert_text((50, 72), content, fontsize=11)
    pdf_path = tmp_path / "test.pdf"
    doc.save(pdf_path)
    doc.close()
    return pdf_path


def test_extract_pages_returns_correct_count(tmp_path: Path) -> None:
    """A 3-page PDF yields page_count == 3 and len(pages) == 3."""
    pdf_path = _make_test_pdf(tmp_path, ["Page one", "Page two", "Page three"])

    result = extract_pages(pdf_path)

    assert result.page_count == 3
    assert len(result.pages) == 3


def test_page_numbers_are_1_indexed(tmp_path: Path) -> None:
    """First page has page_num == 1, last page has page_num == N."""
    pdf_path = _make_test_pdf(tmp_path, ["A", "B", "C", "D"])

    result = extract_pages(pdf_path)

    assert result.pages[0].page_num == 1
    assert result.pages[-1].page_num == 4
    assert [p.page_num for p in result.pages] == [1, 2, 3, 4]


def test_text_content_preserved(tmp_path: Path) -> None:
    """Inserted text appears in the extracted output (substring match)."""
    marker = "Geography of Rajasthan"
    pdf_path = _make_test_pdf(tmp_path, [marker])

    result = extract_pages(pdf_path)

    assert marker in result.pages[0].text


def test_char_count_matches_text_length(tmp_path: Path) -> None:
    """PageText.char_count equals len(PageText.text)."""
    pdf_path = _make_test_pdf(tmp_path, ["Hello world"])

    result = extract_pages(pdf_path)

    assert result.pages[0].char_count == len(result.pages[0].text)


def test_total_chars_sums_pages(tmp_path: Path) -> None:
    """total_chars equals the sum of per-page char_count values."""
    pdf_path = _make_test_pdf(tmp_path, ["alpha", "beta", "gamma"])

    result = extract_pages(pdf_path)

    assert result.total_chars == sum(p.char_count for p in result.pages)


def test_missing_file_raises_pdf_parse_error(tmp_path: Path) -> None:
    """A nonexistent path raises PdfParseError, not FileNotFoundError."""
    missing = tmp_path / "does_not_exist.pdf"

    with pytest.raises(PdfParseError) as excinfo:
        extract_pages(missing)

    assert str(missing) in str(excinfo.value)


def test_pdf_extraction_result_is_pydantic_model(tmp_path: Path) -> None:
    """Result is a Pydantic BaseModel (not a dataclass) and serializes."""
    pdf_path = _make_test_pdf(tmp_path, ["one"])

    result = extract_pages(pdf_path)

    assert isinstance(result, BaseModel)
    assert isinstance(result.pages[0], PageText)
    dumped = result.model_dump()
    assert dumped["page_count"] == 1
    assert "pages" in dumped
    assert isinstance(PdfExtractionResult.model_json_schema(), dict)
