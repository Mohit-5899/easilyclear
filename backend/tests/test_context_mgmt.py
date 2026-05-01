"""Tests for context management utilities (clearing + compaction)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from llm.base import LLMResponse, Message
from tutor.context_mgmt import (
    clear_old_tool_results,
    compact_history,
    estimate_tokens,
    manage_context,
)


# ---------- estimate_tokens ----------


def test_estimate_tokens_uses_4_chars_per_token():
    msgs = [
        Message(role="user", content="x" * 400),
        Message(role="user", content="x" * 800),
    ]
    # 1200 chars / 4 = 300 tokens
    assert estimate_tokens(msgs) == 300


def test_estimate_tokens_empty():
    assert estimate_tokens([]) == 0


# ---------- clear_old_tool_results ----------


def _tool_result(idx: int) -> Message:
    return Message(
        role="user",
        content=(
            f"TOOL_RESULT (lookup_skill_content, scope=all)\n"
            f"[1] (page {idx}) very long body of paragraph " + ("x" * 200)
        ),
    )


def test_clear_old_tool_results_keeps_recent():
    msgs = [
        Message(role="system", content="sys"),
        Message(role="user", content="hi"),
        _tool_result(1),
        Message(role="assistant", content="answer 1"),
        Message(role="user", content="next?"),
        _tool_result(2),
        _tool_result(3),
        Message(role="assistant", content="answer 2"),
    ]
    new, cleared = clear_old_tool_results(msgs, keep_recent=1)
    assert cleared == 2  # 2 of 3 TOOL_RESULTs cleared
    # The most recent tool_result preserved (it's at index -2; -1 is the
    # final assistant message)
    assert new[-2].content.startswith("TOOL_RESULT")
    assert "page 3" in new[-2].content
    # Earlier ones replaced with placeholder
    placeholder_count = sum(
        1 for m in new
        if m.content.startswith("[earlier TOOL_RESULT cleared")
    )
    assert placeholder_count == 2


def test_clear_old_tool_results_below_keep_is_noop():
    msgs = [
        Message(role="user", content="hi"),
        _tool_result(1),
        Message(role="assistant", content="ans"),
    ]
    new, cleared = clear_old_tool_results(msgs, keep_recent=3)
    assert cleared == 0
    assert new[1].content.startswith("TOOL_RESULT")


def test_clear_old_tool_results_does_not_mutate_input():
    original = [_tool_result(1), _tool_result(2), _tool_result(3)]
    snapshot = [m.content for m in original]
    clear_old_tool_results(original, keep_recent=1)
    assert [m.content for m in original] == snapshot


# ---------- compact_history ----------


class _FakeSummarizerLLM:
    """Returns a canned summary on the next .complete() call."""

    provider_name = "fake"

    def __init__(self, summary: str = "Default summary text.") -> None:
        self._summary = summary
        self.calls = 0

    async def complete(self, messages, *, model, temperature=0.0, max_tokens=800, **kw):
        self.calls += 1
        content = f"<summary>{self._summary}</summary>"
        return LLMResponse(
            content=content, model=model, provider="fake",
            prompt_tokens=10, completion_tokens=20, raw=None,
        )

    async def stream(self, *args, **kwargs):
        raise NotImplementedError


def test_compact_history_replaces_middle_with_summary():
    msgs = [
        Message(role="system", content="agent system prompt"),
        Message(role="user", content="What is Aravalli?"),
        Message(role="assistant", content="Aravalli is..."),
        Message(role="user", content="Tell me about climate"),
        Message(role="assistant", content="Climate of Rajasthan..."),
        Message(role="user", content="And rivers?"),
        Message(role="assistant", content="Rivers of Rajasthan..."),
        Message(role="user", content="Latest follow-up?"),
    ]
    llm = _FakeSummarizerLLM("user explored Aravalli, climate, rivers")
    rebuilt = asyncio.run(compact_history(
        msgs, llm=llm, model="m", keep_recent_pairs=1,
    ))
    # System prompt preserved at index 0
    assert rebuilt[0].role == "system"
    assert rebuilt[0].content == "agent system prompt"
    # Summary block injected as second message
    assert rebuilt[1].role == "system"
    assert "user explored Aravalli" in rebuilt[1].content
    # Last 1 user/assistant pair preserved (since keep_recent_pairs=1)
    assert rebuilt[-1].content == "Latest follow-up?"
    # Original is shorter
    assert len(rebuilt) < len(msgs)
    # LLM called exactly once
    assert llm.calls == 1


def test_compact_history_short_conversation_is_noop():
    """If we only have system + user + answer + user, nothing to compact."""
    msgs = [
        Message(role="system", content="sys"),
        Message(role="user", content="hi"),
        Message(role="assistant", content="hello"),
        Message(role="user", content="next?"),
    ]
    llm = _FakeSummarizerLLM()
    rebuilt = asyncio.run(compact_history(msgs, llm=llm, model="m"))
    assert len(rebuilt) == len(msgs)
    assert llm.calls == 0


def test_compact_history_falls_back_on_summarizer_error():
    """If the summarizer call raises, return original messages unchanged."""
    msgs = [Message(role="user", content="x" * 100) for _ in range(8)]
    msgs.insert(0, Message(role="system", content="sys"))

    class _BrokenLLM:
        provider_name = "broken"

        async def complete(self, *args, **kwargs):
            raise RuntimeError("boom")

        async def stream(self, *args, **kwargs):
            raise NotImplementedError

    rebuilt = asyncio.run(compact_history(
        msgs, llm=_BrokenLLM(), model="m",
    ))
    assert rebuilt == msgs


# ---------- manage_context ----------


def test_manage_context_short_conversation_passes_through():
    """Below clear/compact thresholds, messages come back unchanged."""
    msgs = [
        Message(role="system", content="sys"),
        Message(role="user", content="hi"),
        Message(role="assistant", content="hello"),
        Message(role="user", content="next?"),
    ]
    llm = _FakeSummarizerLLM()
    out = asyncio.run(manage_context(
        msgs, llm=llm, model="m",
        clear_threshold_tokens=8000,
        compact_threshold_tokens=12000,
    ))
    assert out == msgs
    assert llm.calls == 0


def test_manage_context_clears_when_threshold_met():
    """Low clear threshold triggers tool-result clearing without compaction."""
    msgs = [
        Message(role="system", content="sys"),
        Message(role="user", content="hi"),
        _tool_result(1),
        Message(role="assistant", content="ans1"),
        Message(role="user", content="next?"),
        _tool_result(2),
        Message(role="assistant", content="ans2"),
        Message(role="user", content="more?"),
        _tool_result(3),
    ]
    llm = _FakeSummarizerLLM()
    out = asyncio.run(manage_context(
        msgs, llm=llm, model="m",
        clear_threshold_tokens=10,        # always trigger clearing
        compact_threshold_tokens=999_999, # never compact
        keep_recent_tool_results=1,
    ))
    placeholder_count = sum(
        1 for m in out if m.content.startswith("[earlier TOOL_RESULT cleared")
    )
    assert placeholder_count == 2
    assert llm.calls == 0  # no compaction call


def test_manage_context_compacts_when_threshold_met():
    """Low compact threshold (after clearing fails to bring under) triggers
    summarization."""
    msgs = [Message(role="system", content="sys")]
    for i in range(10):
        msgs.append(Message(role="user", content=f"q{i} " + "x" * 200))
        msgs.append(Message(role="assistant", content=f"a{i} " + "x" * 200))

    llm = _FakeSummarizerLLM("compressed history of q0..q9")
    out = asyncio.run(manage_context(
        msgs, llm=llm, model="m",
        clear_threshold_tokens=999_999,   # skip clearing
        compact_threshold_tokens=10,      # always compact
    ))
    # System preserved + summary block inserted + recent tail
    assert out[0].role == "system"
    assert out[0].content == "sys"
    assert any("compressed history" in m.content for m in out)
    assert llm.calls == 1
    assert len(out) < len(msgs)
