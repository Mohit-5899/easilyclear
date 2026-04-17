"""Stage 7 of the V2 pipeline — content filling.

Walks the proposed tree DFS. For each node, calls Gemma with the content
writer prompt and the referenced source paragraphs, then stores the
generated markdown body + derived source_pages on the node.

One LLM call per node. Errors on a single node fall back to using the
node's description as the body — the pipeline never fails because of one
bad LLM call.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from llm.base import LLMClient, Message

from .extract import ExtractedDoc, Paragraph
from .multi_agent import ProposedNode, ProposedTree


logger = logging.getLogger(__name__)


_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts_v2"


# Max referenced-paragraph text length we'll stuff into a single content-writer
# call. Guards against sending a whole book to write one leaf when the tree
# accidentally over-assigns paragraphs to a single node.
_MAX_SOURCE_CHARS = 20_000


class FilledNode(BaseModel):
    """A proposed node with its generated markdown body attached."""

    title: str
    description: str
    paragraph_refs: list[int]
    body: str
    source_pages: list[int]
    children: list["FilledNode"] = Field(default_factory=list)


FilledNode.model_rebuild()


class FilledTree(BaseModel):
    root: FilledNode


def _read_prompt(filename: str) -> str:
    return (_PROMPT_DIR / filename).read_text(encoding="utf-8")


def _paragraphs_by_id(extracted: ExtractedDoc) -> dict[int, Paragraph]:
    return {p.paragraph_id: p for p in extracted.paragraphs}


def _gather_source_text(
    paragraph_refs: list[int], index: dict[int, Paragraph]
) -> str:
    """Join referenced paragraphs into one source block, truncating if huge."""
    chunks: list[str] = []
    total = 0
    for ref in paragraph_refs:
        para = index.get(ref)
        if para is None:
            continue
        piece = f"[p.{para.page}] {para.text}"
        if total + len(piece) > _MAX_SOURCE_CHARS:
            chunks.append("\n\n[... additional source content truncated ...]")
            break
        chunks.append(piece)
        total += len(piece) + 2
    return "\n\n".join(chunks)


def _derive_source_pages(
    paragraph_refs: list[int], index: dict[int, Paragraph]
) -> list[int]:
    """Unique sorted pages referenced by this node's paragraphs."""
    pages: set[int] = set()
    for ref in paragraph_refs:
        para = index.get(ref)
        if para is not None:
            pages.add(para.page)
    return sorted(pages)


def _build_user_prompt(
    node: ProposedNode, is_leaf: bool, source_text: str
) -> str:
    role = "leaf sub-topic" if is_leaf else "chapter / internal node"
    length_hint = (
        "200–600 words" if is_leaf else "100–300 word overview"
    )
    return (
        f"## Skill node\n\n"
        f"- Title: {node.title}\n"
        f"- Description: {node.description}\n"
        f"- Role: {role}\n"
        f"- Target length: {length_hint}\n\n"
        f"## Source paragraphs\n\n"
        f"{source_text if source_text else '(none — write from the description only; keep it short)'}\n\n"
        f"Write the markdown body now. No frontmatter, no title header — just the body."
    )


async def _write_node_body(
    llm: LLMClient,
    node: ProposedNode,
    is_leaf: bool,
    source_text: str,
    system_prompt: str,
    model: str,
    max_tokens: int,
) -> str:
    """Single LLM call to produce the body for one node. Errors fall back
    to the node's description."""
    try:
        user_prompt = _build_user_prompt(node, is_leaf, source_text)
        response = await llm.complete(
            messages=[
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_prompt),
            ],
            model=model,
            temperature=0.3,
            max_tokens=max_tokens,
        )
        body = response.content.strip()
        if not body:
            logger.warning(
                "Content writer returned empty body for '%s'; using description fallback",
                node.title,
            )
            return node.description
        return body
    except Exception as exc:  # pragma: no cover - network/provider errors
        logger.warning(
            "Content writer failed for '%s' (%s: %s); using description fallback",
            node.title,
            type(exc).__name__,
            exc,
        )
        return node.description


async def _fill_node(
    llm: LLMClient,
    node: ProposedNode,
    index: dict[int, Paragraph],
    system_prompt: str,
    model: str,
    max_tokens: int,
) -> FilledNode:
    """Recursively fill content for one node and its descendants."""
    is_leaf = len(node.children) == 0

    if not node.paragraph_refs and not is_leaf:
        # Internal node without its own refs — gather children's refs as
        # proxy source for the overview.
        proxied: list[int] = []
        for child in node.children:
            proxied.extend(child.paragraph_refs)
        # Deduplicate + cap to avoid overflowing the context with the whole
        # chapter just to write a 200-word overview.
        proxied = list(dict.fromkeys(proxied))[:30]
        source_text = _gather_source_text(proxied, index)
        source_pages = _derive_source_pages(proxied, index)
    else:
        source_text = _gather_source_text(node.paragraph_refs, index)
        source_pages = _derive_source_pages(node.paragraph_refs, index)

    if not node.paragraph_refs and is_leaf:
        # Guard against a malformed tree: empty leaf → use description as body.
        body = node.description
    else:
        body = await _write_node_body(
            llm=llm,
            node=node,
            is_leaf=is_leaf,
            source_text=source_text,
            system_prompt=system_prompt,
            model=model,
            max_tokens=max_tokens,
        )

    filled_children: list[FilledNode] = []
    for child in node.children:
        filled_children.append(
            await _fill_node(
                llm=llm,
                node=child,
                index=index,
                system_prompt=system_prompt,
                model=model,
                max_tokens=max_tokens,
            )
        )

    return FilledNode(
        title=node.title,
        description=node.description,
        paragraph_refs=node.paragraph_refs,
        body=body,
        source_pages=source_pages,
        children=filled_children,
    )


async def fill_content(
    llm: LLMClient,
    tree: ProposedTree,
    extracted: ExtractedDoc,
    *,
    model: str,
    max_tokens: int = 1600,
) -> FilledTree:
    """Generate markdown bodies for every node in the tree.

    Returns a FilledTree whose structure mirrors the input but with body +
    source_pages populated on each node.
    """
    index = _paragraphs_by_id(extracted)
    system_prompt = _read_prompt("content_writer_system.md")
    logger.info("fill_content: starting DFS fill")
    filled_root = await _fill_node(
        llm=llm,
        node=tree.root,
        index=index,
        system_prompt=system_prompt,
        model=model,
        max_tokens=max_tokens,
    )
    logger.info("fill_content: done")
    return FilledTree(root=filled_root)
