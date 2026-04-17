from config import Settings, get_settings

from .base import LLMClient
from .mock import MockLLMClient
from .ollama import OllamaClient
from .openrouter import OpenRouterClient


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    """Factory — the ONE place the codebase knows about concrete LLM classes.

    Every caller depends on the LLMClient Protocol, gets its instance through
    this function, and never imports OpenRouterClient / OllamaClient / MockLLMClient
    directly. Swapping providers = one env var (LLM_PROVIDER)."""
    s = settings or get_settings()

    if s.llm_provider == "openrouter":
        if not s.openrouter_api_key:
            raise ValueError(
                "LLM_PROVIDER=openrouter requires OPENROUTER_API_KEY in .env. "
                "Set LLM_PROVIDER=mock to develop without a key."
            )
        return OpenRouterClient(
            api_key=s.openrouter_api_key,
            base_url=s.openrouter_base_url,
            site_url=s.openrouter_site_url,
            app_name=s.openrouter_app_name,
            timeout_seconds=s.request_timeout_seconds,
        )

    if s.llm_provider == "ollama":
        return OllamaClient(base_url=s.ollama_base_url)

    return MockLLMClient()
