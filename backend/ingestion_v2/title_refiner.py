"""Stage 6 of the V2 pipeline — title refinement.

The Proposer assigns titles based on its read of the full book, but
occasionally picks paragraph ranges that drift forward by one section
header. The result: a leaf labeled "Lakes" whose actual paragraphs are
about Irrigation. Coverage and structural validators don't catch this
because the tree is structurally valid — only the labels are wrong.

This stage walks every leaf, sends its first ~5 paragraphs to Gemma, and
asks for a title + description that match the actual content. We keep the
Proposer's paragraph ranges (those drive content) and overwrite only the
title and description fields on the FilledNode tree.

Per spec Addendum A.11 — added 2026-05-01 after audit found systematic
shift-by-one mislabeling in the V2.1 Springboard ingestion (mineral leaf
contained energy content, lakes leaf contained irrigation content, etc.).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from llm.base import LLMClient, Message

from ._json_utils import ensure_valid_json
from .extract import ExtractedDoc
from .multi_agent import ProposedNode, ProposedTree


logger = logging.getLogger(__name__)


_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts_v2"

# How many leading paragraphs to send to the title refiner. Enough to
# capture the topic, small enough to keep the prompt cheap.
_PARAGRAPHS_FOR_REFINEMENT = 5

# Per-paragraph char cap when assembling the prompt — keeps token count
# bounded on long-paragraph leaves.
_MAX_CHARS_PER_PARA = 600


class _RefinedLabel(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=400)


def _read_prompt(filename: str) -> str:
    return (_PROMPT_DIR / filename).read_text(encoding="utf-8")


def _leaf_sample_text(
    leaf: ProposedNode, extracted: ExtractedDoc
) -> str:
    """Pull the first N paragraphs of a leaf's range from the source."""
    by_id = {p.paragraph_id: p for p in extracted.paragraphs}
    sample_paras = [
        by_id[pid] for pid in leaf.paragraph_refs[:_PARAGRAPHS_FOR_REFINEMENT]
        if pid in by_id
    ]
    lines: list[str] = []
    for p in sample_paras:
        text = p.text
        if len(text) > _MAX_CHARS_PER_PARA:
            text = text[:_MAX_CHARS_PER_PARA].rstrip() + " [...]"
        lines.append(f"- {text}")
    return "\n".join(lines)


async def _refine_one(
    llm: LLMClient,
    *,
    model: str,
    proposer_title: str,
    proposer_description: str,
    sample_text: str,
) -> _RefinedLabel:
    """Ask the LLM to (re)write title + description for one leaf."""
    system = _read_prompt("title_refiner_system.md")
    user = (
        f"## Proposer-assigned label (may be wrong)\n\n"
        f"- Title: {proposer_title}\n"
        f"- Description: {proposer_description}\n\n"
        f"## Actual first paragraphs of this leaf\n\n"
        f"{sample_text}\n\n"
        f"Now emit the refined title + description as JSON."
    )
    messages = [
        Message(role="system", content=system),
        Message(role="user", content=user),
    ]
    try:
        response = await llm.complete(
            messages,
            model=model,
            temperature=0.1,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
    except TypeError:
        response = await llm.complete(
            messages, model=model, temperature=0.1, max_tokens=400,
        )
    cleaned = ensure_valid_json(response.content)
    return _RefinedLabel.model_validate_json(cleaned)


def _walk_leaves(node: ProposedNode, out: list[ProposedNode]) -> None:
    if not node.children:
        out.append(node)
        return
    for child in node.children:
        _walk_leaves(child, out)


async def refine_titles(
    llm: LLMClient,
    *,
    tree: ProposedTree,
    extracted: ExtractedDoc,
    model: str,
) -> ProposedTree:
    """Walk every leaf and overwrite its title + description in-place.

    Internal (non-leaf) nodes keep their Proposer-assigned labels — those
    describe a chapter's intent rather than a specific paragraph range, so
    they're more reliably correct.

    Runs BEFORE fill_content so internal-node "Contents" outlines pick up
    the refined leaf titles.

    Returns the same ProposedTree (mutated). On per-leaf failure, leaves
    the Proposer label intact and logs a warning.
    """
    leaves: list[ProposedNode] = []
    _walk_leaves(tree.root, leaves)
    return await _refine_tree_leaves(
        llm, leaves=leaves, extracted=extracted, model=model, tree=tree,
    )


async def _refine_tree_leaves(
    llm: LLMClient,
    *,
    leaves: list[ProposedNode],
    extracted: ExtractedDoc,
    model: str,
    tree: ProposedTree,
) -> ProposedTree:
    refined_count = 0
    failed_count = 0
    for leaf in leaves:
        sample_text = _leaf_sample_text(leaf, extracted)
        if not sample_text.strip():
            continue
        try:
            label = await _refine_one(
                llm,
                model=model,
                proposer_title=leaf.title,
                proposer_description=leaf.description,
                sample_text=sample_text,
            )
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            failed_count += 1
            logger.warning(
                "title_refiner: leaf %r refinement failed (%s); keeping original",
                leaf.title, exc,
            )
            continue
        # Deliberate in-place mutation: the ProposedTree is owned exclusively
        # by the pipeline at this stage (no other coroutine holds it), and
        # rebuilding the whole tree just to swap two strings would add
        # ~30 lines without a real safety win. See spec Addendum A.11.
        old_title = leaf.title
        leaf.title = label.title.strip()
        leaf.description = label.description.strip()
        refined_count += 1
        if old_title != leaf.title:
            logger.info(
                "title_refiner: %r -> %r", old_title, leaf.title,
            )

    logger.info(
        "title_refiner: refined %d leaves, %d failed",
        refined_count, failed_count,
    )
    return tree
