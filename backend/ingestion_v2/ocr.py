"""Stage 1.5 — page-level OCR using Tesseract.

PyMuPDF only extracts native text glyphs. Coaching textbooks for RAS Pre
embed maps, tables, and section headers as raster images — that content is
invisible to ``page.get_text()``. Tesseract OCRs the rendered page and we
merge the OCR-only lines (those not already in native text) into the page
text BEFORE branding cleanup runs.

Per spec Addendum A.10 — added 2026-05-01 after audit found 100% of
Springboard pages have embedded images (2503 total across 267 pages).
"""

from __future__ import annotations

import logging
from io import BytesIO

import fitz
import pytesseract
from PIL import Image


logger = logging.getLogger(__name__)


# Render at 200 DPI — empirically gives Tesseract enough resolution for
# small map labels without blowing render time past 2s/page.
_OCR_DPI = 200


def _normalize_line(line: str) -> str:
    """Normalize a line for substring comparison (case + whitespace)."""
    return " ".join(line.lower().split())


def merge_ocr_with_native(native_text: str, ocr_text: str) -> str:
    """Append OCR-only lines to native text, dropping ones already present.

    Strategy:
      * Walk every non-trivial line of OCR output.
      * Skip if its normalized form appears in the normalized native text.
      * Otherwise append to a recovered-content block.

    The recovered block is separated from native text by a blank line so
    the paragraph splitter treats it as a fresh paragraph (which it is —
    it came from the page's image layer, not its text layer).
    """
    if not ocr_text.strip():
        return native_text

    native_norm = _normalize_line(native_text)
    recovered: list[str] = []
    seen_norms: set[str] = set()
    for raw_line in ocr_text.splitlines():
        norm = _normalize_line(raw_line)
        if not norm or len(norm) < 4:
            continue
        if norm in seen_norms:
            continue
        if norm in native_norm:
            continue
        recovered.append(raw_line.strip())
        seen_norms.add(norm)

    if not recovered:
        return native_text

    return native_text.rstrip() + "\n\n" + "\n".join(recovered) + "\n"


def ocr_page(page: fitz.Page, *, dpi: int = _OCR_DPI, lang: str = "eng") -> str:
    """Render ``page`` as a raster and OCR it via Tesseract.

    Returns the raw OCR text (no normalization). Caller merges with native
    text via :func:`merge_ocr_with_native`.
    """
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img, lang=lang)
