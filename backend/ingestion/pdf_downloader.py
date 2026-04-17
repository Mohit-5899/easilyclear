"""Download + unzip + merge helper for textbook PDFs.

NCERT ships textbooks as a ZIP of per-chapter PDFs, so the ingestion pipeline
needs a small utility that can:

* fetch a single URL (either a .pdf or a .zip) to a temp location,
* unzip and list the chapter PDFs in lexicographic order,
* merge them into one contiguous PDF via PyMuPDF's ``Document.insert_pdf``.

The merge step is critical: PageIndex works on a single document, and
NCERT's chapter-file naming (e.g. ``jess101.pdf`` .. ``jess107.pdf``) sorts
lexicographically into the correct chapter order.

See ARCHITECTURE.md §10 for the surrounding ingestion pipeline.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import fitz  # PyMuPDF
import httpx
from pydantic import BaseModel, HttpUrl

_DOWNLOAD_TIMEOUT_SECONDS = 120.0


class DownloadResult(BaseModel):
    """Outcome of ``download_pdf``. All paths are absolute."""

    source_url: HttpUrl
    merged_pdf_path: Path
    chapter_paths: list[Path]
    total_bytes: int
    total_pages: int


def _merge_pdfs(chapter_paths: list[Path], output_path: Path) -> Path:
    """Merge ``chapter_paths`` in order into a single PDF at ``output_path``.

    Uses PyMuPDF's ``Document.insert_pdf`` which preserves page content and
    ordering. No re-rendering, no text loss.
    """
    merged = fitz.open()
    try:
        for chapter in chapter_paths:
            with fitz.open(chapter) as src:
                merged.insert_pdf(src)
        merged.save(output_path)
    finally:
        merged.close()
    return output_path


async def download_pdf(url: str, dest_dir: Path) -> DownloadResult:
    """Download a PDF or ZIP from ``url`` and return a ``DownloadResult``.

    If the URL ends in ``.zip``, the archive is extracted into
    ``dest_dir/unzipped/`` and every contained ``.pdf`` is merged (in
    lexicographic filename order) into ``dest_dir/merged.pdf``. If the URL
    ends in ``.pdf``, it is saved as-is and no merging happens.

    Raises:
        httpx.HTTPError: if the HTTP GET returns a non-success status.
        RuntimeError: if the URL neither ends in ``.pdf`` nor ``.zip``.
    """
    # Validate URL shape at the boundary (§1.6).
    HttpUrl(url)

    dest_dir.mkdir(parents=True, exist_ok=True)
    basename = url.rsplit("/", 1)[-1]
    lower = basename.lower()

    if not (lower.endswith(".pdf") or lower.endswith(".zip")):
        raise RuntimeError(f"Downloaded file is not a PDF or zip: {url}")

    downloaded_path = dest_dir / basename
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=_DOWNLOAD_TIMEOUT_SECONDS,
    ) as http:
        response = await http.get(url)
        response.raise_for_status()
        downloaded_path.write_bytes(response.content)

    total_bytes = downloaded_path.stat().st_size

    if lower.endswith(".zip"):
        unzip_dir = dest_dir / "unzipped"
        unzip_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(downloaded_path) as zf:
            zf.extractall(unzip_dir)
        chapter_paths = sorted(
            p.resolve() for p in unzip_dir.rglob("*.pdf") if p.is_file()
        )
        if not chapter_paths:
            raise RuntimeError(f"Zip contained no PDF files: {url}")
        merged_pdf_path = _merge_pdfs(chapter_paths, dest_dir / "merged.pdf")
    else:
        chapter_paths = []
        merged_pdf_path = downloaded_path

    with fitz.open(merged_pdf_path) as doc:
        total_pages = doc.page_count

    return DownloadResult(
        source_url=url,
        merged_pdf_path=merged_pdf_path.resolve(),
        chapter_paths=chapter_paths,
        total_bytes=total_bytes,
        total_pages=total_pages,
    )
