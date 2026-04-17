"""Stage 7 of the V2 pipeline — source-preserving content assembly.

Per spec Addendum A.1: skill bodies are verbatim concatenations of the
referenced source paragraphs. No LLM call is made. Only mechanical text
cleanup is applied (whitespace normalization, line-wrap repair). This
preserves the source book's authority for downstream LLMs that will
generate mock tests and tutor answers from this content.

Internal nodes (chapters / subject root) get a deterministic "Contents"
outline of their children. No LLM call.
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from .extract import ExtractedDoc, Paragraph
from .multi_agent import ProposedNode, ProposedTree


logger = logging.getLogger(__name__)


# Regex: a paragraph line that ends with a soft break (no terminal punctuation,
# lowercase character, or a hyphen — classic mid-sentence PDF line-wrap).
_SOFT_BREAK = re.compile(r"(?<=[a-z,;\-])\n(?=[a-z])")

# Regex: 3+ consecutive blank lines collapsed to 2.
_EXCESS_BLANKS = re.compile(r"\n{3,}")


class FilledNode(BaseModel):
    """A proposed node with its assembled markdown body attached."""

    title: str
    description: str
    paragraph_refs: list[int]
    body: str
    source_pages: list[int]
    children: list["FilledNode"] = Field(default_factory=list)


FilledNode.model_rebuild()


class FilledTree(BaseModel):
    root: FilledNode


def _paragraphs_by_id(extracted: ExtractedDoc) -> dict[int, Paragraph]:
    return {p.paragraph_id: p for p in extracted.paragraphs}


def _clean_paragraph_text(text: str) -> str:
    """Mechanical cleanup only. No semantic rewriting.

    - Collapse internal whitespace runs to single space
    - Strip leading/trailing whitespace
    - Rejoin line-wrapped sentences (PDF extraction artifact)
    """
    text = text.strip()
    text = _SOFT_BREAK.sub(" ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text


def _collect_source_paragraphs(
    paragraph_refs: list[int], index: dict[int, Paragraph]
) -> list[Paragraph]:
    """Resolve refs to Paragraph objects in order, skipping unknowns."""
    out: list[Paragraph] = []
    for ref in paragraph_refs:
        para = index.get(ref)
        if para is not None:
            out.append(para)
    return out


def _assemble_leaf_body(paragraphs: list[Paragraph]) -> str:
    """Concatenate paragraph texts verbatim, cleaned, with blank-line separators."""
    if not paragraphs:
        return ""
    cleaned = [_clean_paragraph_text(p.text) for p in paragraphs]
    cleaned = [c for c in cleaned if c]
    body = "\n\n".join(cleaned)
    body = _EXCESS_BLANKS.sub("\n\n", body)
    return body.strip()


def _assemble_internal_body(node: ProposedNode) -> str:
    """Deterministic Contents outline for internal nodes — no source needed."""
    if not node.children:
        return ""
    lines = ["## Contents", ""]
    for child in node.children:
        lines.append(f"- **{child.title}** — {child.description}")
    return "\n".join(lines)


def _derive_source_pages(
    paragraph_refs: list[int], index: dict[int, Paragraph]
) -> list[int]:
    """Unique sorted pages referenced by this node's paragraphs."""
    pages = {
        index[ref].page for ref in paragraph_refs if ref in index
    }
    return sorted(pages)


def _fill_node(
    node: ProposedNode, index: dict[int, Paragraph]
) -> FilledNode:
    """Recursively assemble a FilledNode with verbatim or outline body."""
    is_leaf = not node.children

    if is_leaf:
        paragraphs = _collect_source_paragraphs(node.paragraph_refs, index)
        body = _assemble_leaf_body(paragraphs)
        if not body:
            # Malformed tree guard: no source paragraphs resolved. Keep the
            # description so the .md file isn't empty — but warn loudly.
            logger.warning(
                "fill_content: leaf '%s' has no resolvable source paragraphs "
                "(refs=%s); using description as fallback body",
                node.title, node.paragraph_refs,
            )
            body = node.description
        source_pages = _derive_source_pages(node.paragraph_refs, index)
    else:
        body = _assemble_internal_body(node)
        # Internal node's own source_pages = union of its children's refs.
        all_child_refs: list[int] = []
        for child in node.children:
            all_child_refs.extend(child.paragraph_refs)
        source_pages = _derive_source_pages(all_child_refs, index)

    filled_children = [_fill_node(child, index) for child in node.children]

    return FilledNode(
        title=node.title,
        description=node.description,
        paragraph_refs=node.paragraph_refs,
        body=body,
        source_pages=source_pages,
        children=filled_children,
    )


def fill_content(tree: ProposedTree, extracted: ExtractedDoc) -> FilledTree:
    """Assemble bodies for every node in the tree (deterministic, no LLM).

    Leaves get verbatim source paragraphs. Internal nodes get a Contents
    outline of their children. See spec Addendum A.1.
    """
    logger.info("fill_content: starting (source-preservation, no LLM calls)")
    index = _paragraphs_by_id(extracted)
    filled_root = _fill_node(tree.root, index)
    logger.info("fill_content: done")
    return FilledTree(root=filled_root)
