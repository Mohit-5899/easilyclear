"""V2 ingestion pipeline orchestrator.

Composes extract → pre_structure → decompose → validate → fill → emit into
a single coroutine. Callers provide a PDF path + book metadata and receive
a PipelineResult describing the emitted skill folder.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from config import Settings, get_settings
from llm.factory import get_llm_client

from .content_fill import FilledNode, FilledTree, fill_content
from .dedup import Embedder, LeafLabel
from .emit import emit_skill_folder
from .extract import ExtractedDoc, extract_document
from .merge import MergeReport, merge_into_subject_tree
from .multi_agent import ProposedTree, decompose
from .pre_structure import build_draft
from .text_cleanup import CleanupPattern
from .title_refiner import refine_titles
from .validation import ValidationResult, validate_coverage


logger = logging.getLogger(__name__)


# Default output root used when the caller doesn't override it. Resolves to
# <repo-root>/database/skills/.
_DEFAULT_OUTPUT_ROOT = (
    Path(__file__).resolve().parent.parent / "database" / "skills"
)


class PipelineResult(BaseModel):
    skill_folder: Path
    total_nodes: int = Field(ge=0)
    total_leaves: int = Field(ge=0)
    coverage: float = Field(ge=0.0, le=1.0)
    elapsed_seconds: float = Field(ge=0.0)
    merge_report: MergeReport | None = None

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
    subject_slug: str,
    book_metadata: dict[str, Any],
    *,
    book_slug: str | None = None,
    output_root: Path | None = None,
    settings: Settings | None = None,
    source_patterns: list[CleanupPattern] | None = None,
    overwrite_subject: bool = False,
    embedder: Embedder | None = None,
    judge: "Callable[[LeafLabel, LeafLabel], str] | None" = None,
) -> PipelineResult:
    """Run the full V2 ingestion pipeline end-to-end (v3 schema).

    Args:
        pdf_path: Absolute path to a text-extractable PDF.
        subject_slug: Subject canonical slug (e.g. ``"rajasthan_geography"``).
            Replaces the old ``subject`` + ``book_slug`` pair — books no
            longer get their own subfolder under the subject (per spec
            2026-05-04).
        book_metadata: Freeform dict for the root SKILL.md frontmatter.
            Recognized keys: name, scope, exam_coverage, publisher,
            source_url, authority_rank (0=NCERT, 1=RBSE/state, 2=coaching).
        book_slug: Per-source slug retained inside ``sources[]`` metadata
            (audit trail). If omitted, derived from book_metadata.publisher
            via slugify().
        output_root: Root for emitted skill folders. Defaults to
            ``<repo>/database/skills/``.
        overwrite_subject: If True, clobber an existing subject folder.
            Default False — emit raises SubjectTreeExistsError to prevent
            silent overwrites; the caller should route a 2nd source
            through merge.py instead.

    Returns:
        PipelineResult with the emitted path, node stats, and coverage.
    """
    started = time.monotonic()
    s = settings or get_settings()
    root = output_root or _DEFAULT_OUTPUT_ROOT
    model = s.model_ingestion
    book_title = book_metadata.get("name") or subject_slug
    # Derive a per-source book_slug if not provided — purely metadata.
    effective_book_slug = book_slug or book_metadata.get("book_slug") or subject_slug

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
        # Per spec Addendum A.9 — coverage failure means content is missing
        # from a student's study material. Fail hard rather than emit a
        # broken skill folder that masks the bug downstream.
        raise RuntimeError(
            f"pipeline: coverage below threshold "
            f"({validation.coverage * 100:.1f}% < required), "
            f"{len(validation.unreferenced)} paragraphs unreferenced "
            f"(first 10: {validation.unreferenced[:10]})"
        )

    # Stage 6 — Title refinement (one Gemma call per leaf)
    # See spec Addendum A.11 — Proposer titles drift from content when it
    # picks range boundaries one section header late. We refine each leaf
    # title from its actual first paragraphs before content assembly so
    # internal-node "Contents" outlines pick up the corrected titles.
    logger.info("pipeline: stage 6 — refining leaf titles")
    proposed = await refine_titles(
        llm, tree=proposed, extracted=extracted, model=model,
    )

    # Stage 7 — Content assembly (deterministic, source-preserving; no LLM)
    # See spec Addendum A.1 — leaves get verbatim paragraphs, internal nodes
    # get a Contents outline. No summarization.
    logger.info("pipeline: stage 7 — assembling source-preserved content")
    filled: FilledTree = fill_content(tree=proposed, extracted=extracted)

    # Stage 8 — Emit (v3 schema; subject-canonical layout)
    source_metadata = {
        "publisher": book_metadata.get("publisher", "unknown"),
        "book_slug": effective_book_slug,
        "authority_rank": int(book_metadata.get("authority_rank", 3)),
    }
    subject_dir = root / subject_slug
    merge_report: MergeReport | None = None

    if subject_dir.exists() and not overwrite_subject:
        # Stage 6.5b — merge into existing subject tree (spec §6).
        if embedder is None:
            raise RuntimeError(
                f"subject tree already exists at {subject_dir}. "
                f"Pass embedder=<Embedder> to merge this source in, or "
                f"overwrite_subject=True to clobber. See ingestion_v2/merge.py."
            )
        logger.info("pipeline: stage 6.5b — merging into existing subject tree")
        merge_report = merge_into_subject_tree(
            filled, subject_dir,
            source_metadata=source_metadata,
            embedder=embedder,
            judge=judge,
        )
        logger.info(
            "pipeline: merge complete — appended=%d added_leaves=%d added_chapters=%d",
            merge_report.appended,
            merge_report.added_leaves,
            merge_report.added_chapters,
        )
        folder = subject_dir
    else:
        logger.info("pipeline: stage 8 — emitting skill folder")
        folder = await emit_skill_folder(
            filled=filled,
            subject_slug=subject_slug,
            book_metadata=book_metadata,
            output_root=root,
            source_metadata=source_metadata,
            overwrite=overwrite_subject,
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
        merge_report=merge_report,
    )
