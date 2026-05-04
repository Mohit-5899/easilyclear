"""Agentic tutor — JSON-mode tool loop over Gemma 4 26B.

Per docs/research/2026-05-02-ux-redesign-architecture.md §3:
  - Path A (primary): JSON-mode tool decision via ``response_format={"type":
    "json_object"}``
  - Path B (fallback): inline ``<|tool_call|>{...}<|tool_call|>`` regex
    parse if JSON-mode misfires
  - Path C (degrade): no-tool BM25 + answer if both fail twice

Step budget: 3 (default). Stream events emitted match the AI SDK UI Message
Stream protocol with two new event types layered on:
  - ``tool-call``    {id, name, args}
  - ``tool-result``  {id, hit_count, scope_label}

Multi-turn history is purely in-memory in this agent loop — the FastAPI
endpoint is responsible for stitching together prior conversation turns
from the client request.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from llm.base import LLMClient, Message

from .context_mgmt import manage_context
from .retriever import ParagraphHit
from .scope import Scope, build_retriever_for_scope, scope_label


logger = logging.getLogger(__name__)


_INLINE_TOOL_RE = re.compile(
    r"<\|tool_call\|>(.*?)<\|?/?tool_call\|?>", re.DOTALL,
)


class LookupArgs(BaseModel):
    query: str
    scope: Scope = "all"
    book_slug: str | None = None
    node_id: str | None = None


class _ToolDecision(BaseModel):
    action: Literal["lookup", "answer"]
    query: str | None = None
    scope: Scope | None = None
    book_slug: str | None = None
    node_id: str | None = None
    text: str | None = None


def _sse(event: dict) -> bytes:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")


def _parse_decision(raw: str) -> _ToolDecision | None:
    """Try strict JSON first; fall back to inline ``<|tool_call|>`` block."""
    candidate = raw.strip()
    # Strip code fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```\s*$", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()
    try:
        return _ToolDecision.model_validate_json(candidate)
    except (ValidationError, json.JSONDecodeError):
        pass

    # Inline tool-call tag fallback.
    m = _INLINE_TOOL_RE.search(raw)
    if m:
        try:
            return _ToolDecision.model_validate_json(m.group(1))
        except (ValidationError, json.JSONDecodeError):
            pass
    return None


def _node_trail_from_node_id(node_id: str) -> str:
    """Drop the leading subject segment to leave just chapter/leaf trail.

    Per spec 2026-05-04 the node_id is now ``<subject>/<chapter>/<leaf>``
    (no book slug). Returns the part after the subject for compact display.
    """
    parts = node_id.split("/")
    return "/".join(parts[1:]) if len(parts) > 1 else node_id


def _format_tool_result_message(
    scope_str: str, hits: list[ParagraphHit]
) -> str:
    """Render TOOL_RESULT lines for the agent.

    Brand-stripping rule (spec 2026-05-04): NO publisher names in the
    message. The model only sees ``[N] path='...' page=...`` plus the
    snippet. Source attribution lives in the leaf's frontmatter, never
    surfaced to the LLM.
    """
    if not hits:
        return f"TOOL_RESULT (lookup_skill_content, scope={scope_str})\n(no hits)"
    lines = [f"TOOL_RESULT (lookup_skill_content, scope={scope_str})"]
    for idx, h in enumerate(hits, start=1):
        trail = _node_trail_from_node_id(h.node_id)
        lines.append(
            f"[{idx}] path={trail!r} page={h.page}\n"
            f"    {h.snippet}"
        )
    return "\n".join(lines)


async def _call_decision(
    llm: LLMClient,
    *,
    model: str,
    messages: list[Message],
    max_tokens: int = 1024,
) -> str:
    """Call the LLM in JSON-mode (with TypeError fallback for clients
    that don't accept response_format)."""
    try:
        response = await llm.complete(
            messages,
            model=model,
            temperature=0.2,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
    except TypeError:
        response = await llm.complete(
            messages, model=model, temperature=0.2, max_tokens=max_tokens,
        )
    return response.content


async def run_agent(
    *,
    llm: LLMClient,
    model: str,
    skill_root: Path,
    history: list[dict[str, str]],
    user_message: str,
    system_prompt: str,
    max_steps: int = 4,
    top_k: int = 8,
    default_scope: Scope = "all",
    default_subject_slug: str | None = None,
) -> AsyncIterator[bytes]:
    """Drive the JSON-mode tool loop and emit SSE events.

    Args:
        llm: any LLMClient — JSON-mode is preferred, TypeError fallback works.
        model: provider slug.
        skill_root: filesystem root for skill folders.
        history: prior chat turns as ``[{"role": ..., "content": ...}]``.
            Should NOT include the new user message — pass that via
            ``user_message`` so the agent can compose the loop cleanly.
        user_message: the new question.
        system_prompt: contents of ``prompts_v2/agent_chat_system.md``.
        max_steps: cap on lookup/answer turns. Default 3.
        top_k: how many hits to surface per lookup.
        default_scope: scope to use when the model omits ``scope``.
        default_subject_slug: which subject to use when the model picks
            scope=subject without naming one.

    Emits SSE events in order:
        start-step → (tool-call → tool-result → data-citation × N)*
                  → text-start → text-delta × N → text-end → finish → [DONE]
    """
    yield _sse({"type": "start-step"})

    # Build messages: system, then prior history, then new user.
    msgs: list[Message] = [Message(role="system", content=system_prompt)]
    for turn in history:
        role = turn.get("role")
        if role not in {"user", "assistant"}:
            continue
        msgs.append(Message(role=role, content=str(turn.get("content", ""))))
    msgs.append(Message(role="user", content=user_message))

    # Stage 0 — context management (Anthropic context-engineering pattern):
    # clear stale tool results, optionally compact older turns. Cheap when
    # the conversation is short; pays for itself on long threads.
    msgs = await manage_context(msgs, llm=llm, model=model)

    # Track all hits accumulated across the loop so the final text-delta can
    # reference them by their stable [N] index.
    accumulated: list[ParagraphHit] = []
    text_id = f"t-{uuid.uuid4().hex[:8]}"
    answered = False

    # Loop guard — block near-duplicate queries from causing wasted steps.
    seen_query_keys: set[str] = set()

    for step in range(1, max_steps + 1):
        raw = await _call_decision(llm, model=model, messages=msgs)
        decision = _parse_decision(raw)

        if decision is None:
            logger.warning("agent: step %d failed to parse JSON: %r", step, raw[:200])
            # Path C degrade — bail out and use default scope to fetch
            # something so the user still gets an answer.
            yield _sse({"type": "tool-call", "id": f"tc{step}",
                        "name": "lookup_skill_content",
                        "args": {"query": user_message, "scope": default_scope}})
            try:
                retriever = build_retriever_for_scope(
                    skill_root, default_scope, subject_slug=default_subject_slug,
                )
                hits = retriever.search(user_message, k=top_k)
            except (FileNotFoundError, ValueError) as exc:
                logger.warning("agent: degrade-path retrieval failed: %s", exc)
                hits = []
            label = scope_label(skill_root, default_scope,
                                subject_slug=default_subject_slug)
            yield _sse({"type": "tool-result", "id": f"tc{step}",
                        "hit_count": len(hits), "scope_label": label})
            for i, h in enumerate(hits, start=len(accumulated) + 1):
                yield _sse(_citation_event(i, h))
            accumulated.extend(hits)
            # Force a final-answer step next.
            msgs.append(Message(
                role="user",
                content=_format_tool_result_message(default_scope, hits)
                + "\n\nNow emit an `action=answer` JSON object using these sources.",
            ))
            continue

        if decision.action == "lookup":
            scope = decision.scope or default_scope
            # Pydantic ToolDecision still names the field ``book_slug`` for
            # wire compat with older saved threads — treat it as subject_slug.
            subject_slug = decision.book_slug or default_subject_slug
            query = decision.query or ""

            # Loop guard: dedupe near-identical queries via tokenized
            # signature (lowercase word set). If the same set has been
            # seen this turn, replace the result with a hint to broaden.
            qkey = " ".join(sorted({w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2}))
            if qkey and qkey in seen_query_keys:
                logger.info("agent: blocking duplicate query %r", query)
                msgs.append(Message(
                    role="user",
                    content=(
                        f"TOOL_RESULT (lookup_skill_content, scope={scope})\n"
                        "(duplicate query — already searched these keywords. "
                        "Try DIFFERENT specific keywords: named entities "
                        "from the topic, district names, MW capacities, "
                        "act names, year numbers. Or answer with what you "
                        "have using the [N] markers from earlier hits.)"
                    ),
                ))
                continue
            seen_query_keys.add(qkey)

            yield _sse({
                "type": "tool-call",
                "id": f"tc{step}",
                "name": "lookup_skill_content",
                "args": {
                    "query": query,
                    "scope": scope,
                    "subject_slug": subject_slug,
                    "node_id": decision.node_id,
                },
            })
            try:
                retriever = build_retriever_for_scope(
                    skill_root, scope,
                    subject_slug=subject_slug,
                    node_id=decision.node_id,
                )
                hits = retriever.search(query, k=top_k)
            except (FileNotFoundError, ValueError) as exc:
                logger.warning("agent: lookup failed (%s); empty hits", exc)
                hits = []
            label = scope_label(skill_root, scope,
                                subject_slug=subject_slug,
                                node_id=decision.node_id)
            yield _sse({
                "type": "tool-result",
                "id": f"tc{step}",
                "hit_count": len(hits),
                "scope_label": label,
            })
            for i, h in enumerate(hits, start=len(accumulated) + 1):
                yield _sse(_citation_event(i, h))
            accumulated.extend(hits)

            # Append to the agent's view of the conversation so the next
            # decision call sees TOOL_RESULT context.
            msgs.append(Message(
                role="user",
                content=_format_tool_result_message(scope, hits),
            ))
            continue

        # action == "answer" — stream the text and exit.
        text = decision.text or "(no answer text)"
        yield _sse({"type": "text-start", "id": text_id})
        # Naive chunking: split into ~80-char windows so the UI gets a
        # streaming feel even on a non-streaming JSON-mode response.
        for chunk in _chunk_text(text):
            yield _sse({"type": "text-delta", "id": text_id, "delta": chunk})
        yield _sse({"type": "text-end", "id": text_id})
        answered = True
        break

    if not answered:
        # Step budget exhausted without an answer. Emit a polite fallback.
        yield _sse({"type": "text-start", "id": text_id})
        yield _sse({"type": "text-delta", "id": text_id,
                    "delta": "I couldn't find enough source content to answer "
                             "with confidence. Try rephrasing or narrowing the topic."})
        yield _sse({"type": "text-end", "id": text_id})

    yield _sse({"type": "finish", "finishReason": "stop"})
    yield b"data: [DONE]\n\n"


def _citation_event(index: int, hit: ParagraphHit) -> dict:
    return {
        "type": "data-citation",
        "id": f"c{index}",
        "data": {
            "index": index,
            "node_id": hit.node_id,
            "paragraph_id": hit.paragraph_id,
            "page": hit.page,
            "snippet": hit.snippet,
        },
    }


def _chunk_text(text: str, size: int = 80) -> list[str]:
    """Split a string into ``size``-char chunks for streaming UX."""
    if not text:
        return []
    return [text[i:i + size] for i in range(0, len(text), size)]
