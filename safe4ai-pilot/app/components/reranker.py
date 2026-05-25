from __future__ import annotations

import asyncio

import numpy as np
import structlog
from sentence_transformers import CrossEncoder

from app.models import RankedChunk, RetrievedChunk

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

logger = structlog.get_logger(__name__)


class Reranker:
    def __init__(self, model_name: str = _MODEL_NAME, enabled: bool = True) -> None:
        self._enabled = enabled
        self._model: CrossEncoder | None = None
        if enabled:
            try:
                self._model = CrossEncoder(model_name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("reranker_model_load_failed", model_name=model_name, error=str(exc))
                self._enabled = False

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int = 6,
    ) -> list[RankedChunk]:
        if not chunks:
            return []

        if not self._enabled or self._model is None:
            ranked = sorted(chunks, key=lambda chunk: chunk.score, reverse=True)[:top_n]
            return [RankedChunk(**chunk.model_dump(), rerank_score=chunk.score) for chunk in ranked]

        pairs = [(query, chunk.content) for chunk in chunks]
        predict = getattr(self._model, "predict")
        raw_scores = predict(pairs)
        scores = [float(score) for score in np.asarray(raw_scores).tolist()]

        ranked = sorted(
            zip(chunks, scores),
            key=lambda x: x[1],
            reverse=True,
        )[:top_n]

        return [RankedChunk(**chunk.model_dump(), rerank_score=score) for chunk, score in ranked]

    async def arerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int = 6,
    ) -> list[RankedChunk]:
        """Async wrapper that runs the blocking CrossEncoder.predict in a thread pool.

        Use this from async graph nodes / pipeline methods to avoid stalling
        the event loop during CPU-bound inference.
        """
        return await asyncio.to_thread(self.rerank, query, chunks, top_n)
