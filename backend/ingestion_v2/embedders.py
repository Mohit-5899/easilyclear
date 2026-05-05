"""Lightweight embedders for the merge stage.

The production merge stage (ingestion_v2/merge.py) needs an Embedder
implementing ``.encode(text) -> list[float]``. For the hackathon demo we
ship two options:

- ``HashBagEmbedder``  — pure-stdlib, no API cost. Token-level bag-of-words
  hashed into a fixed-dimension dense vector. Quality is good enough to
  catch obvious duplicate leaves (shared title tokens, shared body
  vocabulary) which is what the merge stage needs for cosine ≥ 0.92
  auto-merging. Synonym matching (e.g., "Aravalli range" ↔ "Aravalli
  mountains") falls into the 0.80–0.92 grey zone where the Gemma judge
  can decide.
- (Future) ``BgeEmbedder`` — real semantic embeddings via
  sentence-transformers if we ever decide to add the dep.

For S1 (NCERT Class 11 ingest) the HashBag is the default. It's
deterministic, has no external dependencies, and runs in microseconds per
leaf.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable


_TOKEN_RE = re.compile(r"[a-z][a-z0-9]+")


def _tokenize(text: str) -> Iterable[str]:
    return _TOKEN_RE.findall(text.lower())


class HashBagEmbedder:
    """Project tokens into a fixed-dim sparse-then-densified vector.

    Each token is hashed to a slot in ``[0, dim)`` and accumulated; the
    resulting vector is L2-normalized. Cosine similarity between two
    such vectors approximates Jaccard overlap on the underlying token
    sets, weighted by repetition.

    Stdlib-only: no numpy / no model weights. Deterministic across runs.
    """

    def __init__(self, dim: int = 1024) -> None:
        if dim < 64:
            raise ValueError("dim must be >= 64 to avoid pathological collisions")
        self.dim = dim

    def encode(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in _tokenize(text):
            slot = int(hashlib.blake2s(tok.encode("utf-8"), digest_size=4).hexdigest(), 16) % self.dim
            vec[slot] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0.0:
            return vec
        return [x / norm for x in vec]
