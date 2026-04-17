"""End-to-end ingestion orchestrator — whitelist → download → parse → clean →
PageIndex → provenance JSON.

Produces a ``<book_slug>.json`` file in ``database/textbooks/`` matching the
schema documented in ARCHITECTURE.md §10.3. All intermediate steps flow
through Pydantic models; no dicts until the final JSON dump.

High-level flow (see §10.2):

    validate_source -> download_pdf -> extract_pages
        -> regex_clean [+ optional llm_clean]
        -> write cleaned PDF -> page_index -> wrap with provenance -> JSON.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import fitz  # PyMuPDF
from pydantic import BaseModel

from config import Settings, get_settings
from ingestion.pdf_downloader import DownloadResult, download_pdf
from ingestion.pdf_parser import PageText, extract_pages
from ingestion.source_whitelist import AllowedSource, validate_source
from ingestion.text_cleaner import llm_clean, regex_clean
from llm.base import LLMClient
from llm.factory import get_llm_client
from vendor import pageindex as vendored_pageindex

_PAGEINDEX_VERSION = "vendored-f2dcffc0"
_CLEANUP_VERSION = "v1"
_DEFAULT_TMP_ROOT = Path("/tmp/gemma-tutor-ingest")
_GATHER_CONCURRENCY = 5


class TreeBuildResult(BaseModel):
    """Summary returned to the caller after a successful ingestion."""

    book_slug: str
    json_path: Path
    node_count: int
    page_count: int
    total_llm_calls: int
    suspicious_pages: int
    elapsed_seconds: float


class _CleanedPage(BaseModel):
    """Internal: a page after layers 2+3 have been applied."""

    page_num: int
    cleaned_text: str
    was_suspicious: bool
    llm_applied: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_default_database_dir() -> Path:
    """Walk upwards from this file to locate ``<repo>/database/textbooks/``."""
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidate = ancestor / "database" / "textbooks"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "Could not locate database/textbooks/ directory above "
        f"{here}. Pass database_dir= explicitly."
    )


def _count_nodes(structure: list[dict[str, Any]]) -> int:
    """Recursively count nodes in a PageIndex structure list."""
    total = 0
    for node in structure:
        total += 1
        children = node.get("nodes") or []
        if children:
            total += _count_nodes(children)
    return total


async def _apply_cleaning_layers(
    pages: list[PageText],
    *,
    run_llm_cleaner: bool,
    llm_client: LLMClient,
    llm_model: str,
) -> tuple[list[_CleanedPage], int, int]:
    """Run layer 2 (regex) and optional layer 3 (LLM) over every page.

    Returns ``(cleaned_pages, suspicious_count, llm_call_count)``.
    """
    cleaned: list[_CleanedPage] = []
    suspicious = 0
    llm_calls = 0

    for page in pages:
        result = regex_clean(page.text)
        text = result.cleaned_text
        llm_applied = False
        if result.was_suspicious:
            suspicious += 1
            if run_llm_cleaner:
                text = await llm_clean(text, llm_client, llm_model)
                llm_calls += 1
                llm_applied = True
        cleaned.append(
            _CleanedPage(
                page_num=page.page_num,
                cleaned_text=text,
                was_suspicious=result.was_suspicious,
                llm_applied=llm_applied,
            )
        )
    return cleaned, suspicious, llm_calls


def _write_cleaned_pdf(
    cleaned_pages: list[_CleanedPage],
    source_pdf: Path,
    output_path: Path,
) -> Path:
    """Rewrite a PDF whose page text comes from ``cleaned_pages``.

    Page geometry is copied from the source PDF so PageIndex's physical page
    indices still refer to the same 1-indexed pages as the original. Styling
    is NOT preserved — PageIndex only needs the text content.
    """
    out = fitz.open()
    try:
        with fitz.open(source_pdf) as src:
            by_num = {p.page_num: p for p in cleaned_pages}
            for idx in range(src.page_count):
                original = src.load_page(idx)
                rect = original.rect
                new_page = out.new_page(width=rect.width, height=rect.height)
                text = by_num.get(idx + 1)
                content = text.cleaned_text if text else ""
                if content:
                    new_page.insert_text(
                        (50, 72),
                        content,
                        fontsize=10,
                    )
        out.save(output_path)
    finally:
        out.close()
    return output_path


_PAGEINDEX_TIMEOUT_SECONDS = 900  # 15-minute watchdog — hangs fail fast


async def _run_pageindex(cleaned_pdf_path: Path) -> dict[str, Any]:
    """Invoke vendored PageIndex and return its raw result dict.

    PageIndex's ``page_index_main`` calls ``asyncio.run()`` internally, which
    cannot be nested inside an already-running event loop. We run it on a
    worker thread so it creates its own loop via ``asyncio.to_thread``.

    A 15-minute watchdog caps total runtime — any hang (deadlock, stuck
    httpx call, rate-limit stall) surfaces as a clear TimeoutError rather
    than an indefinite idle process.
    """

    def _sync_call() -> Any:
        return vendored_pageindex.page_index(str(cleaned_pdf_path))

    try:
        raw = await asyncio.wait_for(
            asyncio.to_thread(_sync_call),
            timeout=_PAGEINDEX_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as e:
        raise RuntimeError(
            f"PageIndex indexing exceeded {_PAGEINDEX_TIMEOUT_SECONDS}s "
            "watchdog — likely a gather deadlock or hung LLM call. Check "
            "/tmp/gemma-tutor-smoke/ingest_run.log for the last activity."
        ) from e

    if inspect.isawaitable(raw):
        raw = await raw
    if not isinstance(raw, dict):
        raise RuntimeError(
            f"PageIndex returned unexpected type {type(raw).__name__}; "
            "expected dict."
        )
    return raw


def _build_final_payload(
    *,
    result_dict: dict[str, Any],
    book_slug: str,
    doc_name: str,
    source_url: str,
    allowed_source: AllowedSource,
    language: str,
    subject: str,
    subject_scope: str,
    exam_coverage: list[str],
    ingested_at: str,
    cleaned_at: str,
    run_llm_cleaner: bool,
    settings: Settings,
) -> dict[str, Any]:
    """Wrap PageIndex's output with the provenance metadata from §10.3."""
    layers = ["whitelist", "regex"]
    if run_llm_cleaner:
        layers.append("llm_pass")
    return {
        "doc_name": doc_name,
        "book_slug": book_slug,
        "doc_description": result_dict.get("doc_description", ""),
        "source_url": source_url,
        "source_authority": allowed_source.authority,
        "source_publisher": allowed_source.publisher,
        "language": language,
        "subject": subject,
        "subject_scope": subject_scope,
        "exam_coverage": exam_coverage,
        "ingested_at": ingested_at,
        "cleaned_at": cleaned_at,
        "cleanup_version": _CLEANUP_VERSION,
        "cleaner_layers_applied": layers,
        "pageindex_version": _PAGEINDEX_VERSION,
        "llm_model_indexing": settings.model_answer,
        "structure": result_dict.get("structure", []),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def ingest_pdf(
    *,
    source_url: str,
    book_slug: str,
    doc_name: str,
    subject: Literal["geography"] = "geography",
    subject_scope: Literal["rajasthan", "pan_india", "world"] = "rajasthan",
    exam_coverage: list[str] | None = None,
    language: Literal["en"] = "en",
    run_llm_cleaner: bool = False,
    database_dir: Path | None = None,
    tmp_dir: Path | None = None,
    llm_client: LLMClient | None = None,
    settings: Settings | None = None,
) -> TreeBuildResult:
    """Run the full ingestion pipeline for one textbook.

    Subject-scoping is explicit per ARCHITECTURE §10.3. Default scope is
    ``rajasthan`` because the hackathon MVP targets Rajasthan govt exam
    aspirants — pan-India material (like NCERT Class 10) must be tagged
    explicitly so retrieval can down-weight it vs Rajasthan-native content.
    """
    start = time.monotonic()
    ingested_at = datetime.now(timezone.utc).isoformat()

    # Layer 1 — whitelist. Raises SourceNotAllowedError if rejected.
    allowed_source = validate_source(source_url)

    resolved_settings = settings or get_settings()
    resolved_client = llm_client or get_llm_client(resolved_settings)
    resolved_database_dir = (
        database_dir if database_dir is not None else _find_default_database_dir()
    )
    resolved_database_dir.mkdir(parents=True, exist_ok=True)
    resolved_tmp_dir = tmp_dir if tmp_dir is not None else _DEFAULT_TMP_ROOT / book_slug
    resolved_tmp_dir.mkdir(parents=True, exist_ok=True)

    # Download + merge.
    download: DownloadResult = await download_pdf(
        source_url, resolved_tmp_dir / "download"
    )

    # Extract pages (layer 0 — raw text).
    extraction = extract_pages(download.merged_pdf_path)

    # Layers 2 (+ optional 3).
    cleaned_pages, suspicious_pages, layer3_calls = await _apply_cleaning_layers(
        extraction.pages,
        run_llm_cleaner=run_llm_cleaner,
        llm_client=resolved_client,
        llm_model=resolved_settings.model_answer,
    )
    cleaned_at = datetime.now(timezone.utc).isoformat()

    # Rewrite PDF with cleaned text before handing to PageIndex.
    cleaned_pdf_path = _write_cleaned_pdf(
        cleaned_pages,
        source_pdf=download.merged_pdf_path,
        output_path=resolved_tmp_dir / "cleaned.pdf",
    )

    # Inject LLM client into vendored PageIndex + run it.
    vendored_pageindex.set_llm_client(
        resolved_client, resolved_settings.model_answer
    )
    # NOTE: do NOT call set_gather_concurrency(). PageIndex has multiple
    # nested gather sites; sharing a single semaphore across them causes a
    # deadlock where an outer gather holds all slots while a nested one waits
    # forever. Letting _bounded_gather fall back to a fresh per-call
    # Semaphore(5) keeps each gather independently bounded without nesting
    # coupling. See sessions/2026-04-15.md for the full diagnosis.
    result_dict = await _run_pageindex(cleaned_pdf_path)

    final_payload = _build_final_payload(
        result_dict=result_dict,
        book_slug=book_slug,
        doc_name=doc_name,
        source_url=source_url,
        allowed_source=allowed_source,
        language=language,
        subject=subject,
        subject_scope=subject_scope,
        exam_coverage=list(exam_coverage or []),
        ingested_at=ingested_at,
        cleaned_at=cleaned_at,
        run_llm_cleaner=run_llm_cleaner,
        settings=resolved_settings,
    )

    json_path = (resolved_database_dir / f"{book_slug}.json").resolve()
    with json_path.open("w", encoding="utf-8") as fp:
        json.dump(final_payload, fp, indent=2, ensure_ascii=False)

    node_count = _count_nodes(final_payload["structure"])
    elapsed = time.monotonic() - start

    return TreeBuildResult(
        book_slug=book_slug,
        json_path=json_path,
        node_count=node_count,
        page_count=extraction.page_count,
        total_llm_calls=layer3_calls,
        suspicious_pages=suspicious_pages,
        elapsed_seconds=elapsed,
    )
