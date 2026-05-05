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
  * an http(s) URL or ZIP URL — downloaded + merged via the
    ingestion_v2.pdf_downloader helper (kept after V1 cleanup since it
    handles ZIP-of-PDFs merging that V2 still needs).
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

# pydantic-settings resolves env_file relative to CWD. Load backend/.env
# explicitly here so the CLI can be invoked from anywhere without losing
# LLM_PROVIDER / OPENROUTER_API_KEY from the user's environment.
try:
    from dotenv import load_dotenv
    load_dotenv(_BACKEND / ".env", override=False)
except ImportError:  # pragma: no cover - dotenv is a hard dep
    pass


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
    stream=sys.stdout,
)


from ingestion_v2.embedders import HashBagEmbedder  # noqa: E402
from ingestion_v2.pdf_downloader import download_pdf  # noqa: E402
from ingestion_v2.pipeline import run_pipeline  # noqa: E402
from ingestion_v2.text_cleanup import BRANDING_BUNDLES  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--source",
        required=True,
        help="HTTP(S) URL, ZIP URL, file:// URI, or local path to the PDF.",
    )
    # v3 schema: subject is the canonical key; book_slug becomes per-source
    # provenance metadata only (kept for audit + dedup).
    p.add_argument(
        "--subject-slug", default=None,
        help="Subject canonical slug (e.g. 'rajasthan_geography'). "
             "If omitted, falls back to --subject for v2 compat.",
    )
    p.add_argument("--subject", default="geography")
    p.add_argument(
        "--book-slug", required=True,
        help="Per-source slug retained inside sources[] metadata for audit "
             "and dedup ranking (NOT exposed in URLs / UI).",
    )
    p.add_argument("--book-name", required=True)
    p.add_argument("--scope", default="rajasthan")
    p.add_argument(
        "--authority-rank", type=int, default=3,
        help="0=NCERT, 1=RBSE/state, 2=coaching, 3=other. Drives dedup "
             "winner-rule ordering when a subject has multiple sources.",
    )
    p.add_argument(
        "--overwrite-subject", action="store_true",
        help="Clobber an existing subject folder. Default: refuse and "
             "exit with a clear error so a 2nd source must route through "
             "merge.py (deferred to P2.5).",
    )
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
    p.add_argument(
        "--branding",
        default=None,
        choices=sorted(BRANDING_BUNDLES.keys()),
        help=(
            "Name of a source-specific branding pattern bundle to strip "
            "(in addition to the always-on generic patterns). E.g. "
            "'springboard_rajasthan' for the Springboard RAS Pre notes."
        ),
    )
    return p.parse_args()


async def _resolve_source(source: str) -> Path:
    """Turn a --source value into a local file path (.pdf or .txt).

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

    pdf_path = await _resolve_source(args.source)
    if not pdf_path.exists():
        logging.error("Source file not found at %s", pdf_path)
        return 2

    exam_coverage = [
        s.strip() for s in args.exam_coverage.split(",") if s.strip()
    ]
    book_metadata = {
        "name": args.book_name,
        "scope": args.scope,
        "exam_coverage": exam_coverage,
        "publisher": args.publisher,
        "authority_rank": args.authority_rank,
        "source_url": args.source if urlparse(args.source).scheme in ("http", "https") else "",
    }

    output_root = Path(args.output_root).resolve() if args.output_root else None

    source_patterns = (
        list(BRANDING_BUNDLES[args.branding]) if args.branding else []
    )
    if source_patterns:
        logging.info(
            "using branding bundle '%s' (%d extra patterns)",
            args.branding, len(source_patterns),
        )

    # v3 canonical: subject_slug drives the folder layout. Falls back to
    # --subject for callers still on the v2 CLI surface.
    subject_slug = args.subject_slug or args.subject

    # Stage 6.5b — when an existing subject tree is on disk and we're not
    # clobbering, the pipeline merges this source in via cosine + judge.
    # Wire a deterministic stdlib embedder by default so no extra deps or
    # API keys are needed; callers wanting higher-quality semantic match
    # can swap this for a real embedder by importing run_pipeline directly.
    candidate_root = output_root or (
        Path(__file__).resolve().parent.parent / "backend" / "database" / "skills"
    )
    embedder = None
    if (candidate_root / subject_slug).exists() and not args.overwrite_subject:
        embedder = HashBagEmbedder()
        logging.info(
            "subject tree already exists at %s — wiring HashBagEmbedder for "
            "merge stage (cosine prefilter; no API cost)",
            candidate_root / subject_slug,
        )

    result = await run_pipeline(
        pdf_path=pdf_path,
        subject_slug=subject_slug,
        book_slug=args.book_slug,
        book_metadata=book_metadata,
        output_root=output_root,
        source_patterns=source_patterns,
        overwrite_subject=args.overwrite_subject,
        embedder=embedder,
    )

    print("=" * 70)
    print("V2 INGESTION COMPLETE")
    print("=" * 70)
    print(f"skill_folder       : {result.skill_folder}")
    print(f"total_nodes        : {result.total_nodes}")
    print(f"total_leaves       : {result.total_leaves}")
    print(f"coverage           : {result.coverage * 100:.1f}%")
    print(f"elapsed_seconds    : {result.elapsed_seconds:.1f}")
    if result.merge_report is not None:
        m = result.merge_report
        print(
            f"merge              : appended={m.appended}  "
            f"added_leaves={m.added_leaves}  added_chapters={m.added_chapters}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
