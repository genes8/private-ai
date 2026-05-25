from __future__ import annotations

import json
from typing import Any

import httpx

from app.agents.llm_caller import call_llm
from app.prompts.registry import get_prompt


async def decompose_query(
    query: str,
    *,
    chat_client: Any = None,
    ollama_url: str = "",
    model: str = "",
    client: httpx.AsyncClient | None = None,
) -> list[str]:
    template = get_prompt("query_decomposer", "v1")
    prompt = template.template.format(query=query)

    def _parse(raw: str) -> list[str]:
        try:
            data = json.loads(raw)
            sub_queries = data.get("sub_queries", [])
            if isinstance(sub_queries, list) and all(isinstance(q, str) for q in sub_queries):
                return sub_queries[:4]
        except (json.JSONDecodeError, AttributeError):
            pass
        return [query]

    try:
        raw = await call_llm(
            prompt,
            system="You are a query decomposition assistant. Reply with JSON.",
            chat_client=chat_client,
            ollama_url=ollama_url,
            model=model,
            http_client=client,
        )
        return _parse(raw.strip())
    except Exception:
        return [query]
