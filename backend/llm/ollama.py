from typing import AsyncIterator

from .base import LLMResponse, Message


class OllamaClient:
    """Stub for offline-demo swap (Day 26+).

    Left unimplemented intentionally — we build against this interface during
    the OpenRouter phase so that filling in the HTTP calls later is purely
    additive. No caller code will change.
    """

    provider_name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self._base_url = base_url.rstrip("/")

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        raise NotImplementedError(
            "OllamaClient.complete is deferred to Day 26 (offline demo swap). "
            "Use LLM_PROVIDER=openrouter or LLM_PROVIDER=mock for now."
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        raise NotImplementedError(
            "OllamaClient.stream is deferred to Day 26 (offline demo swap)."
        )
        yield  # pragma: no cover — makes this a valid async generator signature
