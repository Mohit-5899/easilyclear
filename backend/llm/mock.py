from typing import AsyncIterator

from .base import LLMResponse, Message


class MockLLMClient:
    """Deterministic fake client. Lets us develop and run tests without any API
    key. Returns a predictable echo-style response so retrieval/tutor/tests code
    can be exercised offline."""

    provider_name = "mock"

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        user_turn = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "<no user message>",
        )
        fake = f"[mock:{model}] Echo of: {user_turn[:200]}"
        return LLMResponse(
            content=fake,
            model=model,
            provider=self.provider_name,
            prompt_tokens=sum(len(m.content.split()) for m in messages),
            completion_tokens=len(fake.split()),
            raw=None,
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        resp = await self.complete(
            messages, model=model, temperature=temperature, max_tokens=max_tokens
        )
        for word in resp.content.split():
            yield word + " "
