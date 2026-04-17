"""V2 ingestion CLI — run the Gemma-only agentic pipeline on a single PDF.

Usage:
    source backend/.venv/bin/activate
    python scripts/ingest_v2.py \\
        --source <pdf_path_or_http_url> \\
        --subject geography \\
        --book-slug ncert_class10_contemporary_india_2_v2 \\
        --book-name "Contemporary India II (NCERT Class 10 Geography) — V2" \\
        --scope pan_india \\
        --exam-coverage "patwari,reet,ras_pre,rbse_10" \\
        --publisher NCERT

The CLI accepts either:
  * an http(s) URL or ZIP URL — downloaded + merged via the existing
    ingestion.pdf_downloader (same helper used by V1)
  * a local filesystem path (absolute or relative) — used as-is
  * a file:// URI — stripped to a local path

The emitted skill folder lands at
``database/skills/<subject>/<book_slug>/`` by default.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse


# Make backend/ importable regardless of CWD.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
    stream=sys.stdout,
)


from ingestion.pdf_downloader import download_pdf  # noqa: E402
from ingestion_v2.pipeline import run_pipeline  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--source",
        required=True,
        help="HTTP(S) URL, ZIP URL, file:// URI, or local path to the PDF.",
    )
    p.add_argument("--subject", default="geography")
    p.add_argument("--book-slug", required=True)
    p.add_argument("--book-name", required=True)
    p.add_argument("--scope", default="rajasthan")
    p.add_argument(
        "--exam-coverage",
        default="",
        help="Comma-separated list of exam codes (e.g. 'patwari,reet,ras_pre').",
    )
    p.add_argument("--publisher", default="unknown")
    p.add_argument(
        "--output-root",
        default=None,
        help="Override output root (default: <repo>/database/skills).",
    )
    return p.parse_args()


async def _resolve_pdf(source: str) -> Path:
    """Turn a --source value into a local PDF path.

    HTTP(S) + ZIP URLs are routed through the V1 downloader (merges zipped
    chapter PDFs into a single file). file:// URIs and bare paths are used
    as-is.
    """
    parsed = urlparse(source)
    scheme = parsed.scheme.lower()

    if scheme in ("http", "https"):
        dest_dir = Path(tempfile.mkdtemp(prefix="gemma-v2-ingest-"))
        logging.info("downloading PDF to %s", dest_dir)
        result = await download_pdf(source, dest_dir)
        return Path(result.merged_pdf_path)

    if scheme == "file":
        # file:///abs/path → /abs/path
        local = parsed.path
        return Path(local)

    # Bare path (possibly relative).
    path = Path(source).expanduser()
    if not path.is_absolute():
        path = path.resolve()
    return path


async def _main() -> int:
    args = _parse_args()

    pdf_path = await _resolve_pdf(args.source)
    if not pdf_path.exists():
        logging.error("PDF not found at %s", pdf_path)
        return 2

    exam_coverage = [
        s.strip() for s in args.exam_coverage.split(",") if s.strip()
    ]
    book_metadata = {
        "name": args.book_name,
        "scope": args.scope,
        "exam_coverage": exam_coverage,
        "publisher": args.publisher,
        "source_url": args.source if urlparse(args.source).scheme in ("http", "https") else "",
    }

    output_root = Path(args.output_root).resolve() if args.output_root else None

    result = await run_pipeline(
        pdf_path=pdf_path,
        subject=args.subject,
        book_slug=args.book_slug,
        book_metadata=book_metadata,
        output_root=output_root,
    )

    print("=" * 70)
    print("V2 INGESTION COMPLETE")
    print("=" * 70)
    print(f"skill_folder       : {result.skill_folder}")
    print(f"total_nodes        : {result.total_nodes}")
    print(f"total_leaves       : {result.total_leaves}")
    print(f"coverage           : {result.coverage * 100:.1f}%")
    print(f"elapsed_seconds    : {result.elapsed_seconds:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
