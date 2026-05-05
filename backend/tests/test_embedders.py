"""Tests for ingestion_v2/embedders.py."""

from __future__ import annotations

import sys
from pathlib import Path

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import pytest

from ingestion_v2.dedup import cosine
from ingestion_v2.embedders import HashBagEmbedder


def test_identical_text_self_similarity_is_one():
    e = HashBagEmbedder()
    v = e.encode("Aravalli is the oldest fold mountain range.")
    assert abs(cosine(v, v) - 1.0) < 1e-9


def test_disjoint_topics_have_low_similarity():
    e = HashBagEmbedder()
    a = e.encode("Aravalli Mountain Range\n\nThe Aravalli is in Rajasthan.")
    b = e.encode("Pushkar Lake Festival\n\nHeld annually in Kartik month.")
    assert cosine(a, b) < 0.30


def test_shared_topic_higher_than_disjoint():
    e = HashBagEmbedder()
    aravalli_a = e.encode("Aravalli Range\n\nThe Aravalli is the oldest fold "
                          "mountain range in India.")
    aravalli_b = e.encode("Aravalli Range\n\nAravalli range stretches from "
                          "Gujarat to Delhi.")
    thar = e.encode("Thar Desert\n\nThe Thar is a hot desert.")
    assert cosine(aravalli_a, aravalli_b) > cosine(aravalli_a, thar)


def test_empty_text_returns_zero_vector():
    e = HashBagEmbedder()
    v = e.encode("")
    assert all(x == 0.0 for x in v)
    assert len(v) == e.dim


def test_dim_validation():
    with pytest.raises(ValueError):
        HashBagEmbedder(dim=8)


def test_deterministic_across_calls():
    e1 = HashBagEmbedder()
    e2 = HashBagEmbedder()
    text = "Same text, different instances."
    assert e1.encode(text) == e2.encode(text)
