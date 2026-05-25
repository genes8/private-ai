"""Shared LLM call helper.

Every agent node that needs to call the LLM should use ``call_llm`` instead
of writing its own chat_client/httpx fallback pattern.  The five nearly-
identical copies that existed before this module had slightly different timeout
values, different Ollama endpoint paths (/api/generate vs /api/chat), and
different error-handling — this consolidation makes the behaviour consistent.
"""
from __future__ import annotations

from typing import Any

import httpx


async def call_llm(
    prompt: str,
    *,
    system: str = "",
    chat_client: Any = None,
    ollama_url: str = "",
    model: str = "",
    http_client: httpx.AsyncClient | None = None,
    timeout: float = 30.0,
) -> str:
    """Call the LLM and return the text response.

    Resolution order:
    1. ``chat_client`` (ChatClient protocol) — used in production when a
       provider is configured.
    2. ``http_client`` (injected AsyncClient) — used in tests to avoid
       opening new connections.
    3. A fresh ``httpx.AsyncClient`` — used when neither is supplied.

    All paths hit ``/api/generate`` (Ollama's generate endpoint) for the raw
    fallback so that behaviour is consistent regardless of call site.
    """
    if chat_client is not None:
        result = await chat_client.chat(system, prompt)
        return result.content

    async def _via(c: httpx.AsyncClient) -> str:
        resp = await c.post(
            f"{ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "think": False},
            timeout=timeout,
        )
        resp.raise_for_status()
        return str(resp.json().get("response", ""))

    if http_client is not None:
        return await _via(http_client)
    async with httpx.AsyncClient() as c:
        return await _via(c)
