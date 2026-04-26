"""
app/services/nvidia_nim_service.py — Shared NVIDIA NIM chat client.

Uses NVIDIA's OpenAI-compatible API for LLM-backed moderation services.
"""

import logging

from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def is_nim_configured() -> bool:
    """Return True when the NVIDIA API key is available."""
    return bool(settings.NVIDIA_API_KEY and not settings.NVIDIA_API_KEY.startswith("nvapi_REPLACE"))


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=settings.NVIDIA_NIM_BASE_URL,
        api_key=settings.NVIDIA_API_KEY,
    )


async def nim_chat_completion(
    *,
    messages: list[dict[str, str]],
    max_tokens: int = 1024,
    temperature: float = 0.1,
    top_p: float = 1.0,
) -> str:
    """
    Run a streaming NVIDIA NIM chat completion and return assembled content.

    The public API is intentionally tiny so services can keep their own prompts,
    parsing, and domain-specific fallback behavior.
    """
    if not is_nim_configured():
        raise RuntimeError("NVIDIA API key not configured")

    stream = await _client().chat.completions.create(
        model=settings.NVIDIA_NIM_MODEL,
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        stream=True,
    )

    parts: list[str] = []
    async for chunk in stream:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue

        delta = choices[0].delta
        content = getattr(delta, "content", None)
        if content is not None:
            parts.append(content)

    if not parts:
        raise RuntimeError("Empty NVIDIA NIM message content")

    return "".join(parts)
