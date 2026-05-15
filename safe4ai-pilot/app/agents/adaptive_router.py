from __future__ import annotations

import json
from typing import Any

import httpx

from app.models import PrivateAIState
from app.prompts.registry import get_prompt


def route_after_grade(state: PrivateAIState) -> str:
    """Synchronous fallback rule: ≥ 2 relevant chunks → generate, else → decompose."""
    if sum(1 for c in state.graded_chunks if c.relevant) >= 2:
        return "generate"
    return "decompose"


def route_quality_gate(state: PrivateAIState) -> str:
    """Synchronous rule: grounded answer → respond, otherwise → fallback."""
    if state.grounded:
        return "respond"
    return "fallback"


async def decide_next_step(
    state: PrivateAIState,
    allowed_steps: list[str],
    *,
    chat_client: Any = None,
    ollama_url: str = "",
    model: str = "",
    client: httpx.AsyncClient | None = None,
) -> str:
    """LLM-based adaptive routing for self-correction cycles."""
    if not allowed_steps:
        return "fallback"

    template = get_prompt("adaptive_router", "v1")
    last_query = state.rewritten_query or (state.messages[-1].content if state.messages else "")
    context = f"graded_chunks={len(state.graded_chunks)}, grounded={state.grounded}"
    prompt = template.template.format(
        query=last_query,
        current_step=state.current_step,
        context=context,
        allowed_steps=", ".join(allowed_steps),
    )

    def _parse(raw: str) -> str:
        try:
            data = json.loads(raw)
            decision = str(data.get("decision", ""))
            if decision in allowed_steps:
                return decision
        except (json.JSONDecodeError, AttributeError):
            pass
        return allowed_steps[0]

    if chat_client is not None:
        result = await chat_client.chat("You are a routing assistant. Reply with JSON.", prompt)
        return _parse(result.content.strip())

    async def _call(c: httpx.AsyncClient) -> str:
        resp = await c.post(
            f"{ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=30.0,
        )
        resp.raise_for_status()
        raw: str = resp.json().get("response", "{}").strip()
        return _parse(raw)

    if client is not None:
        return await _call(client)
    async with httpx.AsyncClient() as c:
        return await _call(c)
