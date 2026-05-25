from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from app.agents.entity_booster import boost_entity_chunks
from app.agents.llm_caller import call_llm
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

    async def _grade_one(chunk: RankedChunk) -> GradedChunk:
        async with semaphore:
            prompt = template.template.format(query=query, chunk=chunk.content)
            try:
                raw = await call_llm(
                    prompt,
                    system="You are a relevance grader. Reply with JSON.",
                    chat_client=chat_client,
                    ollama_url=ollama_url,
                    model=model,
                    http_client=client,
                )
                data: dict[str, Any] = json.loads(raw.strip())
                return GradedChunk(
                    **chunk.model_dump(),
                    relevant=bool(data.get("relevant", False)),
                    reason=str(data.get("reason", "")),
                )
            except Exception:
                return GradedChunk(**chunk.model_dump(), relevant=False, reason="grading failed")

    results = await asyncio.gather(*[_grade_one(chunk) for chunk in chunks])
    return list(results)
