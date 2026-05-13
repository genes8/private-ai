from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from app.models import GradedChunk, RankedChunk
from app.prompts.registry import get_prompt

_MAX_CONCURRENT_GRADES = 5


async def grade_chunks(
    query: str,
    chunks: list[RankedChunk],
    *,
    ollama_url: str,
    model: str,
    client: httpx.AsyncClient | None = None,
) -> list[GradedChunk]:
    if not chunks:
        return []

    template = get_prompt("document_grader", "v1")

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_GRADES)

    async def _grade_one(c: httpx.AsyncClient, chunk: RankedChunk) -> GradedChunk:
        async with semaphore:
            prompt = template.template.format(query=query, chunk=chunk.content)
            try:
                resp = await c.post(
                    f"{ollama_url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                    timeout=30.0,
                )
                resp.raise_for_status()
                raw: str = resp.json().get("response", "{}").strip()
                data: dict[str, Any] = json.loads(raw)
                return GradedChunk(
                    **chunk.model_dump(),
                    relevant=bool(data.get("relevant", False)),
                    reason=str(data.get("reason", "")),
                )
            except Exception:
                return GradedChunk(**chunk.model_dump(), relevant=False, reason="grading failed")

    async def _run(c: httpx.AsyncClient) -> list[GradedChunk]:
        results = await asyncio.gather(*[_grade_one(c, chunk) for chunk in chunks])
        return list(results)

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient() as c:
        return await _run(c)
