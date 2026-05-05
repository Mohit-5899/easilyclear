"""Tutor chat endpoint — POST /tutor/chat.

Per spec 2026-05-02-tutor-chat.md. Builds a BM25 retriever scoped to the
selected node's subtree, retrieves top-3 paragraphs, calls Gemma 4 26B with
those paragraphs in the prompt, and streams the response in AI SDK UI
Message Stream format so the frontend's ``useChat`` hook can render text
deltas + citation pills natively.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import get_settings
from llm.base import LLMClient, Message
from tutor.prompt import build_tutor_messages
from tutor.retriever import build_retriever_for_node
from tutor.stream import stream_tutor_response


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/tutor", tags=["tutor"])


# Default skill root — configurable via Settings.skill_root for tests/dev.
_DEFAULT_SKILL_ROOT = Path(__file__).resolve().parent.parent / "database" / "skills"


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    node_id: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1)
    book_slug: str | None = None


def _get_skill_root(app_state) -> Path:
    """Resolve skill root, honoring test override on app.state."""
    override = getattr(app_state, "skill_root_override", None)
    if override is not None:
        return Path(override)
    return _DEFAULT_SKILL_ROOT


def _node_title(skill_root: Path, node_id: str) -> str:
    """Best-effort: read the leaf or SKILL.md frontmatter for a friendlier
    title in the prompt. Falls back to the last path segment."""
    parts = node_id.split("/")
    # Try leaf.md
    leaf_md = skill_root.joinpath(*parts).with_suffix(".md")
    skill_md = skill_root.joinpath(*parts) / "SKILL.md"
    for candidate in (leaf_md, skill_md):
        if candidate.is_file():
            try:
                import frontmatter
                post = frontmatter.load(candidate)
                name = post.metadata.get("name")
                if name:
                    return str(name)
            except (OSError, ValueError):
                pass
    return parts[-1].replace("-", " ").replace("_", " ").title()


@router.post("/chat")
async def tutor_chat(req: ChatRequest, request: Request) -> StreamingResponse:
    settings = get_settings()
    llm: LLMClient = request.app.state.llm
    skill_root = _get_skill_root(request.app.state)

    # Latest user message is the question.
    user_msgs = [m for m in req.messages if m.role == "user"]
    if not user_msgs:
        raise HTTPException(status_code=422, detail="no user message in request")
    question = user_msgs[-1].content

    # Build retriever scoped to selected subtree.
    try:
        retriever = build_retriever_for_node(skill_root, req.node_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    hits = retriever.search(question, k=3)

    title = _node_title(skill_root, req.node_id)
    prompt_messages = build_tutor_messages(
        question=question, node_title=title, hits=hits,
    )
    llm_messages = [Message(**m) for m in prompt_messages]

    headers = {
        # AI SDK 5 wire-protocol marker — useChat sniffs this on the client.
        "x-vercel-ai-ui-message-stream": "v1",
        "Cache-Control": "no-cache",
    }
    return StreamingResponse(
        stream_tutor_response(
            llm=llm,
            model=settings.model_answer,
            messages=llm_messages,
            hits=hits,
        ),
        media_type="text/event-stream",
        headers=headers,
    )
