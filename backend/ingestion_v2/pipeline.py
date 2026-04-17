"""V2 ingestion pipeline orchestrator.

Composes extract → pre_structure → decompose → validate → fill → emit into
a single coroutine. Callers provide a PDF path + book metadata and receive
a PipelineResult describing the emitted skill folder.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from config import Settings, get_settings
from llm.factory import get_llm_client

from .content_fill import FilledNode, FilledTree, fill_content
from .emit import emit_skill_folder
from .extract import ExtractedDoc, extract_document
from .multi_agent import ProposedTree, decompose
from .pre_structure import build_draft
from .text_cleanup import CleanupPattern
from .validation import ValidationResult, validate_coverage


logger = logging.getLogger(__name__)


# Default output root used when the caller doesn't override it. Resolves to
# <repo-root>/database/skills/.
_DEFAULT_OUTPUT_ROOT = (
    Path(__file__).resolve().parent.parent.parent / "database" / "skills"
)


class PipelineResult(BaseModel):
    skill_folder: Path
    total_nodes: int = Field(ge=0)
    total_leaves: int = Field(ge=0)
    coverage: float = Field(ge=0.0, le=1.0)
    elapsed_seconds: float = Field(ge=0.0)

    model_config = {"arbitrary_types_allowed": True}


def _count_nodes(node: FilledNode) -> tuple[int, int]:
    """Return (total_nodes, total_leaves) for a FilledNode subtree."""
    if not node.children:
        return 1, 1
    total, leaves = 1, 0
    for child in node.children:
        t, l = _count_nodes(child)
        total += t
        leaves += l
    return total, leaves


async def run_pipeline(
    pdf_path: Path,
    subject: str,
    book_slug: str,
    book_metadata: dict[str, Any],
    output_root: Path | None = None,
    settings: Settings | None = None,
    source_patterns: list[CleanupPattern] | None = None,
) -> PipelineResult:
    """Run the full V2 ingestion pipeline end-to-end.

    Args:
        pdf_path: Absolute path to a text-extractable PDF.
        subject: Top-level subject folder name, e.g. ``"geography"``.
        book_slug: kebab-or-snake-case unique ID under <subject>, e.g.
            ``"ncert_class10_contemporary_india_2_v2"``.
        book_metadata: Freeform dict rendered into the root SKILL.md
            frontmatter. Recognized keys: name, scope, exam_coverage,
            publisher, source_url.
        output_root: Root for emitted skill folders. Defaults to
            ``<repo>/database/skills/``.
        settings: Optional Settings override; otherwise loaded via
            get_settings().

    Returns:
        PipelineResult with the emitted path, node stats, and coverage.
    """
    started = time.monotonic()
    s = settings or get_settings()
    root = output_root or _DEFAULT_OUTPUT_ROOT
    model = s.model_ingestion
    book_title = book_metadata.get("name") or book_slug

    logger.info("pipeline: starting (pdf=%s, model=%s)", pdf_path, model)

    # Stage 1 — Extraction (with optional source-specific branding cleanup)
    logger.info("pipeline: stage 1 — extracting paragraphs")
    extracted: ExtractedDoc = extract_document(
        pdf_path, source_patterns=source_patterns or []
    )
    logger.info(
        "pipeline: extracted %d paragraphs across %d pages (%d bookmarks)",
        len(extracted.paragraphs),
        extracted.page_count,
        len(extracted.bookmarks),
    )

    # Stage 2 — Pre-structure
    logger.info("pipeline: stage 2 — building draft hierarchy")
    draft = build_draft(extracted)
    logger.info(
        "pipeline: draft has %d candidate chapters (bookmark-driven=%s)",
        len(draft.candidate_chapters),
        draft.has_bookmark_structure,
    )

    # Stage 4 — Multi-agent decomposition (3 is the RAG-prime no-op)
    logger.info("pipeline: stage 4 — Proposer + Critic")
    llm = get_llm_client(s)
    proposed: ProposedTree = await decompose(
        llm,
        draft=draft,
        extracted=extracted,
        model=model,
        book_title=book_title,
        book_subject=subject,
        max_critic_rounds=1,
    )

    # Stage 5 — Validation
    logger.info("pipeline: stage 5 — coverage validation")
    validation: ValidationResult = validate_coverage(proposed, extracted)
    logger.info(
        "pipeline: coverage=%.1f%% (%d/%d paragraphs referenced; ok=%s)",
        validation.coverage * 100,
        validation.referenced_paragraphs,
        validation.total_paragraphs,
        validation.ok,
    )
    if not validation.ok:
        logger.warning(
            "pipeline: coverage below threshold — %d paragraphs unreferenced "
            "(first 10: %s); proceeding anyway",
            len(validation.unreferenced),
            validation.unreferenced[:10],
        )

    # Stage 7 — Content assembly (deterministic, source-preserving; no LLM)
    # See spec Addendum A.1 — leaves get verbatim paragraphs, internal nodes
    # get a Contents outline. No summarization.
    logger.info("pipeline: stage 7 — assembling source-preserved content")
    filled: FilledTree = fill_content(tree=proposed, extracted=extracted)

    # Stage 8 — Emit
    logger.info("pipeline: stage 8 — emitting skill folder")
    folder = await emit_skill_folder(
        filled=filled,
        subject=subject,
        book_slug=book_slug,
        book_metadata=book_metadata,
        output_root=root,
    )

    total_nodes, total_leaves = _count_nodes(filled.root)
    elapsed = time.monotonic() - started
    logger.info(
        "pipeline: done in %.1fs — %d nodes (%d leaves) at %s",
        elapsed,
        total_nodes,
        total_leaves,
        folder,
    )

    return PipelineResult(
        skill_folder=folder,
        total_nodes=total_nodes,
        total_leaves=total_leaves,
        coverage=validation.coverage,
        elapsed_seconds=elapsed,
    )
