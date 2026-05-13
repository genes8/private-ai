from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RetrievedChunk(BaseModel):
    chunk_id: str
    doc_id: str
    filename: str
    page_number: int
    content: str
    score: float


class RankedChunk(RetrievedChunk):
    rerank_score: float


class GradedChunk(RankedChunk):
    relevant: bool
    reason: str


class Citation(BaseModel):
    filename: str
    page_number: int
    excerpt: str
    score: float


class GuardResult(BaseModel):
    allowed: bool
    reason: str


class RouterDecision(BaseModel):
    collection: str
    confidence: float
    reason: str


class PrivateAIState(BaseModel):
    session_id: str
    user_id: str
    messages: list[Message] = Field(default_factory=list)
    current_step: Literal[
        "intake",
        "rewrite",
        "retrieve",
        "grade",
        "decompose",
        "generate",
        "output_filter",
        "quality_gate",
        "respond",
        "fallback",
    ] = "intake"
    status: Literal["active", "completed", "failed"] = "active"

    # retrieval
    rewritten_query: str = ""
    retrieved_chunks: list[RankedChunk] = Field(default_factory=list)
    graded_chunks: list[GradedChunk] = Field(default_factory=list)
    retrieval_score_max: float = 0.0

    # decomposition
    sub_queries: list[str] = Field(default_factory=list)

    # output
    draft_answer: str = ""
    citations: list[Citation] = Field(default_factory=list)
    grounded: bool = False

    # observability
    trace_id: str = ""
    cost_usd: float = 0.0
    errors: list[str] = Field(default_factory=list)

    # human review flag — set by graph when answer quality is insufficient
    requires_human_review: bool = False

    # counts how many times retrieve_node has run; used as self-correction loop guard
    retrieval_attempts: int = 0

    # snapshot of the exact chunks supplied to generate_node for the current answer;
    # output_filter_node validates against this rather than the live graded_chunks snapshot
    generation_context: list[GradedChunk] = Field(default_factory=list)
