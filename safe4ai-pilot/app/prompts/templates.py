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
            "You are a search query optimizer. Given the conversation history "
            "and the user's latest question, "
            "write a hypothetical document excerpt that would perfectly answer the question. "
            "Use context from the conversation to resolve pronouns and vague "
            "references (e.g. 'it', 'this', 'the alliance', 'tell me more'). "
            "Return only the hypothetical excerpt, no explanation.\n\n"
            "{history}"
            "Question: {query}"
        ),
        input_variables=["query", "history"],
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
    PromptTemplate(
        name="rag_answer",
        version="v1",
        template=(
            "Answer the following question using ONLY the provided context. "
            "If the context does not contain enough information, say so.\n\n"
            "Context:\n{context}\n\n"
            "Question: {query}"
        ),
        input_variables=["context", "query"],
    ),
    PromptTemplate(
        name="rag_answer",
        version="v2",
        template=(
            "Answer the following question for the user, using the context below "
            "as your primary source of truth. The context is excerpts from the "
            "user's own confidential documents, labeled [1], [2], ....\n\n"
            "Follow this answer contract:\n"
            "1. Answer the user's actual question directly and concisely first. "
            "Reply in the user's language when it is clear.\n"
            "2. Keep a hard distinction between two kinds of statements:\n"
            "   - Document-grounded facts: supported by the context. Cite them "
            "with the bracketed source numbers, e.g. [1] or [2].\n"
            "   - General inference / model knowledge: obvious general-world "
            "facts or simple inferences (e.g. 'the Houses of Parliament are in "
            "London'). You may use these, but you MUST label them clearly, for "
            "example: 'This is not stated directly in the documents; it is "
            "general model knowledge or an inference.'\n"
            "3. When the documents do not state something, say so explicitly: "
            "state what the documents do and do not confirm. Do not present an "
            "inference as a documented fact.\n"
            "4. NEVER fill these entity-specific facts from your own training "
            "when the context does not state them: headquarters or registered "
            "office, exact address, founders/executives/members/partners/"
            "customers, website/email/phone/domain, dates/counts/prices/contract "
            "terms, security/compliance/legal claims, and internal policy "
            "obligations or operational commitments. For these, say what the "
            "documents do and do not confirm.\n"
            "5. Do not say 'the statement is false' unless the user is "
            "explicitly checking a specific claim.\n"
            "6. Do not force fixed headings. When no inference is needed, a "
            "short, conversational, grounded answer is fine.\n\n"
            "Context:\n{context}\n\n"
            "Question: {query}"
        ),
        input_variables=["context", "query"],
    ),
    PromptTemplate(
        name="adaptive_router",
        version="v1",
        template=(
            "You are a pipeline router for a document Q&A system.\n"
            "Current state:\n"
            "- Query: {query}\n"
            "- Current step: {current_step}\n"
            "- Context: {context}\n\n"
            "Choose the next step from: {allowed_steps}\n"
            'Return JSON: {{"decision": "...", "reasoning": "...", "suggested_focus": "..."}}'
        ),
        input_variables=["query", "current_step", "context", "allowed_steps"],
    ),
]
