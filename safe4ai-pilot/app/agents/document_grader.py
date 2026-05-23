from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from app.agents.entity_booster import boost_entity_chunks
from app.models import GradedChunk, RankedChunk
from app.prompts.registry import get_prompt

_MAX_CONCURRENT_GRADES = 5


def grade_chunks_by_score(chunks: list[RankedChunk], threshold: float) -> list[GradedChunk]:
    """Grade chunks using rerank score only — no LLM call."""
    return [
        GradedChunk(
            **chunk.model_dump(),
            relevant=chunk.rerank_score >= threshold,
            reason="rerank",
        )
        for chunk in chunks
    ]


async def grade_chunks(
    query: str,
    chunks: list[RankedChunk],
    *,
    chat_client: Any = None,
    ollama_url: str = "",
    model: str = "",
    client: httpx.AsyncClient | None = None,
    rerank_threshold: float | None = None,
) -> list[GradedChunk]:
    if not chunks:
        return []

    if rerank_threshold is not None:
        chunks = boost_entity_chunks(query, chunks, rerank_threshold)
        return grade_chunks_by_score(chunks, rerank_threshold)

    template = get_prompt("document_grader", "v1")
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_GRADES)

    async def _grade_one_with_client(chunk: RankedChunk) -> GradedChunk:
        async with semaphore:
            prompt = template.template.format(query=query, chunk=chunk.content)
            try:
                result = await chat_client.chat(
                    "You are a relevance grader. Reply with JSON.", prompt
                )
                raw = result.content.strip()
                data: dict[str, Any] = json.loads(raw)
                return GradedChunk(
                    **chunk.model_dump(),
                    relevant=bool(data.get("relevant", False)),
                    reason=str(data.get("reason", "")),
                )
            except Exception:
                return GradedChunk(**chunk.model_dump(), relevant=False, reason="grading failed")

    async def _grade_one_ollama(c: httpx.AsyncClient, chunk: RankedChunk) -> GradedChunk:
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
                data = json.loads(raw)
                return GradedChunk(
                    **chunk.model_dump(),
                    relevant=bool(data.get("relevant", False)),
                    reason=str(data.get("reason", "")),
                )
            except Exception:
                return GradedChunk(**chunk.model_dump(), relevant=False, reason="grading failed")

    if chat_client is not None:
        results = await asyncio.gather(*[_grade_one_with_client(chunk) for chunk in chunks])
        return list(results)

    async def _run(c: httpx.AsyncClient) -> list[GradedChunk]:
        results = await asyncio.gather(*[_grade_one_ollama(c, chunk) for chunk in chunks])
        return list(results)

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient() as c:
        return await _run(c)
