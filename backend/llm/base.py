from typing import AsyncIterator, Literal, Protocol, runtime_checkable

from pydantic import BaseModel


Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    role: Role
    content: str


class LLMResponse(BaseModel):
    content: str
    model: str
    provider: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    raw: dict | None = None


@runtime_checkable
class LLMClient(Protocol):
    """Unified LLM interface. Every caller in retrieval/, tutor/, tests_engine/
    depends on this Protocol, never on a concrete implementation. Swapping
    OpenRouter ↔ Ollama ↔ mock is one env var away (see llm/factory.py)."""

    provider_name: str

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse: ...

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]: ...
