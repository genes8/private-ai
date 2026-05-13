from __future__ import annotations

import json

import httpx

from app.prompts.registry import get_prompt


async def decompose_query(
    query: str,
    *,
    ollama_url: str,
    model: str,
    client: httpx.AsyncClient | None = None,
) -> list[str]:
    template = get_prompt("query_decomposer", "v1")
    prompt = template.template.format(query=query)

    async def _call(c: httpx.AsyncClient) -> list[str]:
        try:
            resp = await c.post(
                f"{ollama_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=30.0,
            )
            resp.raise_for_status()
            raw: str = resp.json().get("response", "{}").strip()
            data = json.loads(raw)
            sub_queries = data.get("sub_queries", [])
            if isinstance(sub_queries, list) and all(isinstance(q, str) for q in sub_queries):
                return sub_queries[:4]
        except Exception:  # noqa: S110
            pass
        return [query]

    if client is not None:
        return await _call(client)
    async with httpx.AsyncClient() as c:
        return await _call(c)
