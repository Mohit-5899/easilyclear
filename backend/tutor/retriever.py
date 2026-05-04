"""BM25 retriever scoped to a node's subtree (spec 2026-05-02-tutor-chat.md).

Reads emitted skill folder Markdown, splits each leaf body into paragraphs,
indexes with BM25Okapi, returns top-k matches as ParagraphHit objects.

Per CLAUDE.md "use what we have": frontmatter parsed via python-frontmatter
(already a dependency), tokenization via simple lowercase + word-split (no
extra NLP dep). For a hackathon corpus of <2K paragraphs per book, this is
plenty.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import frontmatter
from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi


logger = logging.getLogger(__name__)


# Word-character tokenizer. BM25Okapi expects pre-tokenized lists of strings.
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Paragraph splitter: blank-line boundary, same as ingestion_v2.extract.
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")

# Snippet cap when surfacing back to the chat prompt.
_SNIPPET_CHARS = 600


class ParagraphHit(BaseModel):
    """One BM25 hit on a paragraph somewhere in the indexed subtree."""

    node_id: str
    paragraph_id: int = Field(ge=0)
    page: int = Field(ge=1)
    snippet: str
    score: float


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Retriever:
    """In-memory BM25 over a flat list of paragraph dicts."""

    def __init__(self, paragraphs: list[dict]) -> None:
        """Build the BM25 index.

        Args:
            paragraphs: list of dicts with keys ``node_id``, ``paragraph_id``,
                ``page``, ``text``. Order is preserved as document order.
        """
        self._paragraphs = list(paragraphs)
        if not self._paragraphs:
            self._bm25 = None
            return
        tokenized = [_tokenize(p["text"]) for p in self._paragraphs]
        self._bm25 = BM25Okapi(tokenized)

    def search(self, query: str, k: int = 3) -> list[ParagraphHit]:
        """Return the top-k paragraphs by BM25 relevance to ``query``.

        Hits with score == 0 are filtered out (BM25Okapi ranks all docs even
        when no terms match).
        """
        if not self._paragraphs or self._bm25 is None:
            return []
        if not query.strip():
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        # Pair (score, idx), take top-k positive scores.
        ranked = sorted(
            ((float(s), i) for i, s in enumerate(scores) if s > 0),
            key=lambda t: t[0],
            reverse=True,
        )[:k]

        hits: list[ParagraphHit] = []
        for score, idx in ranked:
            p = self._paragraphs[idx]
            text = p["text"]
            snippet = (
                text if len(text) <= _SNIPPET_CHARS
                else text[:_SNIPPET_CHARS].rstrip() + " […]"
            )
            hits.append(
                ParagraphHit(
                    node_id=p["node_id"],
                    paragraph_id=int(p["paragraph_id"]),
                    page=int(p["page"]),
                    snippet=snippet,
                    score=score,
                )
            )
        return hits


def _walk_leaf_files(folder: Path, node_id_prefix: str) -> list[Path]:
    """Return all leaf .md files (not SKILL.md) under ``folder``."""
    out: list[Path] = []
    for path in folder.rglob("*.md"):
        if path.name == "SKILL.md":
            continue
        out.append(path)
    return out


def _parse_leaf_paragraphs(path: Path) -> list[dict]:
    """Parse one leaf .md → list of paragraph dicts.

    Each leaf file contains one body of verbatim source paragraphs separated
    by blank lines. We split on those, assign a sequential paragraph_id
    scoped to this leaf (counter starts at 0 per leaf — fine for retrieval
    since we surface node_id + paragraph_id together as the citation key).
    """
    post = frontmatter.load(path)
    node_id = str(post.metadata.get("node_id", ""))
    # New v3 schema: pages live in sources[].pages. Legacy v2 schema:
    # source_pages at top level. Try v3 first, fall back to v2.
    pages: list[int] = []
    sources = post.metadata.get("sources")
    if isinstance(sources, list) and sources:
        for s in sources:
            if isinstance(s, dict) and isinstance(s.get("pages"), list):
                pages.extend(int(p) for p in s["pages"] if isinstance(p, int))
    if not pages:
        legacy_pages = post.metadata.get("source_pages") or [1]
        if isinstance(legacy_pages, list):
            pages = [int(p) for p in legacy_pages if isinstance(p, int)]
    page = pages[0] if pages else 1

    paragraphs: list[dict] = []
    paragraph_id = 0
    for chunk in _PARAGRAPH_SPLIT.split(post.content):
        text = chunk.strip()
        if len(text) < 20:
            continue
        # Skip the v3 source-section headers — they're chrome, not content.
        if text.startswith("## Source ") or text.startswith("# Source "):
            continue
        paragraphs.append(
            {
                "node_id": node_id,
                "paragraph_id": paragraph_id,
                "page": page,
                "text": text,
            }
        )
        paragraph_id += 1
    return paragraphs


def build_retriever_for_node(
    skill_root: Path, node_id: str
) -> BM25Retriever:
    """Walk the skill folder, load paragraphs from every leaf under
    ``node_id``, build a BM25 retriever scoped to that subtree.

    Args:
        skill_root: filesystem root containing skill folders. Per project
            convention this is ``database/skills/``.
        node_id: e.g. ``"geography/test_book/01-chapter"``. The retriever
            indexes only leaves whose own node_id starts with this string.
    """
    if not skill_root.is_dir():
        raise FileNotFoundError(f"skill_root does not exist: {skill_root}")

    # node_id maps to a folder via path components.
    parts = node_id.split("/")
    target = skill_root.joinpath(*parts)
    if not target.exists():
        # node_id may identify a leaf .md instead of a folder.
        leaf_md = target.with_suffix(".md")
        if leaf_md.is_file():
            return BM25Retriever(_parse_leaf_paragraphs(leaf_md))
        raise FileNotFoundError(
            f"no folder or .md found for node_id={node_id!r} under {skill_root}"
        )

    all_paragraphs: list[dict] = []
    for leaf_path in _walk_leaf_files(target, node_id):
        try:
            all_paragraphs.extend(_parse_leaf_paragraphs(leaf_path))
        except (OSError, ValueError) as exc:
            logger.warning(
                "retriever: skipping leaf %s (%s: %s)",
                leaf_path, type(exc).__name__, exc,
            )
    return BM25Retriever(all_paragraphs)
