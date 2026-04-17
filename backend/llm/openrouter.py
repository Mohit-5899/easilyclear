import asyncio
import json
import logging
import random
from typing import AsyncIterator

import httpx

from .base import LLMResponse, Message

logger = logging.getLogger(__name__)

_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 5
_BASE_DELAY = 2.0


class OpenRouterClient:
    provider_name = "openrouter"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        site_url: str = "https://github.com/gemma-tutor",
        app_name: str = "Gemma Tutor",
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("OpenRouter API key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": site_url,
            "X-Title": app_name,
        }
        self._timeout = timeout_seconds

    def _build_payload(
        self,
        messages: list[Message],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool,
        response_format: dict | None = None,
    ) -> dict:
        payload: dict = {
            "model": model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        return payload

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        response_format: dict | None = None,
    ) -> LLMResponse:
        payload = self._build_payload(
            messages,
            model,
            temperature,
            max_tokens,
            stream=False,
            response_format=response_format,
        )
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(_MAX_RETRIES + 1):
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers,
                    json=payload,
                )
                if resp.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES:
                    retry_after = resp.headers.get("retry-after")
                    if retry_after is not None:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = _BASE_DELAY * (2 ** attempt)
                    else:
                        delay = _BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        "openrouter: %d (retrying in %.1fs, attempt %d/%d)",
                        resp.status_code, delay, attempt + 1, _MAX_RETRIES,
                    )
                    await asyncio.sleep(delay)
                    continue
                resp.raise_for_status()
                data = resp.json()
                break

        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return LLMResponse(
            content=choice,
            model=data.get("model", model),
            provider=self.provider_name,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            raw=data,
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        payload = self._build_payload(messages, model, temperature, max_tokens, stream=True)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=self._headers,
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    chunk = line.removeprefix("data: ").strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        obj = json.loads(chunk)
                        delta = obj["choices"][0]["delta"].get("content")
                        if delta:
                            yield delta
                    except (KeyError, json.JSONDecodeError):
                        continue
