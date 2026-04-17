from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "gemma-tutor-backend"
    app_env: Literal["dev", "prod"] = "dev"

    cors_allow_origins: list[str] = [
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

    llm_provider: Literal["openrouter", "ollama", "mock"] = "mock"

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = "https://github.com/gemma-tutor"
    openrouter_app_name: str = "Gemma Tutor"

    ollama_base_url: str = "http://localhost:11434"

    model_answer: str = Field(
        default="google/gemma-4-26b-a4b-it:free",
        description="Model for user-facing answers. OpenRouter slug during build; Ollama tag at demo time.",
    )
    model_retrieval: str = Field(
        default="google/gemma-4-26b-a4b-it:free",
        description="Model for PageIndex tree traversal. Can point to a cheaper model later if rate limits bite.",
    )

    request_timeout_seconds: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
