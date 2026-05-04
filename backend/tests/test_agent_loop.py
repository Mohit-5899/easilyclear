"""Tests for the agentic tutor loop (JSON-mode tool decisions, max_steps,
fallback parse, no-tool degrade).

Mocks the LLM so the assertions are deterministic. Each `_ScriptedLLM`
returns the next canned response from a list per `complete()` call.
"""

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

from llm.base import LLMResponse
from tutor.agent import run_agent


SYSTEM_PROMPT = "You are a tutor. Output JSON {action: lookup|answer, ...}"


def _make_book(root: Path) -> None:
    """Build a subject-canonical test tree with enough paragraph diversity
    that BM25 IDF produces non-zero scores."""
    subj = root / "tinysubject"
    subj.mkdir(parents=True)
    (subj / "SKILL.md").write_text(
        "---\nnode_id: tinysubject\nsubject: tinysubject\n---\n## Contents\n"
    )
    chap = subj / "01-chapter"
    chap.mkdir()
    (chap / "SKILL.md").write_text(
        "---\nnode_id: tinysubject/01-chapter\nsubject: tinysubject\n"
        "---\n## Contents\n"
    )

    def _leaf(slug: str, page: int, body: str) -> str:
        return (
            f"---\n"
            f"node_id: tinysubject/01-chapter/{slug}\n"
            f"subject: tinysubject\n"
            f"sources:\n"
            f"  - source_id: 1\n"
            f"    publisher: Test Publisher\n"
            f"    pages: [{page}]\n"
            f"    paragraph_ids: [0, 1]\n"
            f"    authority_rank: 2\n"
            f"---\n"
            f"## Source 1 (page {page})\n\n"
            f"{body}\n"
        )

    (chap / "01-aravali.md").write_text(_leaf(
        "01-aravali", 3,
        "Aravalli is the oldest fold mountain range in India.\n\n"
        "Gurushikhar in Sirohi at 1722 metres is the highest peak.",
    ))
    (chap / "02-rivers.md").write_text(_leaf(
        "02-rivers", 4,
        "Banas is the longest river that drains entirely within Rajasthan.\n\n"
        "Chambal originates in Janapao Hills of Madhya Pradesh.",
    ))
    (chap / "03-climate.md").write_text(_leaf(
        "03-climate", 5,
        "Mawath is winter rainfall caused by western disturbance from the Mediterranean.\n\n"
        "Jaisalmer experiences arid desert climate with very low annual rainfall.",
    ))


class _ScriptedLLM:
    """Returns canned responses one-by-one per call."""

    provider_name = "scripted"

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def complete(self, messages, *, model, temperature=0.3, max_tokens=1024, **kwargs):
        self.calls += 1
        if not self._responses:
            content = '{"action":"answer","text":"(no responses left)"}'
        else:
            content = self._responses.pop(0)
        return LLMResponse(
            content=content, model=model, provider="scripted",
            prompt_tokens=10, completion_tokens=20, raw=None,
        )

    async def stream(self, *args, **kwargs) -> AsyncIterator[str]:
        if False:
            yield ""  # pragma: no cover


def _parse_sse(blob: bytes) -> list[dict]:
    out: list[dict] = []
    for line in blob.decode().splitlines():
        if not line.startswith("data: "):
            continue
        chunk = line.removeprefix("data: ").strip()
        if not chunk or chunk == "[DONE]":
            continue
        try:
            out.append(json.loads(chunk))
        except json.JSONDecodeError:
            pass
    return out


async def _collect(agen: AsyncIterator[bytes]) -> bytes:
    out = bytearray()
    async for chunk in agen:
        out += chunk
    return bytes(out)


def test_agent_lookup_then_answer(tmp_path: Path):
    _make_book(tmp_path)
    llm = _ScriptedLLM([
        # Step 1: look up
        json.dumps({"action": "lookup", "query": "Aravalli oldest", "scope": "all"}),
        # Step 2: answer
        json.dumps({"action": "answer",
                    "text": "Aravalli is the oldest fold mountain in India [1]."}),
    ])
    blob = asyncio.run(_collect(run_agent(
        llm=llm, model="x", skill_root=tmp_path,
        history=[], user_message="What is Aravalli?",
        system_prompt=SYSTEM_PROMPT, max_steps=3, default_scope="all",
    )))
    events = _parse_sse(blob)
    types = [e["type"] for e in events]

    assert types[0] == "start-step"
    assert "tool-call" in types
    assert "tool-result" in types
    assert "data-citation" in types
    assert "text-delta" in types
    assert types[-1] == "finish"
    # Answer text contains the expected substring
    delta_blob = "".join(e["delta"] for e in events if e["type"] == "text-delta")
    assert "Aravalli" in delta_blob


def test_agent_answer_immediately_skips_lookup(tmp_path: Path):
    _make_book(tmp_path)
    llm = _ScriptedLLM([
        json.dumps({"action": "answer", "text": "I already know."}),
    ])
    blob = asyncio.run(_collect(run_agent(
        llm=llm, model="x", skill_root=tmp_path,
        history=[], user_message="say hi",
        system_prompt=SYSTEM_PROMPT, max_steps=3,
    )))
    events = _parse_sse(blob)
    types = [e["type"] for e in events]
    assert "tool-call" not in types
    assert "text-delta" in types


def test_agent_max_steps_force_fallback(tmp_path: Path):
    """If the model keeps lookup-ing without ever answering, the loop must
    bail out gracefully with a fallback message."""
    _make_book(tmp_path)
    # Three lookup responses in a row, max_steps=3 → loop exits without answer.
    llm = _ScriptedLLM([
        json.dumps({"action": "lookup", "query": "x", "scope": "all"}),
        json.dumps({"action": "lookup", "query": "y", "scope": "all"}),
        json.dumps({"action": "lookup", "query": "z", "scope": "all"}),
    ])
    blob = asyncio.run(_collect(run_agent(
        llm=llm, model="x", skill_root=tmp_path,
        history=[], user_message="endless loop",
        system_prompt=SYSTEM_PROMPT, max_steps=3,
    )))
    events = _parse_sse(blob)
    # We should see exactly 3 tool calls then a fallback text-delta + finish.
    tool_calls = [e for e in events if e["type"] == "tool-call"]
    assert len(tool_calls) == 3
    delta = "".join(e["delta"] for e in events if e["type"] == "text-delta")
    assert "couldn't find" in delta.lower() or "couldn't" in delta.lower()
    assert events[-1]["type"] == "finish"


def test_agent_unparseable_response_degrades_to_default_scope(tmp_path: Path):
    """When the model emits prose instead of JSON, Path C kicks in: we run
    a default-scope BM25 with the user's question, surface citations, and
    then ask again for a final answer."""
    _make_book(tmp_path)
    llm = _ScriptedLLM([
        "definitely not json",  # forces degrade path
        json.dumps({"action": "answer",
                    "text": "Aravalli is the oldest mountain [1]."}),
    ])
    blob = asyncio.run(_collect(run_agent(
        llm=llm, model="x", skill_root=tmp_path,
        history=[], user_message="What is Aravalli?",
        system_prompt=SYSTEM_PROMPT, max_steps=3,
    )))
    events = _parse_sse(blob)
    # Degrade path emitted a tool-call with the user message as query
    tool_calls = [e for e in events if e["type"] == "tool-call"]
    assert len(tool_calls) >= 1
    assert tool_calls[0]["args"]["query"] == "What is Aravalli?"
    # Final answer streamed
    delta = "".join(e["delta"] for e in events if e["type"] == "text-delta")
    assert "Aravalli" in delta


def test_agent_inline_tool_tag_fallback_parses(tmp_path: Path):
    """The model wraps its JSON in <|tool_call|> tags — we should still parse it."""
    _make_book(tmp_path)
    llm = _ScriptedLLM([
        '<|tool_call|>{"action":"lookup","query":"Aravalli","scope":"all"}<|tool_call|>',
        json.dumps({"action": "answer", "text": "Aravalli is old [1]."}),
    ])
    blob = asyncio.run(_collect(run_agent(
        llm=llm, model="x", skill_root=tmp_path,
        history=[], user_message="What is Aravalli?",
        system_prompt=SYSTEM_PROMPT, max_steps=3,
    )))
    events = _parse_sse(blob)
    tool_calls = [e for e in events if e["type"] == "tool-call"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["args"]["query"] == "Aravalli"


def test_agent_history_is_preserved_in_messages(tmp_path: Path):
    """Prior conversation should flow through to the LLM call."""
    _make_book(tmp_path)
    captured_messages: list = []

    class _CaptureLLM(_ScriptedLLM):
        async def complete(self, messages, *, model, temperature=0.3, max_tokens=1024, **kwargs):
            captured_messages.append(list(messages))
            return await super().complete(
                messages, model=model, temperature=temperature, max_tokens=max_tokens,
            )

    llm = _CaptureLLM([
        json.dumps({"action": "answer", "text": "ok."}),
    ])
    asyncio.run(_collect(run_agent(
        llm=llm, model="x", skill_root=tmp_path,
        history=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello!"},
        ],
        user_message="follow-up",
        system_prompt=SYSTEM_PROMPT, max_steps=2,
    )))
    assert len(captured_messages) >= 1
    roles = [m.role for m in captured_messages[0]]
    contents = [m.content for m in captured_messages[0]]
    assert roles[0] == "system"
    assert "hi" in contents
    assert "hello!" in contents
    assert "follow-up" in contents
