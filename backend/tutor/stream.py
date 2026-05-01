"""AI SDK UI Message Stream protocol writer (spec 2026-05-02-tutor-chat.md).

Per research `docs/research/2026-05-01-streaming-chat.md`: FastAPI emits the
AI SDK UI Message Stream protocol directly so the Next.js client can use
``useChat`` from ``@ai-sdk/react`` v5 without going through the buggy
``@openrouter/ai-sdk-provider``.

Wire format: SSE with ``x-vercel-ai-ui-message-stream: v1`` header. Each
event is a single ``data: <json>\\n\\n`` line. Event types we emit:

  * ``start-step``       — once at the very beginning
  * ``data-citation``    — one per retrieved source paragraph (emitted up
                            front so the UI can render citation pills as
                            placeholders before text streams in)
  * ``text-start``       — opens a text part with a stable ``id``
  * ``text-delta``       — token deltas referencing that ``id``
  * ``text-end``         — closes the text part
  * ``finish``           — terminates the stream

We also emit a final ``data: [DONE]`` terminator (Vercel-compatible).
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator

from llm.base import LLMClient, Message

from .retriever import ParagraphHit


logger = logging.getLogger(__name__)


def _sse(event: dict) -> bytes:
    """Encode one event dict as an SSE ``data:`` frame."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")


async def stream_tutor_response(
    *,
    llm: LLMClient,
    model: str,
    messages: list[Message],
    hits: list[ParagraphHit],
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> AsyncIterator[bytes]:
    """Stream a tutor chat response in AI SDK UI Message Stream format.

    Order of emitted events:
      1. ``start-step``
      2. one ``data-citation`` per hit (with 1-indexed ``index``)
      3. ``text-start``
      4. zero or more ``text-delta`` (one per upstream LLM delta)
      5. ``text-end``
      6. ``finish``
      7. ``[DONE]`` sentinel

    On upstream LLM error we emit a ``finish`` with ``finishReason="error"``
    and the message in ``providerMetadata``.
    """
    yield _sse({"type": "start-step"})

    # Citations up front.
    for idx, hit in enumerate(hits, start=1):
        yield _sse(
            {
                "type": "data-citation",
                "id": f"c{idx}",
                "data": {
                    "index": idx,
                    "node_id": hit.node_id,
                    "paragraph_id": hit.paragraph_id,
                    "page": hit.page,
                    "snippet": hit.snippet,
                },
            }
        )

    text_id = f"t-{uuid.uuid4().hex[:8]}"
    yield _sse({"type": "text-start", "id": text_id})

    finish_reason = "stop"
    error_message: str | None = None

    try:
        async for delta in llm.stream(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if not delta:
                continue
            yield _sse({"type": "text-delta", "id": text_id, "delta": delta})
    except Exception as exc:  # pragma: no cover - network failure paths
        logger.warning("tutor stream upstream error: %s", exc)
        finish_reason = "error"
        error_message = str(exc)

    yield _sse({"type": "text-end", "id": text_id})

    finish_event: dict = {"type": "finish", "finishReason": finish_reason}
    if error_message:
        finish_event["providerMetadata"] = {"error": error_message}
    yield _sse(finish_event)
    yield b"data: [DONE]\n\n"
