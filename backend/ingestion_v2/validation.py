"""Stage 5 of the V2 pipeline — structural validation.

MVP scope: coverage only. Walks the proposed tree, collects every
referenced paragraph_id, and computes coverage = referenced / total. Full
design also checks sibling cohesion + inter-parent divergence via
embeddings — that's deferred to V2.1.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .extract import ExtractedDoc
from .multi_agent import ProposedNode, ProposedTree


# Coverage threshold for a tree to be considered "OK" enough to ship. Below
# this, we still emit the skill folder but log a warning.
_COVERAGE_OK_THRESHOLD = 0.80


class ValidationResult(BaseModel):
    coverage: float = Field(ge=0.0, le=1.0)
    total_paragraphs: int = Field(ge=0)
    referenced_paragraphs: int = Field(ge=0)
    unreferenced: list[int]
    ok: bool = Field(
        description=f"True if coverage >= {_COVERAGE_OK_THRESHOLD}"
    )


def _collect_paragraph_refs(node: ProposedNode, accumulator: set[int]) -> None:
    """DFS walk. Collect paragraph_refs from every node (leaf or internal)."""
    for ref in node.paragraph_refs:
        accumulator.add(ref)
    for child in node.children:
        _collect_paragraph_refs(child, accumulator)


def validate_coverage(
    tree: ProposedTree, extracted: ExtractedDoc
) -> ValidationResult:
    """Compute paragraph coverage for a proposed tree."""
    total = len(extracted.paragraphs)
    if total == 0:
        return ValidationResult(
            coverage=1.0,
            total_paragraphs=0,
            referenced_paragraphs=0,
            unreferenced=[],
            ok=True,
        )

    referenced: set[int] = set()
    _collect_paragraph_refs(tree.root, referenced)

    all_ids = {p.paragraph_id for p in extracted.paragraphs}
    # Filter referenced to only IDs that actually exist (in case the model
    # hallucinated an ID).
    valid_referenced = referenced & all_ids
    unreferenced = sorted(all_ids - valid_referenced)

    coverage = len(valid_referenced) / total
    return ValidationResult(
        coverage=coverage,
        total_paragraphs=total,
        referenced_paragraphs=len(valid_referenced),
        unreferenced=unreferenced,
        ok=coverage >= _COVERAGE_OK_THRESHOLD,
    )
