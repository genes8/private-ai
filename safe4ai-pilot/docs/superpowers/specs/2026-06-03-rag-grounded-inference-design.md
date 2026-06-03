# RAG Grounded Inference Answer Contract Design

Date: 2026-06-03
Status: Approved design, pending implementation plan

## Goal

Improve the on-prem RAG answer behavior for the local `qwen3.5:9b` model so it
feels like a useful assistant without weakening the product's core guarantee:
confidential local documents remain the primary source of truth.

The model may use only obvious general knowledge or simple inference when the
documents provide partial evidence. It must clearly label that material as not
found directly in the documents. It must not fill entity-specific facts from
pretraining.

## Current Context

The current graph flow is:

`intake -> rewrite -> retrieve -> grade -> [generate | decompose] -> output_filter -> quality_gate -> [respond | retrieve | fallback]`

Relevant implementation anchors:

- `app/prompts/templates.py` defines `query_rewriter`, `document_grader`,
  `query_decomposer`, `conversation_summarizer`, `rag_answer`, and
  `adaptive_router`.
- `app/agents/graph.py` builds the LangGraph pipeline and formats the context
  currently sent to `rag_answer`.
- `app/agents/document_grader.py` normally uses score-only grading when
  `rerank_threshold` is set, so tuning the `document_grader` prompt alone will
  not affect the default path.
- `app/agents/adaptive_router.py` currently uses deterministic routing rules,
  which is good for latency on a local 9B model.
- `app/security/output_filter.py` already performs output checks and is the
  right place for a lightweight format/label guard.

## Answer Contract

Every answer should preserve a hard distinction between document-grounded facts
and model inference.

1. Document-grounded facts

   This is the primary layer. Facts in this layer must be supported by retrieved
   chunks and citations.

2. General inference / model knowledge

   This is allowed only for general-world facts or obvious inferences, such as
   "the Houses of Parliament are in London." It must be labeled clearly:

   "This is not stated directly in the documents; it is general model knowledge
   or an inference."

3. Not confirmed in documents

   Entity-specific facts that the documents do not state must not be completed
   from model pretraining. Examples include headquarters, founders, addresses,
   websites, members, partners, legal status, contracts, dates, counts, prices,
   obligations, and policy commitments.

## Expected Behavior Example

User: `is it London?`

If the retrieved context says the Business AI Alliance is UK-based and was
launched at the Houses of Parliament, but does not state headquarters:

> The documents do not state the Business AI Alliance headquarters city.
>
> From the documents: the Alliance is UK-based and was launched at the Houses
> of Parliament.
>
> General inference: this is not stated directly in the documents, but the
> Houses of Parliament are in London. So if you mean the launch location, then
> London is the answer.
>
> Not confirmed in the documents: that London is the Alliance headquarters.

The model should not answer as though "London is the headquarters" unless that
is directly supported by retrieved documents.

## Pipeline Design

Keep the current graph shape and avoid adding another LLM node in the first
implementation. The user's latency target is already acceptable at roughly ten
seconds, and an extra classifier call would put that at risk.

### 1. Strengthen `rag_answer`

Replace the short `ONLY context` prompt with a strict answer contract prompt.
The prompt should instruct the model to:

- answer the user's actual question directly first;
- separate document-grounded facts from general inference;
- state when a fact is not confirmed in the documents;
- avoid "the statement is false" unless the user is explicitly checking a
  claim;
- never use pretraining for entity-specific facts not present in the documents;
- use the user's language when clear.

### 2. Improve Context Packing

Format generation context with stable source labels, for example:

`[S1] Business-AI-Alliance-New-Joiner-Welcome-Pack-November-2025.pdf p.2`

This gives the 9B model cleaner anchors for citing evidence while preserving
the existing UI citation list.

### 3. Add a Lightweight Output Guard

If the generated answer uses general inference/model knowledge language, the
answer must include a clear disclaimer that this information is not stated
directly in the documents.

The guard should not require every answer to include an inference section. It
should only enforce labeling when inference is present.

## Allowed General Inference

Allowed examples:

- A cited place is in a well-known city, such as Houses of Parliament -> London.
- A country or jurisdiction relationship that is common general knowledge.
- A simple wording clarification that does not add a private/entity-specific
  fact.

These must be labeled as not directly found in the documents.

## Disallowed Pretraining Fill

Disallowed unless retrieved documents support it:

- headquarters or registered office;
- exact address;
- founder, executive team, members, partners, customers;
- website, email, phone, domain;
- dates, counts, prices, contract terms;
- security/compliance/legal claims;
- internal policy obligations or operational commitments.

For these, the answer should say what the documents do and do not confirm.

## Testing Plan

Add focused backend tests around graph generation behavior:

- direct document answer remains grounded and cited;
- partial-evidence answer includes document facts plus labeled general
  inference;
- headquarters/entity-specific question is not filled from model knowledge;
- output guard rejects an inference answer that lacks the required disclaimer;
- simple ordinary questions still complete without invoking extra LLM router or
  grader calls beyond the current path.

Existing useful test anchors include:

- `tests/test_agents.py`
- `tests/test_rag_pipeline.py`
- `tests/test_security_guards.py`

## Non-Goals

- Do not add web lookup.
- Do not add a new LLM classifier node in the first iteration.
- Do not change retrieval thresholds, chunk sizes, reranker model, or
  decomposition behavior as part of this first change.
- Do not allow entity-specific public facts from model pretraining.

## Risks And Mitigations

Risk: the prompt becomes too long and slows the local model.
Mitigation: keep the contract explicit but compact, and do not add another LLM
call.

Risk: the model labels unsupported entity-specific facts as "general inference."
Mitigation: list forbidden entity-specific categories in the prompt and add an
output guard for missing inference labels.

Risk: the output format feels too rigid.
Mitigation: require the distinction, not fixed headings for every answer. Short
answers may remain conversational when no inference is used.
