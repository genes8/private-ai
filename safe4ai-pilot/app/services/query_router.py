from __future__ import annotations

import json
from typing import Any

import httpx

from app.models import RouterDecision


class QueryRouter:
    def __init__(self, ollama_url: str, model: str) -> None:
        self._ollama_url = ollama_url
        self._model = model

    async def route(
        self,
        query: str,
        available_collections: list[str],
        session_collection: str | None = None,
    ) -> RouterDecision:
        if not available_collections:
            return RouterDecision(
                collection="",
                confidence=0.0,
                reason="no collections available",
            )

        if session_collection and session_collection in available_collections:
            return RouterDecision(
                collection=session_collection,
                confidence=1.0,
                reason="session default",
            )

        if len(available_collections) == 1:
            return RouterDecision(
                collection=available_collections[0],
                confidence=1.0,
                reason="only one collection available",
            )

        prompt = (
            f"You have these document collections: {available_collections}.\n"
            f"User query: {query}\n"
            "Which collection best matches this query? "
            'Return JSON: {"collection": "...", "confidence": 0.0-1.0, "reason": "..."}'
        )

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._ollama_url}/api/generate",
                    json={"model": self._model, "prompt": prompt, "stream": False},
                    timeout=30.0,
                )
                resp.raise_for_status()
                raw: str = resp.json().get("response", "")
                data: dict[str, Any] = json.loads(raw)
                collection = str(data.get("collection", available_collections[0]))
                confidence = float(data.get("confidence", 0.5))
                reason = str(data.get("reason", ""))
                if collection not in available_collections:
                    collection = available_collections[0]
                return RouterDecision(
                    collection=collection,
                    confidence=confidence,
                    reason=reason,
                )
        except Exception:
            return RouterDecision(
                collection=available_collections[0],
                confidence=0.5,
                reason="fallback: could not parse LLM response",
            )
