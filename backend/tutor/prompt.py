"""Tutor prompt assembly (spec 2026-05-02-tutor-chat.md).

Per research findings (`docs/research/2026-05-01-tool-calling.md`): we don't
rely on Gemma 4 26B's tool-calling. Retrieval happens server-side; we put
the relevant paragraphs into the prompt as numbered sources and ask the
model to cite them with [N] markers. This also matches the streaming chat
pattern in `docs/research/2026-05-01-streaming-chat.md` (RAG before LLM, no
tool roundtrip).
"""

from __future__ import annotations

from .retriever import ParagraphHit


_SYSTEM_PROMPT = (
    "You are a tutor helping a student prepare for the RAS Pre exam "
    "(Rajasthan Administrative Services Preliminary).\n\n"
    "Rules:\n"
    "1. Answer ONLY using the source paragraphs provided below the user's "
    "question.\n"
    "2. If the answer is not in those sources, say exactly: "
    "\"The provided source does not cover that.\"\n"
    "3. Cite each factual claim with a marker like [1], [2], [3] mapping to "
    "the source numbers below. Place the marker immediately after the claim.\n"
    "4. Be precise and exam-focused. Aim for 2-4 sentences unless the "
    "question genuinely requires more.\n"
    "5. Do not invent source numbers. Only use markers for sources that "
    "appear below."
)


def build_tutor_messages(
    *,
    question: str,
    node_title: str,
    hits: list[ParagraphHit],
) -> list[dict[str, str]]:
    """Build the chat-completion messages list.

    Args:
        question: the student's question, raw text.
        node_title: the human-readable title of the selected skill node.
        hits: top-k paragraph hits from the BM25 retriever.

    Returns:
        ``[{"role": "system", "content": ...}, {"role": "user", "content": ...}]``.
        Caller passes this directly to ``LLMClient.complete``.
    """
    if hits:
        sources_block_lines = ["# Source paragraphs (selected node: " + node_title + ")"]
        for idx, hit in enumerate(hits, start=1):
            sources_block_lines.append(
                f"[{idx}] (page {hit.page}) {hit.snippet}"
            )
        sources_block = "\n".join(sources_block_lines)
    else:
        sources_block = (
            f"# Source paragraphs (selected node: {node_title})\n"
            "(no sources retrieved for this question)"
        )

    user_content = (
        f"{sources_block}\n\n"
        f"# Question\n{question}\n\n"
        f"Answer using ONLY the sources above. Cite with [N] markers."
    )

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
