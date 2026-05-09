from dataclasses import dataclass, field


@dataclass
class PromptTemplate:
    name: str
    version: str
    template: str
    input_variables: list[str] = field(default_factory=list)


TEMPLATES: list[PromptTemplate] = [
    PromptTemplate(
        name="query_rewriter",
        version="v1",
        template=(
            "You are a search query optimizer. Given the user question below, "
            "write a hypothetical document excerpt that would perfectly answer it. "
            "Return only the hypothetical excerpt, no explanation.\n\nQuestion: {query}"
        ),
        input_variables=["query"],
    ),
    PromptTemplate(
        name="document_grader",
        version="v1",
        template=(
            "You are grading whether a document chunk is relevant to a user question.\n"
            "Question: {query}\n"
            "Chunk: {chunk}\n"
            'Return JSON: {{"relevant": true/false, "reason": "...", "confidence": 0.0-1.0}}'
        ),
        input_variables=["query", "chunk"],
    ),
    PromptTemplate(
        name="query_decomposer",
        version="v1",
        template=(
            "Break the following complex question into 2-4 simpler sub-questions "
            "that can each be answered independently.\n"
            "Question: {query}\n"
            'Return JSON: {{"sub_queries": ["...", "..."]}}'
        ),
        input_variables=["query"],
    ),
    PromptTemplate(
        name="conversation_summarizer",
        version="v1",
        template=(
            "Summarize the following conversation in 2-3 sentences, "
            "preserving key facts and decisions that are relevant for future turns.\n\n"
            "{conversation}"
        ),
        input_variables=["conversation"],
    ),
]
