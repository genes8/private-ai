# Safe4AI Pilot — Project Context

## What this is
A private AI pilot system that lets enterprise customers chat with their own documents using a fully local LLM stack. No data leaves the server.

## Stack
- **Backend:** FastAPI + Python 3.11
- **AI orchestration:** LangGraph + LangChain
- **LLM:** Qwen 3.5 9B via Ollama — handles chat/RAG and vision OCR (single multimodal model)
- **Embeddings:** nomic-embed-text via Ollama
- **Vector DB:** Qdrant (document retrieval, hybrid dense+sparse)
- **Relational DB:** PostgreSQL + pgvector (sessions, audit, semantic cache)
- **Frontend:** React + Vite + Tailwind (Phase 4)

## Directory map
```
app/             — FastAPI application
  main.py        — entry point + /health
  config.py      — Settings (pydantic-settings, reads .env)
  models.py      — shared Pydantic types (Message, RetrievedChunk, etc.)
  components/    — retrieval primitives (hybrid_retriever, reranker)
  services/      — business logic (rag_pipeline, semantic_cache, etc.)
  prompts/       — versioned prompt templates + registry
  agents/        — LangGraph nodes + tools
  security/      — input_guard, content_filter, output_filter
  auth/          — JWT + RBAC middleware
  audit/         — append-only audit logger
  db/            — SQLAlchemy models + Alembic migrations
observability/   — OpenTelemetry tracer, feedback, cost tracker
evaluation/      — offline eval, online monitor, golden dataset
scripts/         — seed, migrate, healthcheck, backup
tests/           — pytest test suite
```

## Key conventions
- All prompts via `app.prompts.registry.get_prompt()` — never hardcoded inline
- Two distinct routers: `services/query_router.py` (collection) vs `agents/adaptive_router.py` (pipeline step)
- JWT served as HTTP-Only cookie only — never in response body
- Audit logs: append-only, first 500 chars of query only, no passwords or tokens
- 80% test coverage minimum

## What not to touch
- Never modify `evaluation/eval_results/` — gitignored, may contain customer data
- Never commit `.env` or any file matching `.env.*`
- Never store JWT or passwords in logs
