# Architecture

## Why two vector stores?

| | Qdrant | pgvector |
|---|---|---|
| **Used for** | Document retrieval (hybrid dense+sparse ANN) | Semantic cache lookup only |
| **Why** | Purpose-built for ANN, filtering, payload metadata | Cache is small (<10K entries); same DB as audit/sessions |
| **Query volume** | High — every user query | Low — cache hits on repeated queries |

If pilot has < 5K documents, pgvector can serve both roles. Document the decision here.

## Two distinct routers

- **`services/query_router.py`** — *collection router*: selects which Qdrant collection to query. Rule-based first, LLM-assisted if ambiguous. Runs before retrieval.
- **`agents/adaptive_router.py`** — *pipeline step router*: decides which LangGraph node runs next (retrieve / grade / decompose / generate / fallback). LLM-driven with closed enum. Runs inside the agent loop.

These compose sequentially: collection → pipeline steps.

## LangGraph pipeline

```
intake → input_guard → rewrite → retrieve → grade
  ├─ ≥2 relevant chunks → generate → output_filter → quality_gate
  │     ├─ grounded → respond
  │     └─ not grounded → fallback
  └─ <2 relevant → decompose → retrieve (2nd pass) → generate
```

## Security layers

1. **input_guard** — query length, prompt injection patterns, jailbreaks
2. **content_filter** — PII in retrieved chunks before LLM sees them
3. **output_filter** — hallucinated PII, factual grounding, human review routing

## Data flow: ingestion

```
Upload → validate MIME + size → store to data/raw/ (UUID filename)
→ background job → PDF/DOCX/XLSX loader → chunk (800 tokens, 150 overlap)
→ [if scanned: pdf2image → qwen2.5vl OCR → quality gate]
→ embed (nomic-embed-text) → store in Qdrant + document_chunks table
→ status: ready (or needs_review if OCR quality low)
```
