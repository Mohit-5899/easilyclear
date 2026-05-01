"""Context management for the agentic tutor loop.

Implements the patterns from Anthropic's "Effective context engineering for
AI agents" (Sept 2025) adapted to a Gemma-4 + OpenRouter stack where we
don't have access to the native compaction / clear_tool_uses beta. We
re-implement them mechanically:

  * **Tool-result clearing** (free, no LLM call). Replaces older synthetic
    ``TOOL_RESULT (...)`` user messages with a placeholder once the
    conversation has more than ``keep_recent_results`` of them.

  * **Conversation compaction** (one extra Gemma call). When the message
    transcript is estimated above ``compact_token_threshold``, runs a
    summarization prompt that keeps user goals + tool-call decisions and
    discards verbose tool body content. The summary replaces the older
    half of the transcript.

A simple character-based estimator (``estimate_tokens``) approximates the
prompt size. The thresholds default to 8K (clear) and 12K (compact),
leaving headroom on Gemma 4 26B's ~32K input window for the new turn's
TOOL_RESULTs and final completion.

This module is provider-agnostic — it operates on plain
``list[Message]`` objects from ``llm.base``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from llm.base import LLMClient, Message


logger = logging.getLogger(__name__)


# ~4 chars per token is the empirical English rule. Good enough for a
# soft trigger; we don't need exact accuracy.
_CHARS_PER_TOKEN = 4

_TOOL_RESULT_PREFIX = "TOOL_RESULT (lookup_skill_content"
_CLEARED_PLACEHOLDER = (
    "[earlier TOOL_RESULT cleared to save context — re-search if needed]"
)


def estimate_tokens(messages: Iterable[Message]) -> int:
    """Return a rough token estimate for the messages list."""
    total_chars = sum(len(m.content) for m in messages)
    return total_chars // _CHARS_PER_TOKEN


def clear_old_tool_results(
    messages: list[Message], *, keep_recent: int = 3
) -> tuple[list[Message], int]:
    """Replace the body of all but the last ``keep_recent`` TOOL_RESULT
    user messages with a placeholder.

    Anthropic recommends this as the safest, lightest-touch compaction
    technique — old tool outputs are re-fetchable, so dropping their
    bodies costs nothing if the agent needs them again.

    Returns:
        ``(new_messages, cleared_count)``. The ``new_messages`` list is a
        shallow copy with cleared bodies; the original is not mutated.
    """
    # Find indices of TOOL_RESULT messages (always role="user" by our
    # convention in agent.py).
    indices = [
        i for i, m in enumerate(messages)
        if m.role == "user" and m.content.startswith(_TOOL_RESULT_PREFIX)
    ]
    if len(indices) <= keep_recent:
        return list(messages), 0

    to_clear = set(indices[:-keep_recent]) if keep_recent > 0 else set(indices)
    out: list[Message] = []
    for i, m in enumerate(messages):
        if i in to_clear:
            out.append(Message(role=m.role, content=_CLEARED_PLACEHOLDER))
        else:
            out.append(m)
    return out, len(to_clear)


_COMPACT_SYSTEM = (
    "You compress a tutoring conversation so it fits in a smaller context "
    "window. The next turn must be able to continue the conversation as if "
    "the full history were still there.\n\n"
    "Keep:\n"
    "- The user's overall goal and any constraints they stated\n"
    "- Topics already discussed (one short bullet per topic)\n"
    "- The most recent 2 user turns and 1 assistant turn verbatim\n"
    "- Any unresolved follow-up question\n\n"
    "Discard:\n"
    "- Verbose TOOL_RESULT bodies (replace with `(searched and found N hits)`)\n"
    "- Repeated greetings, filler, or meta chatter\n\n"
    "Output a single block of plain text wrapped in <summary>...</summary> "
    "tags. No JSON, no markdown headers. The summary will be inserted as a "
    "single system message in place of the older half of the conversation."
)


async def compact_history(
    messages: list[Message],
    *,
    llm: LLMClient,
    model: str,
    keep_recent_pairs: int = 2,
) -> list[Message]:
    """Summarize the older portion of ``messages`` via one Gemma call.

    Strategy:
      * Always preserve the original system prompt (index 0).
      * Always preserve the last ``keep_recent_pairs`` user/assistant turn
        pairs verbatim.
      * Replace everything in between with a single "system" message
        containing a `<summary>...</summary>` produced by the summarizer.

    Returns the rebuilt messages list. On summarizer failure, returns the
    original list unchanged (graceful degradation).
    """
    if len(messages) <= 1 + keep_recent_pairs * 2:
        return list(messages)

    head = messages[0:1] if messages and messages[0].role == "system" else []
    # Walk from the end, collecting recent user/assistant turns until we
    # have keep_recent_pairs of them.
    tail: list[Message] = []
    pair_count = 0
    for m in reversed(messages[len(head):]):
        tail.insert(0, m)
        if m.role == "user":
            pair_count += 1
            if pair_count >= keep_recent_pairs:
                break

    middle = messages[len(head): len(messages) - len(tail)]
    if not middle:
        return list(messages)

    middle_blob = "\n\n".join(f"[{m.role.upper()}] {m.content}" for m in middle)
    summarizer_messages = [
        Message(role="system", content=_COMPACT_SYSTEM),
        Message(
            role="user",
            content=(
                "Older portion of the conversation to compress:\n\n"
                + middle_blob
                + "\n\nProduce the <summary>...</summary> block now."
            ),
        ),
    ]

    try:
        response = await llm.complete(
            summarizer_messages,
            model=model,
            temperature=0.0,
            max_tokens=800,
        )
    except Exception as exc:  # pragma: no cover - network failure
        logger.warning("compact_history: summarizer call failed: %s", exc)
        return list(messages)

    summary_text = _extract_summary_block(response.content) or response.content.strip()
    summary_message = Message(
        role="system",
        content=f"<conversation_so_far>\n{summary_text}\n</conversation_so_far>",
    )

    rebuilt = head + [summary_message] + tail
    logger.info(
        "compact_history: %d → %d messages (saved ~%d tokens)",
        len(messages), len(rebuilt),
        max(0, estimate_tokens(messages) - estimate_tokens(rebuilt)),
    )
    return rebuilt


_SUMMARY_RE = re.compile(r"<summary>(.*?)</summary>", re.DOTALL | re.IGNORECASE)


def _extract_summary_block(text: str) -> str | None:
    m = _SUMMARY_RE.search(text or "")
    if not m:
        return None
    return m.group(1).strip()


async def manage_context(
    messages: list[Message],
    *,
    llm: LLMClient,
    model: str,
    clear_threshold_tokens: int = 8000,
    compact_threshold_tokens: int = 12000,
    keep_recent_tool_results: int = 3,
) -> list[Message]:
    """Apply tool-result clearing and (optionally) compaction.

    Pipeline:
      1. If estimated tokens >= clear_threshold, clear old TOOL_RESULTs
      2. If estimated tokens still >= compact_threshold, summarize old turns

    Both stages preserve the system prompt and most recent turns.
    """
    out = list(messages)
    tokens = estimate_tokens(out)
    if tokens >= clear_threshold_tokens:
        out, cleared = clear_old_tool_results(
            out, keep_recent=keep_recent_tool_results,
        )
        if cleared:
            logger.info(
                "manage_context: cleared %d old TOOL_RESULT bodies "
                "(was %d tokens)",
                cleared, tokens,
            )
        tokens = estimate_tokens(out)

    if tokens >= compact_threshold_tokens:
        out = await compact_history(out, llm=llm, model=model)

    return out
