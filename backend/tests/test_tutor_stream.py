"""Tests for the AI SDK UI Message Stream writer (spec 2026-05-02-tutor-chat.md)."""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from llm.base import LLMResponse, Message
from tutor.retriever import ParagraphHit
from tutor.stream import stream_tutor_response


class _FakeLLM:
    """Minimal LLMClient that yields canned token deltas."""

    provider_name = "fake"

    def __init__(self, deltas: list[str]) -> None:
        self._deltas = deltas

    async def complete(self, *args, **kwargs) -> LLMResponse:
        raise NotImplementedError

    async def stream(self, messages, *, model, temperature=0.3, max_tokens=1024) -> AsyncIterator[str]:
        for d in self._deltas:
            yield d


def _hit(node_id: str, pid: int, page: int, text: str) -> ParagraphHit:
    return ParagraphHit(
        node_id=node_id, paragraph_id=pid, page=page, snippet=text, score=1.0,
    )


def _parse_sse(events_bytes: bytes) -> list[dict]:
    """Parse our SSE byte stream into a list of JSON event dicts."""
    out: list[dict] = []
    for line in events_bytes.decode().splitlines():
        if line.startswith("data: "):
            chunk = line.removeprefix("data: ").strip()
            if chunk == "[DONE]":
                continue
            out.append(json.loads(chunk))
    return out


async def _collect(agen: AsyncIterator[bytes]) -> bytes:
    out = bytearray()
    async for chunk in agen:
        out += chunk
    return bytes(out)


def test_stream_emits_citations_then_text_deltas():
    llm = _FakeLLM(deltas=["Aravalli ", "is the ", "oldest [1]."])
    hits = [_hit("geo/aravali", 0, 5, "Aravalli is the oldest...")]

    raw = asyncio.run(_collect(stream_tutor_response(
        llm=llm, model="x", messages=[Message(role="user", content="?")], hits=hits,
    )))
    events = _parse_sse(raw)
    types = [e["type"] for e in events]

    # Expect: start-step, then citations, then text-deltas, then finish
    assert types[0] == "start-step"
    assert "data-citation" in types
    assert "text-delta" in types
    assert types[-1] == "finish"


def test_citation_event_carries_node_and_paragraph():
    llm = _FakeLLM(deltas=["x"])
    hits = [_hit("geo/aravali", 7, 12, "snippet body")]

    raw = asyncio.run(_collect(stream_tutor_response(
        llm=llm, model="x", messages=[Message(role="user", content="?")], hits=hits,
    )))
    events = _parse_sse(raw)
    citations = [e for e in events if e["type"] == "data-citation"]
    assert len(citations) == 1
    data = citations[0]["data"]
    assert data["node_id"] == "geo/aravali"
    assert data["paragraph_id"] == 7
    assert data["page"] == 12
    assert data["snippet"] == "snippet body"
    assert data["index"] == 1  # 1-indexed citation marker


def test_text_deltas_carry_id_and_delta():
    llm = _FakeLLM(deltas=["Hello ", "world"])
    raw = asyncio.run(_collect(stream_tutor_response(
        llm=llm, model="x", messages=[Message(role="user", content="?")], hits=[],
    )))
    events = _parse_sse(raw)
    deltas = [e for e in events if e["type"] == "text-delta"]
    assert len(deltas) == 2
    assert deltas[0]["delta"] == "Hello "
    assert deltas[1]["delta"] == "world"
    # Same id across deltas of one text part
    assert deltas[0]["id"] == deltas[1]["id"]


def test_no_hits_skips_citation_events():
    llm = _FakeLLM(deltas=["No sources."])
    raw = asyncio.run(_collect(stream_tutor_response(
        llm=llm, model="x", messages=[Message(role="user", content="?")], hits=[],
    )))
    events = _parse_sse(raw)
    citations = [e for e in events if e["type"] == "data-citation"]
    assert citations == []
    # But text + finish still present
    assert any(e["type"] == "text-delta" for e in events)
    assert events[-1]["type"] == "finish"
