from __future__ import annotations

import httpx

from app.prompts.registry import get_prompt


class QueryRewriter:
    def __init__(self, ollama_url: str, model: str) -> None:
        self._ollama_url = ollama_url
        self._model = model

    async def rewrite(self, query: str) -> str:
        try:
            template = get_prompt("query_rewriter", "v1")
            prompt = template.template.format(query=query)
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._ollama_url}/api/generate",
                    json={"model": self._model, "prompt": prompt, "stream": False},
                    timeout=30.0,
                )
                resp.raise_for_status()
                rewritten: str = resp.json().get("response", "").strip()
            return rewritten if rewritten else query
        except Exception:
            return query
