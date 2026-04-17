"""One-shot ingestion of a single NCERT textbook.

Usage:
    cd backend
    uv run python ../scripts/ingest_one.py

Runs the full ingestion pipeline (whitelist -> download -> merge -> extract
-> clean -> vendored PageIndex -> provenance JSON) against the real NCERT
Class 10 Geography "Contemporary India II" textbook using the currently
configured LLM provider (see backend/.env).

This script is intentionally minimal. Production bulk ingestion (Day 6)
will use scripts/ingest_ncert.py with all 9 books.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

# Resolve backend/ into sys.path so `ingestion.*` imports work regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Make logging from vendored PageIndex + our ingestion layer visible on stderr.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
)

from ingestion.tree_builder import ingest_pdf  # noqa: E402


async def main() -> None:
    started = time.monotonic()
    result = await ingest_pdf(
        source_url="https://ncert.nic.in/textbook/pdf/jess1dd.zip",
        book_slug="ncert_class10_contemporary_india_2",
        doc_name="Contemporary India II (NCERT Class 10 Geography)",
        subject="geography",
        subject_scope="pan_india",  # national NCERT book — secondary fallback vs Rajasthan-native content
        exam_coverage=["patwari", "reet", "ras_pre", "rbse_10"],
        language="en",
        run_llm_cleaner=False,
    )
    elapsed = time.monotonic() - started

    print("=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)
    print(f"book_slug         : {result.book_slug}")
    print(f"json_path         : {result.json_path}")
    print(f"page_count        : {result.page_count}")
    print(f"node_count        : {result.node_count}")
    print(f"suspicious_pages  : {result.suspicious_pages}")
    print(f"wall clock        : {elapsed:.1f}s")
    print(f"tree_builder      : {result.elapsed_seconds:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
