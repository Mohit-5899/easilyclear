"""Agentic tutor chat endpoint — POST /tutor/agent_chat.

Per spec docs/research/2026-05-02-ux-redesign-architecture.md §3.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import get_settings
from llm.base import LLMClient
from tutor.agent import run_agent
from tutor.scope import Scope


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/tutor", tags=["tutor"])


_DEFAULT_SKILL_ROOT = (
    Path(__file__).resolve().parent.parent.parent / "database" / "skills"
)
_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts_v2" / "agent_chat_system.md"
)


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str


class AgentChatRequest(BaseModel):
    messages: list[ChatTurn] = Field(min_length=1)
    book_slug: str | None = None
    default_scope: Scope = "all"
    max_steps: int = Field(default=3, ge=1, le=5)


def _get_skill_root(app_state) -> Path:
    override = getattr(app_state, "skill_root_override", None)
    if override is not None:
        return Path(override)
    return _DEFAULT_SKILL_ROOT


@router.post("/agent_chat")
async def agent_chat(
    req: AgentChatRequest, request: Request,
) -> StreamingResponse:
    settings = get_settings()
    llm: LLMClient = request.app.state.llm
    skill_root = _get_skill_root(request.app.state)

    user_msgs = [m for m in req.messages if m.role == "user"]
    if not user_msgs:
        raise HTTPException(status_code=422, detail="no user message in request")
    last_user = user_msgs[-1].content

    # Prior history = everything except the last user message.
    history: list[dict[str, str]] = []
    seen_last = False
    for m in reversed(req.messages):
        if not seen_last and m.role == "user":
            seen_last = True
            continue
        history.append({"role": m.role, "content": m.content})
    history.reverse()

    try:
        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail=f"missing agent system prompt: {exc}",
        )

    headers = {
        "x-vercel-ai-ui-message-stream": "v1",
        "Cache-Control": "no-cache",
    }

    return StreamingResponse(
        run_agent(
            llm=llm,
            model=settings.model_answer,
            skill_root=skill_root,
            history=history,
            user_message=last_user,
            system_prompt=system_prompt,
            max_steps=req.max_steps,
            default_scope=req.default_scope,
            default_book_slug=req.book_slug,
        ),
        media_type="text/event-stream",
        headers=headers,
    )
