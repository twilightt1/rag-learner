"""Async OpenRouter client supporting both streaming and non-streaming completions."""
from __future__ import annotations

import json
from typing import List, Dict, AsyncIterator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import settings

HEADERS = {
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost:5173",
    "X-Title": "RAG Learner Assistant",
}


def _get_headers() -> Dict[str, str]:
    h = dict(HEADERS)
    if settings.llm_api_key:
        h["Authorization"] = f"Bearer {settings.llm_api_key}"
    return h


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def complete(
    messages: List[Dict[str, str]],
    model: str = None,
    max_tokens: int = 1024,
    temperature: float = 0.3,
) -> str:
    """
    Non-streaming chat completion. Returns the full response string.
    """
    model = model or settings.llm_model
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"https://openrouter.ai/api/v1/chat/completions",
            headers=_get_headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"]


async def stream_complete(
    messages: List[Dict[str, str]],
    model: str = None,
    max_tokens: int = 1024,
    temperature: float = 0.3,
) -> AsyncIterator[str]:
    """
    Streaming chat completion. Yields text delta strings as they arrive.
    """
    model = model or settings.llm_model
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"https://openrouter.ai/api/v1/chat/completions",
            headers=_get_headers(),
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    delta = data["choices"][0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        yield token
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
