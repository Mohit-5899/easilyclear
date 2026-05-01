"""Stage 4 of the V2 pipeline — multi-agent Gemma decomposition.

MVP scope: Proposer → Critic → optional single refinement pass (no Tree of
Thoughts judge). The Proposer drafts a hierarchical tree from the extracted
paragraphs; the Critic reviews it against a quality rubric; if needed, the
Proposer revises once and we ship that.

JSON output is requested via OpenRouter's ``response_format={"type":
"json_object"}`` where supported, with a plain-prompting fallback + one
retry if validation fails.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from llm.base import LLMClient, Message

from ._json_utils import ensure_valid_json
from .extract import ExtractedDoc
from .pre_structure import DraftHierarchy


logger = logging.getLogger(__name__)


_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts_v2"


# -----------------------------------------------------------------------------
# Pydantic models — Proposer output


class ProposedNode(BaseModel):
    """One node in the proposed skill tree. Recursive via `children`.

    Leaf paragraphs are referenced as an inclusive ``[start, end]`` range.
    The Proposer emits ranges (not lists) so a tree over thousands of
    paragraphs fits in the model's output-token budget. A computed
    ``paragraph_refs`` property expands the range for downstream consumers.
    """

    title: str
    description: str
    paragraph_start: int | None = None
    paragraph_end: int | None = None
    children: list["ProposedNode"] = Field(default_factory=list)

    @property
    def paragraph_refs(self) -> list[int]:
        """Expand the inclusive range into an explicit ID list."""
        if self.paragraph_start is None or self.paragraph_end is None:
            return []
        if self.paragraph_end < self.paragraph_start:
            return []
        return list(range(self.paragraph_start, self.paragraph_end + 1))


ProposedNode.model_rebuild()


def _collect_leaves(node: ProposedNode, out: list[ProposedNode]) -> None:
    """DFS collector — a leaf is any node with no children."""
    if not node.children:
        out.append(node)
        return
    for child in node.children:
        _collect_leaves(child, out)


class ProposedTree(BaseModel):
    """Root wrapper for the proposed tree.

    Per spec Addendum A.9 — structural sanity is enforced at parse time so
    the existing Proposer retry loop (run_proposer) surfaces the violation
    back to the model with a correction prompt. This catches the
    null-range/overlap bug that produced stub leaves on the first ingestion.
    """

    root: ProposedNode

    @model_validator(mode="after")
    def _check_tree_structure(self) -> "ProposedTree":
        leaves: list[ProposedNode] = []
        _collect_leaves(self.root, leaves)

        if not leaves:
            raise ValueError("tree has no leaves — at least one is required")

        for leaf in leaves:
            if leaf.paragraph_start is None or leaf.paragraph_end is None:
                raise ValueError(
                    f"leaf {leaf.title!r} has null paragraph_start or "
                    f"paragraph_end. Every leaf MUST cover a contiguous "
                    f"range of paragraph IDs (both fields non-null, "
                    f"start <= end)."
                )
            if leaf.paragraph_end < leaf.paragraph_start:
                raise ValueError(
                    f"leaf {leaf.title!r} has end ({leaf.paragraph_end}) "
                    f"< start ({leaf.paragraph_start}). Range must be "
                    f"non-empty and forward."
                )

        # Check non-overlapping ranges across ALL leaves (siblings or not).
        sorted_leaves = sorted(leaves, key=lambda lf: lf.paragraph_start or 0)
        for prev, curr in zip(sorted_leaves, sorted_leaves[1:]):
            if (curr.paragraph_start or 0) <= (prev.paragraph_end or 0):
                raise ValueError(
                    f"overlapping leaf ranges: {prev.title!r} "
                    f"[{prev.paragraph_start}-{prev.paragraph_end}] and "
                    f"{curr.title!r} "
                    f"[{curr.paragraph_start}-{curr.paragraph_end}]. "
                    f"Each paragraph ID must belong to exactly one leaf."
                )

        return self


# -----------------------------------------------------------------------------
# Pydantic models — Critic output


CriticCategory = Literal[
    "structural_imbalance",
    "sibling_duplication",
    "missing_coverage",
    "inappropriate_depth",
    "poor_naming",
]


class CriticIssue(BaseModel):
    category: CriticCategory
    node_path: str
    suggestion: str


class CriticFeedback(BaseModel):
    issues: list[CriticIssue] = Field(default_factory=list)
    overall_quality: Literal["good", "needs_revision"] = "good"


# -----------------------------------------------------------------------------
# Prompt loaders


def _read_prompt(filename: str) -> str:
    path = _PROMPT_DIR / filename
    return path.read_text(encoding="utf-8")


def _render_paragraph_block(doc: ExtractedDoc, max_chars: int | None = None) -> str:
    """Render all paragraphs as a numbered block. If max_chars is set, truncate
    each paragraph to that many chars (with an ellipsis marker)."""
    lines: list[str] = []
    for p in doc.paragraphs:
        text = p.text
        if max_chars is not None and len(text) > max_chars:
            text = text[:max_chars].rstrip() + " [...]"
        lines.append(f"[ID:{p.paragraph_id} page:{p.page}] {text}")
    return "\n".join(lines)


def _render_draft_chapters(draft: DraftHierarchy) -> str:
    """Render the pre-structure draft as a compact hint block."""
    if not draft.candidate_chapters:
        return "(no draft chapters — Gemma must discover structure from paragraphs)"
    if not draft.has_bookmark_structure:
        return (
            "(no PDF bookmarks found — draft is a single chapter containing "
            "all paragraphs; please propose a real chapter structure)"
        )
    lines: list[str] = []
    for idx, ch in enumerate(draft.candidate_chapters, start=1):
        title = ch.title or f"(untitled chapter {idx})"
        first_id = ch.paragraph_ids[0] if ch.paragraph_ids else None
        last_id = ch.paragraph_ids[-1] if ch.paragraph_ids else None
        lines.append(
            f"{idx}. {title} — pages {ch.page_range[0]}–{ch.page_range[1]}, "
            f"paragraphs {first_id}..{last_id} ({len(ch.paragraph_ids)} total)"
        )
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# JSON extraction / retry helpers


# Local alias retained for the rest of this module's call sites; the
# implementation now lives in ._json_utils so title_refiner.py can share it.
_ensure_valid_json = ensure_valid_json


async def _call_json(
    llm: LLMClient,
    system_prompt: str,
    user_prompt: str,
    *,
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Call the LLM asking for a JSON object. Tries response_format first;
    falls back to plain prompting if the provider rejects it.

    Returns the raw (hopefully-JSON) text content. Caller is responsible for
    parsing + validating.
    """
    messages = [
        Message(role="system", content=system_prompt),
        Message(role="user", content=user_prompt),
    ]
    # Try with response_format hint (OpenRouter + JSON-capable models).
    try:
        response = await llm.complete(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return response.content
    except TypeError:
        # The client doesn't accept response_format (e.g., mock/ollama).
        response = await llm.complete(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.content
    except Exception as exc:  # pragma: no cover - network / provider errors
        logger.warning(
            "json-mode call failed (%s: %s); retrying without response_format",
            type(exc).__name__,
            exc,
        )
        response = await llm.complete(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.content


# -----------------------------------------------------------------------------
# Proposer


def _build_proposer_user_prompt(
    draft: DraftHierarchy,
    extracted: ExtractedDoc,
    book_title: str,
    book_subject: str,
    existing_skills: list[Any] | None,
    prior_feedback: CriticFeedback | None,
) -> str:
    """Assemble the user-side prompt for the Proposer."""
    existing_skills_block = (
        "(none — this is the first book in this subject)"
        if not existing_skills
        else json.dumps(existing_skills, indent=2)
    )

    feedback_block = ""
    if prior_feedback is not None and prior_feedback.issues:
        feedback_block = (
            "\n\n## Critic feedback on your previous attempt\n\n"
            "The previous draft had these issues. Produce a revised tree "
            "that fixes them:\n\n"
        )
        for issue in prior_feedback.issues:
            feedback_block += (
                f"- [{issue.category}] at {issue.node_path}: {issue.suggestion}\n"
            )

    return (
        f"## Book metadata\n\n"
        f"- Title: {book_title}\n"
        f"- Subject: {book_subject}\n"
        f"- Total paragraphs: {len(extracted.paragraphs)}\n"
        f"- Total pages: {extracted.page_count}\n\n"
        f"## Draft chapters (from PDF bookmarks — a hint, not a constraint)\n\n"
        f"{_render_draft_chapters(draft)}\n\n"
        f"## Existing skills in this subject\n\n"
        f"{existing_skills_block}\n\n"
        f"## Full paragraph list\n\n"
        f"{_render_paragraph_block(extracted, max_chars=400)}"
        f"{feedback_block}\n\n"
        f"Now emit the JSON skill tree as specified. Output ONLY the JSON object."
    )


async def run_proposer(
    llm: LLMClient,
    draft: DraftHierarchy,
    extracted: ExtractedDoc,
    *,
    model: str,
    book_title: str = "Textbook",
    book_subject: str = "general",
    existing_skills: list[Any] | None = None,
    prior_feedback: CriticFeedback | None = None,
    max_tokens: int = 16384,
) -> ProposedTree:
    """Run the Proposer agent and return a validated skill tree.

    Retries once on validation failure with the parse error fed back as a
    system-level correction prompt.
    """
    system_prompt = _read_prompt("proposer_system.md")
    user_prompt = _build_proposer_user_prompt(
        draft=draft,
        extracted=extracted,
        book_title=book_title,
        book_subject=book_subject,
        existing_skills=existing_skills,
        prior_feedback=prior_feedback,
    )

    # Per spec Addendum A.9 — bumped from 2 to 5 attempts. The structural
    # validator (no nulls, no overlaps, no inverted ranges) catches subtle
    # Gemma slip-ups that often need 2-3 corrections to converge.
    max_attempts = 5
    last_raw = ""
    for attempt in range(1, max_attempts + 1):
        raw = await _call_json(
            llm,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=0.2,
            max_tokens=max_tokens,
        )
        last_raw = raw
        try:
            cleaned = _ensure_valid_json(raw)
            return ProposedTree.model_validate_json(cleaned)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                "Proposer attempt %d/%d failed validation: %s",
                attempt, max_attempts, exc,
            )
            logger.debug("Proposer raw output: %r", raw[:2000])
            if attempt == max_attempts:
                logger.error(
                    "Proposer raw output (first 2000 chars): %r", last_raw[:2000]
                )
                raise
            # Prepend a correction note and try again.
            user_prompt = (
                f"Your previous response failed validation with this error:\n"
                f"{exc}\n\n"
                f"FIX EXACTLY THAT LEAF. Re-emit the FULL JSON with the fix. "
                f"No prose, no markdown fences. Verify before emitting:\n"
                f"- every leaf has integer (non-null) paragraph_start AND paragraph_end\n"
                f"- every leaf has paragraph_end >= paragraph_start\n"
                f"- no two leaves share any paragraph ID (no overlaps)\n"
                f"- sorted leaves cover [0..total-1] contiguously (no gaps)\n\n"
                f"{user_prompt}"
            )
    raise RuntimeError("unreachable")


# -----------------------------------------------------------------------------
# Critic


def _build_critic_user_prompt(
    proposed: ProposedTree, extracted: ExtractedDoc
) -> str:
    return (
        f"## Total paragraph count in source document\n\n"
        f"{len(extracted.paragraphs)} paragraphs (IDs 0 to "
        f"{len(extracted.paragraphs) - 1 if extracted.paragraphs else 0})\n\n"
        f"## Proposed skill tree\n\n"
        f"```json\n{proposed.model_dump_json(indent=2)}\n```\n\n"
        f"Now evaluate the tree against the rubric and emit your JSON feedback."
    )


async def run_critic(
    llm: LLMClient,
    proposed: ProposedTree,
    extracted: ExtractedDoc,
    *,
    model: str,
    max_tokens: int = 4096,
) -> CriticFeedback:
    """Run the Critic agent. On parse failure, returns empty-good feedback
    rather than blocking the pipeline (the tree is already usable)."""
    system_prompt = _read_prompt("critic_system.md")
    user_prompt = _build_critic_user_prompt(proposed, extracted)

    raw = await _call_json(
        llm,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        temperature=0.2,
        max_tokens=max_tokens,
    )
    try:
        cleaned = _ensure_valid_json(raw)
        return CriticFeedback.model_validate_json(cleaned)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "Critic output failed to parse (%s); treating as 'good' with no issues",
            exc,
        )
        return CriticFeedback(issues=[], overall_quality="good")


# -----------------------------------------------------------------------------
# Refinement + orchestrator


async def refine_with_critic(
    llm: LLMClient,
    initial: ProposedTree,
    feedback: CriticFeedback,
    draft: DraftHierarchy,
    extracted: ExtractedDoc,
    *,
    model: str,
    book_title: str = "Textbook",
    book_subject: str = "general",
) -> ProposedTree:
    """Re-run the Proposer with Critic feedback. If feedback says 'good',
    returns the initial tree unchanged."""
    if feedback.overall_quality == "good" and not feedback.issues:
        return initial
    return await run_proposer(
        llm,
        draft=draft,
        extracted=extracted,
        model=model,
        book_title=book_title,
        book_subject=book_subject,
        prior_feedback=feedback,
    )


async def decompose(
    llm: LLMClient,
    draft: DraftHierarchy,
    extracted: ExtractedDoc,
    *,
    model: str,
    book_title: str = "Textbook",
    book_subject: str = "general",
    max_critic_rounds: int = 1,
) -> ProposedTree:
    """Orchestrate Proposer → Critic → (optional) refinement.

    Returns the final tree after at most one revision pass (MVP).
    """
    logger.info("decompose: running Proposer (model=%s)", model)
    proposed = await run_proposer(
        llm,
        draft=draft,
        extracted=extracted,
        model=model,
        book_title=book_title,
        book_subject=book_subject,
    )

    if max_critic_rounds <= 0:
        return proposed

    logger.info("decompose: running Critic")
    feedback = await run_critic(
        llm, proposed=proposed, extracted=extracted, model=model
    )
    logger.info(
        "decompose: critic returned overall_quality=%s with %d issues",
        feedback.overall_quality,
        len(feedback.issues),
    )

    if feedback.overall_quality == "good" and not feedback.issues:
        return proposed

    logger.info("decompose: running refinement pass")
    return await refine_with_critic(
        llm,
        initial=proposed,
        feedback=feedback,
        draft=draft,
        extracted=extracted,
        model=model,
        book_title=book_title,
        book_subject=book_subject,
    )
