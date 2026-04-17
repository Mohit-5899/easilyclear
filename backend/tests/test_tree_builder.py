"""Tests for ingestion.tree_builder and ingestion.pdf_downloader.

The smoke tests generate tiny PDFs in-memory with PyMuPDF and inject
``MockLLMClient`` so nothing touches the network or OpenRouter.

The MockLLMClient is an echo stub — it cannot return the JSON shapes
PageIndex expects, so the true end-to-end run (full PageIndex call with a
mock client) does not produce a usable tree. The tests instead:

* unit-test ``_merge_pdfs`` directly,
* verify whitelist rejection short-circuits before any download,
* monkey-patch ``_run_pageindex`` to simulate a PageIndex result and
  exercise the full orchestration + provenance wrapping,
* unit-test the database-dir auto-discovery path.
"""

from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from ingestion import tree_builder
from ingestion.pdf_downloader import _merge_pdfs
from ingestion.source_whitelist import SourceNotAllowedError
from ingestion.tree_builder import (
    TreeBuildResult,
    _find_default_database_dir,
    ingest_pdf,
)
from llm.mock import MockLLMClient


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_synthetic_pdf(
    path: Path, pages_content: list[str]
) -> Path:
    """Create a minimal PDF with one page per string at ``path``."""
    doc = fitz.open()
    for content in pages_content:
        page = doc.new_page()
        page.insert_text((50, 72), content, fontsize=11)
    doc.save(path)
    doc.close()
    return path


def _make_geography_pdf(tmp_path: Path) -> Path:
    pages = [
        "Chapter 1: Resources and Development\n\n"
        "This chapter introduces the concept of resources.\n"
        "Resources can be classified into renewable and non-renewable.",
        "Chapter 2: Water Resources\n\n"
        "India has abundant water resources from rivers, lakes, and groundwater.\n"
        "The major rivers include the Ganga, Yamuna, and Brahmaputra.",
        "Chapter 3: Agriculture\n\n"
        "Agriculture is the primary occupation in rural India.\n"
        "Major crops include rice, wheat, and cotton.",
    ]
    return _make_synthetic_pdf(tmp_path / "synthetic_geography.pdf", pages)


# ---------------------------------------------------------------------------
# Test 1 — whitelist rejects non-official sources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_whitelist_rejects_non_official_source(tmp_path: Path) -> None:
    """A banned domain must raise SourceNotAllowedError before any download."""
    download_attempted = False

    async def _fail_download(*args, **kwargs):
        nonlocal download_attempted
        download_attempted = True
        raise AssertionError("download should not be called for rejected URL")

    original = tree_builder.download_pdf
    tree_builder.download_pdf = _fail_download  # type: ignore[assignment]
    try:
        with pytest.raises(SourceNotAllowedError):
            await ingest_pdf(
                source_url="https://vedantu.com/fake.pdf",
                book_slug="banned_book",
                doc_name="Banned",
                database_dir=tmp_path / "db",
                tmp_dir=tmp_path / "tmp",
                llm_client=MockLLMClient(),
            )
    finally:
        tree_builder.download_pdf = original  # type: ignore[assignment]

    assert download_attempted is False


# ---------------------------------------------------------------------------
# Test 2 — _merge_pdfs combines pages
# ---------------------------------------------------------------------------


def test_merge_pdfs_combines_pages(tmp_path: Path) -> None:
    """Two chapter PDFs merge into one with combined page count + text."""
    chap1 = _make_synthetic_pdf(
        tmp_path / "chap1.pdf",
        ["Chapter 1 page A", "Chapter 1 page B"],
    )
    chap2 = _make_synthetic_pdf(
        tmp_path / "chap2.pdf",
        ["Chapter 2 page A", "Chapter 2 page B", "Chapter 2 page C"],
    )

    merged = _merge_pdfs([chap1, chap2], tmp_path / "merged.pdf")

    assert merged.exists()
    with fitz.open(merged) as doc:
        assert doc.page_count == 5
        texts = [doc.load_page(i).get_text() for i in range(doc.page_count)]
    combined = "\n".join(texts)
    assert "Chapter 1 page A" in combined
    assert "Chapter 2 page C" in combined


# ---------------------------------------------------------------------------
# Test 3 — orchestration up to (but not including) the real PageIndex run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingestion_steps_before_pageindex_run_cleanly(
    tmp_path: Path,
) -> None:
    """Whitelist + download stub + extract + clean + cleaned-PDF rewrite all
    run without error; the stubbed PageIndex receives a valid cleaned PDF path.
    """
    synthetic = _make_geography_pdf(tmp_path)

    async def _stub_download(url, dest_dir):
        from ingestion.pdf_downloader import DownloadResult

        dest_dir.mkdir(parents=True, exist_ok=True)
        return DownloadResult(
            source_url=url,
            merged_pdf_path=synthetic.resolve(),
            chapter_paths=[],
            total_bytes=synthetic.stat().st_size,
            total_pages=3,
        )

    seen_paths: list[Path] = []

    async def _stub_pageindex(cleaned_pdf_path: Path):
        seen_paths.append(cleaned_pdf_path)
        assert cleaned_pdf_path.exists()
        # Verify the cleaned PDF still has 3 pages (1:1 with the source).
        with fitz.open(cleaned_pdf_path) as d:
            assert d.page_count == 3
        return {
            "doc_name": "synthetic_geography",
            "doc_description": "A synthetic smoke test document",
            "structure": [
                {
                    "title": "Resources",
                    "node_id": "0001",
                    "start_index": 1,
                    "end_index": 1,
                    "summary": "intro",
                    "nodes": [
                        {
                            "title": "Renewable",
                            "node_id": "0002",
                            "start_index": 1,
                            "end_index": 1,
                            "summary": "sub",
                            "nodes": [],
                        }
                    ],
                },
                {
                    "title": "Water",
                    "node_id": "0003",
                    "start_index": 2,
                    "end_index": 2,
                    "summary": "rivers",
                    "nodes": [],
                },
            ],
        }

    original_download = tree_builder.download_pdf
    original_run = tree_builder._run_pageindex
    tree_builder.download_pdf = _stub_download  # type: ignore[assignment]
    tree_builder._run_pageindex = _stub_pageindex  # type: ignore[assignment]

    try:
        result = await ingest_pdf(
            source_url="https://ncert.nic.in/textbook/pdf/test.pdf",
            book_slug="synthetic_geography_test",
            doc_name="Synthetic Geography Test",
            database_dir=tmp_path / "db",
            tmp_dir=tmp_path / "tmp",
            llm_client=MockLLMClient(),
            run_llm_cleaner=False,
        )
    finally:
        tree_builder.download_pdf = original_download  # type: ignore[assignment]
        tree_builder._run_pageindex = original_run  # type: ignore[assignment]

    assert isinstance(result, TreeBuildResult)
    assert result.book_slug == "synthetic_geography_test"
    assert result.page_count == 3
    assert result.node_count == 3  # 2 top-level + 1 nested
    assert result.suspicious_pages == 0  # clean synthetic text
    assert result.total_llm_calls == 0
    assert result.json_path.exists()
    assert result.json_path.is_absolute()
    assert len(seen_paths) == 1


# ---------------------------------------------------------------------------
# Test 4 — provenance wrapping produces the §10.3 schema
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provenance_wrapping_matches_schema(tmp_path: Path) -> None:
    """End-to-end JSON payload carries every provenance field from §10.3."""
    synthetic = _make_geography_pdf(tmp_path)

    async def _stub_download(url, dest_dir):
        from ingestion.pdf_downloader import DownloadResult

        dest_dir.mkdir(parents=True, exist_ok=True)
        return DownloadResult(
            source_url=url,
            merged_pdf_path=synthetic.resolve(),
            chapter_paths=[],
            total_bytes=synthetic.stat().st_size,
            total_pages=3,
        )

    async def _stub_pageindex(_cleaned_pdf_path: Path):
        return {
            "doc_name": "NCERT Class 10 Test",
            "doc_description": "desc",
            "structure": [
                {
                    "title": "Top",
                    "node_id": "0001",
                    "start_index": 1,
                    "end_index": 3,
                    "summary": "s",
                    "nodes": [],
                }
            ],
        }

    original_download = tree_builder.download_pdf
    original_run = tree_builder._run_pageindex
    tree_builder.download_pdf = _stub_download  # type: ignore[assignment]
    tree_builder._run_pageindex = _stub_pageindex  # type: ignore[assignment]

    try:
        result = await ingest_pdf(
            source_url="https://ncert.nic.in/textbook/pdf/jess1dd.zip",
            book_slug="ncert_class10_contemporary_india_2_test",
            doc_name="Contemporary India II (NCERT Class 10 Geography)",
            subject="geography",
            subject_scope="pan_india",
            exam_coverage=["patwari", "reet", "ras_pre"],
            database_dir=tmp_path / "db",
            tmp_dir=tmp_path / "tmp",
            llm_client=MockLLMClient(),
            run_llm_cleaner=False,
        )
    finally:
        tree_builder.download_pdf = original_download  # type: ignore[assignment]
        tree_builder._run_pageindex = original_run  # type: ignore[assignment]

    with result.json_path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)

    # §10.3 schema — every provenance field must be present.
    assert payload["doc_name"] == "Contemporary India II (NCERT Class 10 Geography)"
    assert payload["book_slug"] == "ncert_class10_contemporary_india_2_test"
    assert payload["doc_description"] == "desc"
    assert payload["source_url"] == "https://ncert.nic.in/textbook/pdf/jess1dd.zip"
    assert payload["source_authority"] == "official"
    assert payload["source_publisher"] == "NCERT"
    assert payload["language"] == "en"
    assert payload["subject"] == "geography"
    assert payload["subject_scope"] == "pan_india"
    assert payload["exam_coverage"] == ["patwari", "reet", "ras_pre"]
    assert payload["cleanup_version"] == "v1"
    assert payload["cleaner_layers_applied"] == ["whitelist", "regex"]
    assert payload["pageindex_version"] == "vendored-f2dcffc0"
    assert payload["llm_model_indexing"]  # truthy, from settings
    assert isinstance(payload["structure"], list)
    assert payload["ingested_at"].endswith("+00:00")
    assert payload["cleaned_at"].endswith("+00:00")


# ---------------------------------------------------------------------------
# Test 5 — database_dir auto-discovery
# ---------------------------------------------------------------------------


def test_default_database_dir_auto_discovery() -> None:
    """Without an explicit database_dir, _find_default_database_dir resolves
    to the repo's database/textbooks/ directory."""
    discovered = _find_default_database_dir()
    assert discovered.is_dir()
    assert discovered.name == "textbooks"
    assert discovered.parent.name == "database"
