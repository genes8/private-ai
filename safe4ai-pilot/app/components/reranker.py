from __future__ import annotations

import numpy as np
from sentence_transformers import CrossEncoder

from app.models import RankedChunk, RetrievedChunk

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class Reranker:
    def __init__(self) -> None:
        self._model: CrossEncoder = CrossEncoder(_MODEL_NAME)

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int = 6,
    ) -> list[RankedChunk]:
        if not chunks:
            return []

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
