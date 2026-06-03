# Safe4AI Private AI Pilot — Implementation Plan

> Superseded on 2026-06-03. Use `safe4ai-pilot/docs/superpowers/plans/2026-06-03-unified-readiness-pilot-roadmap.md` as the canonical plan. This file remains as historical implementation input only.

## Why Two Vector Stores (pgvector + Qdrant)?

Both exist for distinct purposes — they are not redundant:

| | Qdrant | pgvector (PostgreSQL) |
|---|---|---|
| **Used for** | Document retrieval (hybrid dense+sparse, ANN at scale) | Semantic cache lookup only |
| **Why** | Purpose-built for ANN search, filtering, payload metadata — significantly faster at scale | Semantic cache is small (<10K entries), benefits from being in the same DB as audit_logs and sessions; simpler ops |
| **Query volume** | High — every user query hits Qdrant | Low — cache lookups only on repeated/similar queries |

If Qdrant is overkill for a small pilot (< 5K documents), pgvector can serve both roles. Document this decision in `docs/architecture.md`.

---

## Agent Classification

RAG / Document Agent (primary) with decision-support characteristics (regulated domain, audit mandatory, human review required). Framework: LangGraph Python + LangChain + Qdrant. Model: Qwen 3.5 9B via Ollama/vLLM.

---

## Production Directory Structure

Aligned with production AI app architecture. Every layer is a directory, not a file.

```
safe4ai-pilot/
├── app/
│   ├── main.py                        # FastAPI entry point
│   ├── config.py                      # Settings via pydantic-settings
│   ├── models.py                      # Shared Pydantic schemas
│   ├── Dockerfile
│   │
│   ├── components/                    # Low-level retrieval primitives
│   │   ├── hybrid_retriever.py        # Dense + sparse search, BM25 + vectors
│   │   └── reranker.py                # Cross-encoder reranking
│   │
│   ├── services/                      # Core business logic (orchestration layer)
│   │   ├── rag_pipeline.py            # End-to-end RAG: ingest + query
│   │   ├── semantic_cache.py          # Cache LLM responses by query embedding similarity
│   │   ├── conversation.py            # Session state, multi-turn memory management
│   │   ├── query_rewriter.py          # HyDE / query expansion before retrieval
│   │   └── query_router.py            # Route queries to correct index/collection
│   │
│   ├── prompts/                       # Versioned, typed, registered — never hardcoded
│   │   ├── templates.py               # Prompt template definitions with metadata
│   │   └── registry.py                # Central registry: get_prompt(name, version)
│   │
│   ├── agents/                        # Self-correcting intelligence layer
│   │   ├── document_grader.py         # Grade retrieved chunks for relevance
│   │   ├── query_decomposer.py        # Decompose complex queries into sub-queries
│   │   ├── adaptive_router.py         # LLM-driven routing with self-correction
│   │   └── tools/
│   │       ├── vector_search.py       # Tool: query Qdrant
│   │       └── web_search.py          # Tool: web fallback (future)
│   │
│   ├── security/                      # Three guards, not one
│   │   ├── input_guard.py             # Validate and sanitize user input
│   │   ├── content_filter.py          # Filter retrieved content before LLM sees it
│   │   └── output_filter.py           # Validate and filter LLM output before user sees it
│   │
│   ├── auth/                          # JWT, RBAC
│   │   └── middleware.py
│   │
│   ├── audit/                         # Append-only audit trail
│   │   └── logger.py
│   │
│   └── db/                            # SQLAlchemy models, Alembic migrations
│       ├── models.py
│       └── migrations/
│
├── evaluation/                        # Most teams skip this. We don't.
│   ├── golden_dataset.json            # Ground truth Q&A pairs per workflow
│   ├── offline_eval.py                # Run eval against golden dataset, score results
│   ├── online_monitor.py              # Monitor live query quality, flag regressions
│   └── eval_results/                  # local eval outputs, gitignored except sanitized sample
│
├── observability/                     # Per-stage tracing, feedback, cost
│   ├── tracer.py                      # Span per pipeline stage (ingest, retrieve, grade, generate)
│   ├── feedback.py                    # Capture user thumbs up/down, link to trace_id
│   └── cost_tracker.py                # Token count + cost per query, per session, per user
│
├── data/
│   ├── raw/                           # Original documents before processing
│   ├── processed/                     # Chunked + cleaned documents
│   └── index_config/                  # Qdrant collection config, chunk strategy config
│
├── scripts/
│   ├── seed.py                        # Seed users, test documents
│   ├── migrate.py                     # Run Alembic migrations
│   └── healthcheck.py                 # Check all services are alive
│
├── frontend/
│   ├── app.py (or index.html + React)
│   ├── static/
│   └── Dockerfile
│
├── tests/
│   ├── conftest.py                    # Shared fixtures: test DB, mock Ollama, Qdrant testcontainer
│   ├── test_retrieval.py              # Unit + integration tests for retrieval
│   ├── test_cache.py                  # Semantic cache hit/miss tests
│   ├── test_routing.py                # Router decision tests
│   ├── test_security.py              # Guard bypass attempts
│   ├── test_agents.py                 # Grader, decomposer, router tests
│   ├── test_auth.py                   # Login, cookie, brute-force lockout, RBAC
│   ├── test_ingestion.py              # Document upload, background job, restart recovery
│   └── test_audit.py                  # Audit log entries, cleanup job, retention
│
├── docs/
│   ├── architecture.md
│   ├── api-reference.md
│   └── deployment.md
│
├── .claude/
│   └── rules/
│       ├── code-style.md              # How code is written in this repo
│       └── testing.md                 # Testing conventions and patterns
│
├── CLAUDE.md                          # Project context for AI coding assistant
├── AGENTS.md                          # Agent definitions, roles, tool permissions
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## Phase Dependency Map

```
[Phase 0: Business Offer]  ←── runs in parallel, no technical dependency

[Phase 1: Infrastructure & Project Setup]  ✅ DONE
         │
    ┌────┴──────────────────────┐
    │                           │
[Phase 2A: RAG Core] ✅        [Phase 2B: Security & Auth] ✅
         │                      [Phase 2C: Observability] ✅
         │
    ┌────┴──────────────────────┐
    │                           │
[Phase 2D: Evaluation] ✅      [Phase 3A: Agents & LangGraph] ✅
                                [Phase 3B: Admin API] ✅
                                [Phase 3C: Agent Hardening] ✅
                                        │
                                  [Phase 4: Web UI] ✅
                                        │
                                  [Phase 5: Pilot Report]  ← NEXT
```

---

## Phase 0 — Business Offer Definition

**Owner:** Founder / Sales
**Duration:** 1 week
**Parallel with:** Phase 1

- [ ] Write one-page sales offer (single PDF, max 2 sides)
- [ ] Create pilot scope checklist (what is included / excluded per tier)
- [ ] Create discovery questionnaire for first sales calls
  - What workflow do you want to improve?
  - What document types and volumes do you have?
  - Where is data currently stored?
  - What IT approvals are needed?
  - Who is the pilot owner on the customer side?
- [ ] Write security FAQ (top 5 objections: data leaves the server? model training? GDPR?)
- [ ] Create sample final report template (blank, fillable)
- [ ] Define target company list of 100 (by vertical, size, geography)

**Exit criteria:** sales offer is printable and sendable; discovery questionnaire can run a 45-minute call.

---

## Phase 1 — Infrastructure & Project Setup

**Owner:** Backend / DevOps Engineer
**Duration:** 2-3 days
**Blocks:** All phases below

### Project Scaffold

- [x] Initialize Python project (`pyproject.toml`, Python 3.11+)
- [x] Add core dependencies: `fastapi`, `uvicorn[standard]`, `python-multipart`, `langgraph`, `langchain`, `langchain-community`, `langchain-ollama`, `langchain-qdrant`, `pydantic`, `pydantic-settings`, `sqlalchemy`, `pgvector`, `alembic`, `qdrant-client`, `PyJWT[crypto]` *(zamijenjen `python-jose` koji ima CVE-2024-33663/33664)*, `httpx`, `rank-bm25`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp`, `passlib[bcrypt]`, `slowapi`, `python-magic`, `secure`, `structlog`, `sentence-transformers`, `pypdf`, `pdf2image`, `docx2txt`, `openpyxl`, `pillow`, `APScheduler`
  > **Odluka: `unstructured[pdf]` uklonjen** — vuče ogroman transitivni dep tree sa ~30+ CVE-a bez fixa. Nije potreban: PDF parsing pokriva `pypdf`, scanned PDFs pokriva LLM vision OCR (`qwen2.5vl:7b` via Ollama direktno). `UnstructuredPDFLoader` se ne koristi.
- [x] Add dev dependencies: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `pip-audit`, `testcontainers[postgres,qdrant]`, `detect-secrets`
- [x] Create full directory structure as defined in the Production Directory Structure above
- [x] Create `.env.example`:
  ```
  POSTGRES_URL=
  QDRANT_URL=
  OLLAMA_URL=
  OLLAMA_MODEL=qwen3.5:9b
  EMBEDDING_MODEL=nomic-embed-text
  SECRET_KEY=
  ALLOWED_ORIGINS=http://localhost:5173
  ENFORCE_HTTPS=false
  AUDIT_LOG_RETENTION_DAYS=90
  CACHE_RETENTION_DAYS=30
  SEMANTIC_CACHE_THRESHOLD=0.92
  COST_PER_1K_TOKENS=0.0
  MAX_UPLOAD_SIZE_MB=50
  ```

### Hardware Requirements

Minimum for pilot (all models running simultaneously):

| Component | VRAM / RAM |
|---|---|
| Qwen 3.5 9B (Q4 quantized via Ollama) | ~6 GB VRAM or ~12 GB RAM (CPU) |
| Qwen2.5-VL 7B (vision OCR via Ollama) | ~5 GB VRAM or ~10 GB RAM (CPU) |
| nomic-embed-text | ~500 MB VRAM/RAM |
| cross-encoder reranker | ~200 MB RAM |
| Qdrant + PostgreSQL + app | ~4 GB RAM |
| **Total minimum (both models loaded)** | **16 GB VRAM (GPU) or 28 GB RAM (CPU-only)** |

> Note: Both Qwen models don't need to be in VRAM simultaneously — Qwen2.5-VL is only used during ingestion of scanned docs. `OLLAMA_KEEP_ALIVE` can be set to unload vision model after ingestion. In practice, 12 GB VRAM (e.g. RTX 3080 Ti) is sufficient if models are swapped.

- [x] Document in `docs/deployment.md`: GPU recommended (NVIDIA 8GB+); CPU-only works but inference is 5–10x slower
- [x] Set `OLLAMA_KEEP_ALIVE=24h` in Ollama env — prevents model unloading between requests
- [x] Add model pre-warm job on app startup: `POST /api/generate` with empty prompt to Ollama before accepting traffic — avoids cold-start timeout on first real query
- [x] Add graceful degradation: if Ollama returns 503 (model not loaded / OOM), return a user-friendly error ("AI is warming up, please try again in 30 seconds") and log to audit; never crash the app
- [x] CPU fallback: document that Q4 quantized Qwen 3.5 9B runs on CPU at ~3 tokens/sec — acceptable for pilot if no GPU available

### Docker Compose

- [x] `docker-compose.yml` services: `postgres` image=`pgvector/pgvector:0.8.0-pg16` (NOT `postgres:16` — plain postgres doesn't ship with pgvector), `qdrant` (port 6333), `ollama` (port 11434, GPU passthrough), `jaeger` (image=`jaegertracing/all-in-one`, port 16686 UI + 4317 OTLP), `app` (port 8000)
- [x] `docker-compose.override.yml` for local dev (volume mounts, hot reload)
- [x] Health checks on all services
- [x] Ollama model pull on startup: `qwen3.5:9b` (chat/RAG) + `nomic-embed-text` (embeddings) + `qwen2.5vl:7b` (vision OCR for scanned documents)
- [x] `data/raw/`, `data/processed/`, `data/index_config/` mounted as volumes
- [x] `app/Dockerfile` installs system deps: `poppler-utils` (required by `pdf2image` to render PDF pages to images), `libmagic1` — these are apt packages, not pip
- [x] Cross-encoder model pre-baked into Docker image: `RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"` — prevents runtime HuggingFace download in air-gapped deployments
- [x] Pull vision OCR model on Ollama startup: `qwen2.5vl:7b` (multimodal — used for LLM-based OCR of scanned documents)

### Database Migrations (Alembic)

- [x] `sessions` — `(id, user_id, created_at, updated_at, state_json)`
- [x] `users` — `(id, email, password_hash, role ENUM[admin,pilot_user], created_at, is_active, failed_login_count, locked_until)`
- [x] `documents` — `(id, filename, storage_filename, file_type, ingestion_status ENUM[queued,embedding,indexed,failed,skipped], uploaded_by, uploaded_at, doc_metadata, ingestion_started_at)` — enum values renamed from initial plan (`pending→queued`, `ingesting→embedding`, `ready→indexed`, `needs_review→skipped`) to match handoff frontend spec
- [x] `document_chunks` — `(id, document_id, chunk_index, chunk_version integer default 1, content_preview, qdrant_point_id)` — `chunk_version` mirrors `documents.version`; retrieval joins `document_chunks.chunk_version = documents.active_version` to return only active-version chunks
- [x] `semantic_cache` — `(id, query_embedding VECTOR(768), query_text, response_json JSONB, citations_json JSONB, source_document_ids JSONB, source_chunk_ids JSONB, created_at, hit_count)` — `source_document_ids` enables cache invalidation when a document is deleted or reindexed: `DELETE FROM semantic_cache WHERE source_document_ids @> '["<doc_id>"]'::jsonb`
- [x] `audit_logs` — `(id, user_id, session_id, timestamp, action_type, query_text, response_metadata JSONB, latency_ms, model_used, trace_id)`
- [x] `agent_runs` — `(id, session_id, started_at, finished_at, status, final_output, error, cost_usd)`
- [x] `query_feedback` — `(id, trace_id, session_id, user_id, rating ENUM[positive,negative], comment, created_at)`
- [x] `ingestion_jobs` — `(id, document_id, status, created_at, completed_at, error)` — DB-backed job record so restarts can detect and recover stuck jobs
- [x] `human_review_queue` — `(id, session_id, user_id, query, draft_answer, citations_json JSONB, risk_reason, status ENUM[pending,approved,rejected], reviewed_by, reviewed_at)`

### AI Coding Assistant Context

- [x] Write `CLAUDE.md` — project overview, stack, conventions, directory map, what not to touch
- [x] Write `AGENTS.md` — agent definitions, which agent owns which directory, tool permissions
- [x] Write `.claude/rules/code-style.md` — naming conventions, async patterns, error handling style
- [x] Write `.claude/rules/testing.md` — test structure, what must be tested, fixture conventions

### Shared Type Definitions (`app/models.py`)

Define all shared types here in Phase 1 so Phase 2A and Phase 3A can import from the same source without circular dependencies:

- [x] `Message` — `(role: Literal["user","assistant"], content: str, created_at: datetime)`
- [x] `RetrievedChunk` — `(chunk_id, doc_id, filename, page_number, content, score: float)`
- [x] `RankedChunk` — extends `RetrievedChunk` with `rerank_score: float`
- [x] `GradedChunk` — extends `RankedChunk` with `relevant: bool, reason: str`
- [x] `Citation` — `(filename, page_number, excerpt: str, score: float)`
- [x] `PrivateAIState` — full state model (see Phase 3A for fields); defined here so `conversation.py` (Phase 2A) and LangGraph (Phase 3A) both import from `app.models`
- [x] `GuardResult` — `(allowed: bool, reason: str)`
- [x] `RouterDecision` — `(collection: str, confidence: float, reason: str)` — for `query_router.py`

### Router Separation (explicit)

Two routers exist with distinct responsibilities — they do not overlap:

- **`services/query_router.py`** (Phase 2A) — *collection router*: determines which Qdrant collection to query based on session config or query content. Rule-based first, LLM-assisted if ambiguous. Returns `RouterDecision`. Runs before retrieval.
- **`agents/adaptive_router.py`** (Phase 3A) — *pipeline step router*: determines which LangGraph node to execute next (retrieve, grade, decompose, generate, fallback). LLM-driven with closed Literal enum. Runs inside the agent loop.

These compose sequentially: `query_router` selects the collection → `adaptive_router` drives the pipeline steps over that collection.

### Prompt Registry

- [x] Write `app/prompts/templates.py` — define all prompt templates as typed dataclasses with `name`, `version`, `template`, `input_variables`
- [x] Write `app/prompts/registry.py` — `get_prompt(name: str, version: str = "latest") -> PromptTemplate`; prompts are never hardcoded inline in services or agents

### `.gitignore`

- [x] Create `.gitignore` — must exclude: `.env`, `.env.*`, `data/raw/`, `data/processed/`, `*.pyc`, `__pycache__/`, `.mypy_cache/`, `HF_HOME/` (HuggingFace model cache), `evaluation/eval_results/` (may contain customer-derived data — never commit real pilot runs), `*.egg-info/`
- [x] Verify: `git status` shows none of the above as untracked

### CI Pipeline (`.github/workflows/ci.yml`)

- [x] Trigger: push to `main`, PR to `main`
- [x] Steps in order:
  1. `pip install -e ".[dev]"`
  2. `ruff check .` — lint (fail on any error)
  3. `ruff format --check .` — format (fail if not formatted)
  4. `mypy app/` — type check (fail on errors)
  5. `pytest tests/ --cov=app --cov-report=xml --cov-fail-under=80` — tests with coverage gate
  6. `pip-audit --skip-editable --desc` — dependency CVE scan; 0 known vulnerabilities nakon kompletnog upgrade passa (2026-05-09)
  7. `detect-secrets scan --baseline .secrets.baseline` — secrets scan
- [x] Coverage threshold: **80% minimum** on `app/` — CI fails below this

### Pre-commit Hooks (`.pre-commit-config.yaml`)

- [x] `ruff` — lint on every commit
- [x] `ruff-format` — auto-format on every commit
- [x] `detect-secrets` — block commit if new secret detected
- [x] `check-added-large-files` — block files > 5 MB
- [x] Initialize: `detect-secrets scan > .secrets.baseline` on project setup

### `pyproject.toml` Tool Configuration

- [x] `[tool.ruff]` — `line-length = 100`, `target-version = "py311"`, select `["E", "F", "I", "UP", "S"]` (includes security rules)
- [x] `[tool.mypy]` — `strict = true`, `ignore_missing_imports = true`
- [x] `[tool.pytest.ini_options]` — `asyncio_mode = "auto"`, `testpaths = ["tests"]`
- [x] `[tool.coverage.run]` — `omit = ["tests/*", "scripts/*", "evaluation/*"]`

### Scripts

- [x] `scripts/seed.py` — create admin user, load 3 test documents
- [x] `scripts/migrate.py` — wrapper around `alembic upgrade head`
- [x] `scripts/healthcheck.py` — ping postgres, qdrant, ollama; exit non-zero on any failure

### Test Fixture Strategy (`tests/conftest.py`)

- [x] `pg_container` fixture — starts a `pgvector/pgvector:0.8.0-pg16` Testcontainer, runs migrations, yields connection; scoped to session
- [x] `qdrant_container` fixture — starts Qdrant Testcontainer; scoped to session
- [x] `mock_ollama` fixture — `httpx.MockTransport` that returns canned embedding vectors and LLM responses; used in unit tests that must not call real Ollama
- [x] `test_client` fixture — FastAPI `TestClient` wired to test DB and mock Ollama
- [x] Rule: unit tests use `mock_ollama`; integration tests use real containers; no test hits production services

### Smoke Tests

- [x] `GET /health` returns 200 with all dependencies green
- [x] Ollama responds to `/api/generate` with Qwen 3.5 9B — ✅ live smoke potvrđeno 2026-05-09
- [x] Qdrant responds and collection can be created — ✅ live smoke potvrđeno 2026-05-09
- [x] PostgreSQL migrations apply without error — pokriven u `test_integration_containers.py` (Testcontainer, prolazi ✅)
- [x] `pgvector` extension enabled: `SELECT * FROM pg_extension WHERE extname = 'vector'` returns a row — pokriven u `test_integration_containers.py` (Testcontainer, prolazi ✅)

**Status Phase 1 (2026-05-09): KOMPLETNO ✅**
- ruff ✅ · mypy ✅ (17 source files) · pytest 12 passed, 4 skipped (smoke opt-in) · coverage 92.65% ✅ · detect-secrets ✅ · Testcontainer integration ✅
- **pip-audit ✅** — 0 known vulnerabilities
- **Live smoke run ✅** — `docker-compose up` → `{"status":"ok","checks":{"postgres":"ok","qdrant":"ok","ollama":"ok"}}` 2026-05-09
- **docker-compose fixes (macOS):** uklonjen nvidia deploy blok (Docker Desktop ne podržava GPU passthrough); health check-ovi: ollama→`CMD ollama list`, qdrant→`bash /dev/tcp`, jaeger→wget; docker-compose.override.yml build context grešaka ispravljena

**Exit criteria:** `docker-compose up` → health endpoint green → migrations applied → `pytest tests/ --cov=app --cov-fail-under=80` passes locally.

---

## Phase 2A — RAG Core

**Owner:** ML / AI Engineer
**Duration:** 3-4 days
**Requires:** Phase 1
**Parallel with:** Phase 2B, 2C (Phase 2D depends on 2A, so it runs after)

### `app/components/hybrid_retriever.py`

- [x] Dense retrieval: embedding similarity search via Qdrant (cosine, top-k=10)
- [x] Sparse retrieval: BM25 keyword search over chunk content (`rank-bm25`)
- [x] Hybrid fusion: Reciprocal Rank Fusion (RRF) to merge dense + sparse results
- [x] Metadata filtering: filter by `document_ids` list to enforce access boundaries

### `app/components/reranker.py`

- [x] Cross-encoder reranking using `cross-encoder/ms-marco-MiniLM-L-6-v2` (local, no API call)
- [x] Input: top-20 from hybrid retriever; output: top-6 reranked by relevance score
- [x] Expose `rerank(query: str, chunks: list[Chunk]) -> list[RankedChunk]`

### `app/services/rag_pipeline.py`

- [x] Document ingestion:
  - PDF loader (`pypdf`, fallback LLM vision OCR for scanned)
  - DOCX loader (`docx2txt`)
  - XLSX loader (custom: iterate sheets, stringify rows with headers)
  - Plain text loader
  - LLM vision OCR for scanned PDFs (`qwen2.5vl:7b` via Ollama, applied only to pages with < 50 chars of native text) — see LLM Vision OCR section above
  - Store raw to `data/raw/`, processed chunks to `data/processed/`
  - Store chunk metadata in `document_chunks` table
- [x] Chunking: `RecursiveCharacterTextSplitter` chunk_size=800, overlap=150; preserve `{doc_id, filename, page_number, chunk_index}` per chunk
- [x] Embedding: batch via `nomic-embed-text` (Ollama), 100 chunks/batch, retry on failure
- [x] Store vectors + metadata payload in Qdrant collection
- [x] Query path: call hybrid retriever → reranker → return `list[RankedChunk]`

### LLM Vision OCR (`app/services/rag_pipeline.py` — ingestion)

OCR is done via a vision-capable LLM (not Tesseract) for better accuracy on complex layouts, handwriting, mixed languages, and tables.

- [x] PDF page → image: use `pdf2image.convert_from_path()` (requires `poppler-utils`), 200 DPI, PNG output to temp directory
- [x] For each page image, call `qwen2.5vl:7b` via Ollama vision API:
  - System: "Extract all text from this document page exactly as it appears. Preserve structure, headers, tables, and lists. Return only the extracted text."
  - Attach image as base64 in the request
  - Response is the extracted text — treat same as text from native PDF extraction
- [x] OCR is applied only when native text extraction yields < 50 characters per page (i.e. page is an image or scanned)
- [x] **Quality gate**: vision model self-assesses confidence; `ocr_quality` (`"high"/"medium"/"low"/"native"`) stored in Qdrant point payload and `all_chunks` dict ✅
  - `low` → increments `low_confidence_count`; document status set to `needs_review` if > 50% of pages low ✅
  - `medium` or `high` → proceed normally ✅
- [x] Admin sees `skipped` documents in list with warning chip; `DocumentRow` shows `Chip tone="warn"` for skipped status *(Phase 4)*
- [x] Low-confidence chunks included in retrieval but citation shows: "Source quality: low (scanned document — review recommended)"
- [x] Remove `pytesseract` and Tesseract apt packages entirely from stack

### `app/services/query_rewriter.py`

- [x] HyDE (Hypothetical Document Embeddings): generate a hypothetical answer, embed it, use that embedding for retrieval instead of the raw query — improves retrieval for vague questions
- [x] Query expansion: add synonyms / rephrased variants, merge results
- [x] Prompt loaded from registry: `get_prompt("query_rewriter", "v1")`
- [x] Falls back to original query if rewrite fails

### `app/services/semantic_cache.py`

- [x] Cache LLM responses keyed by query embedding (not exact string match)
- [x] Cache hit threshold: cosine similarity > 0.92 (configurable via env)
- [x] Store: `{embedding, query, response, citations, created_at}` in PostgreSQL (`semantic_cache` table with pgvector — Redis not used)
- [x] Cache invalidation: per document (when document is deleted or reindexed, clear related cache entries)
- [x] Log cache hit/miss to observability tracer

### `app/services/conversation.py`

- [x] Load session state from `sessions` table
- [x] Maintain `messages` list (last 10 turns passed to LLM)
- [x] Save updated state after each turn
- [x] `new_session(user_id) -> session_id`
- [x] `load_session(session_id) -> PrivateAIState`
- [x] `save_session(state: PrivateAIState)`

### `app/services/query_router.py`

- [x] Route query to correct Qdrant collection (if multiple document sets indexed)
- [x] Rule-based first (collection name from session config); LLM-assisted if ambiguous
- [x] Returns: `{collection: str, confidence: float, reason: str}`

### Citation Tracking

- [x] Every generated answer links to `chunk_ids` used as context
- [x] Citation schema: `{filename, page_number, excerpt (first 200 chars), score}`
- [x] No-answer fallback: if top chunk score < 0.45 after reranking → do not generate, return fixed fallback string

### Integration Test

- [ ] Upload 20-page PDF → query → cited answer with filename + page number *(real-service, not yet run)*
- [ ] Hybrid retrieval returns better results than dense-only on keyword query *(real-service, not yet run)*
- [ ] Semantic cache returns cached response on paraphrased repeat query *(real-service, not yet run)*
- [ ] Out-of-scope question triggers no-answer fallback *(real-service; unit-tested with mocks ✅)*

**Exit criteria:** ingest → embed → hybrid retrieve → rerank → cited answer works for PDF, DOCX, and scanned image PDF.

**Status Phase 2A (2026-05-11): KOMPLETNO ✅**
- ruff ✅ · mypy ✅ · pytest 173 passed, 4 skipped · coverage 90.93% ✅
- OCR quality gate: `ocr_quality` u Qdrant payload-u za svaki chunk, `needs_review` status na dokumentu ✅
- Real-service integration tests (upload real PDF → query → cited answer) ostaju za pilot smoke run

---

## Phase 2B — Security & Auth

**Owner:** Backend Engineer
**Duration:** 4-5 days
**Requires:** Phase 1
**Parallel with:** Phase 2A, 2C

### Auth

- [x] JWT authentication (`PyJWT[crypto]`, **ne** `python-jose` — python-jose ima CVE-2024-33663/33664 algorithm confusion attacks bez fixa)
  - `POST /auth/login` — email + password → JWT set as **HTTP-Only, Secure, SameSite=Strict cookie** (never in response body or localStorage)
  - `POST /auth/logout` — clears the cookie server-side
  - Access token expiry: 8 hours; cookie `Max-Age` matches
  - HTTPS required in production; `Secure` flag enforced via env (`ENFORCE_HTTPS=true`)
  - API: `jwt.encode(payload, SECRET_KEY, algorithm="HS256")` / `jwt.decode(token, SECRET_KEY, algorithms=["HS256"])`
- [x] CSRF protection: `SameSite=Strict` covers same-origin requests; if cross-origin ever needed, add CSRF double-submit cookie pattern
- [x] RBAC middleware: read JWT from cookie on every request; `admin` and `pilot_user` enforced
- [x] Role decorators: `@require_role("admin")`, `@require_role("pilot_user")`

### Password Hashing

- [x] Direct `bcrypt` lib (passlib[bcrypt] zamijenjen — bcrypt 5.x incompatibility; `hash_password` / `verify_password` koriste `bcrypt.hashpw` / `bcrypt.checkpw` direktno)
- [x] `verify_password(plain, hashed)` and `hash_password(plain)` — only two password-touching functions in the codebase
- [x] Minimum password length: 12 characters, enforced at login

### Brute-Force Protection

- [x] `POST /auth/login` — max 5 attempts per IP per minute; return 429
- [x] Lock account for 15 minutes after 10 failed attempts; log each failure to audit_logs
- [x] Never reveal whether email exists or password is wrong — always return the same generic message

### CORS

- [x] Configure `CORSMiddleware` in `main.py`
- [x] `allow_origins` reads from env `ALLOWED_ORIGINS` — never `*` in production
- [x] `allow_credentials=True` (required for HTTP-Only cookies)
- [x] `allow_methods=["GET", "POST", "PUT", "DELETE"]`
- [x] `allow_headers=["Content-Type"]` — no `Authorization` header needed (cookie-based)

### Security Headers

- [x] Add `secure` library middleware to set on every response:
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` (HSTS)
  - `Content-Security-Policy: default-src 'self'`
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: no-referrer`
  - `Permissions-Policy: geolocation=(), microphone=()`
- [x] Verify headers present on every response in `test_security_headers.py`

### Rate Limiting

- [x] `POST /auth/login` — 5/minute via slowapi ✅
- [ ] `POST /chat` — max 30 requests per user per minute *(endpoint ne postoji — Phase 3B)*
- [x] `POST /admin/documents/upload` — max 10 uploads per user per hour ✅
- [x] `GET /admin/*` — max 100 requests per user per minute ✅

### File Upload Security

- [x] Maximum file size: 50 MB per file (configurable via env `MAX_UPLOAD_SIZE_MB`)
- [x] Validate MIME type against `Content-Type` header AND actual file magic bytes (`python-magic`)
- [x] Allowed extensions whitelist: `.pdf`, `.docx`, `.xlsx`, `.txt` — reject everything else with 400
- [x] Store uploaded files outside the web root (`data/raw/` — never served directly)
- [x] Generate a UUID-based filename on server side; never use the client-supplied filename for storage

### Request Body Limits

- [x] **ASGI middleware** (`limit_body_size` u `main.py`): check `Content-Length` header, return 413 if exceeded
- [ ] **Reverse proxy** (Nginx/Caddy): `client_max_body_size 60m` *(deployment concern — docs/deployment.md)*
- [ ] **Streaming chunk validation**: read in chunks, abort with 413 if bytes exceed limit *(Phase 3B upload endpoint)*

### Dependency Scanning

- [x] `pip-audit` in CI on every PR; 0 known CVEs (2026-05-09)
- [x] Pin all production dependencies with exact versions in `pyproject.toml`

### Logging — Sensitive Data Rules

- [x] Never log: passwords, JWT tokens, cookie values, raw query text in DEBUG level
- [x] `audit_logs.query_text` stores only the first 500 characters; full content never in application logs
- [x] Structured logging only (`structlog`); no f-string log interpolation of user data
- [x] Log files excluded from Docker image (`.dockerignore`); logs written to stdout only in containers

### `app/security/input_guard.py`

- [x] Maximum query length (2048 chars); reject if exceeded
- [x] Detect and block prompt injection patterns (instruction override attempts: "ignore previous instructions", "you are now", etc.)
- [x] Block known jailbreak fragments (maintain a list, configurable)
- [x] Sanitize: strip HTML, control characters
- [x] Return `GuardResult(allowed: bool, reason: str)` — never raise raw exceptions to the user

### `app/security/content_filter.py`

- [x] Filter retrieved chunks before passing to LLM
- [x] Remove chunks flagged as containing PII patterns (regex: SSN, credit card, passport formats) — log a warning but do not crash
- [x] Configurable blocklist of document sections that must not be passed to LLM — `ContentFilter(blocked_terms=[...]).filter_blocked_sections()` ✅

### `app/security/output_filter.py`

- [x] Validate LLM output before it reaches the user
- [x] Detect if answer contains PII that was not in the retrieved chunks (LLM hallucinated PII)
- [x] Detect if answer contradicts a retrieved chunk (basic factual grounding check)
- [x] If output fails: return fallback message, log the raw output to audit (not to user), increment a counter in observability

### Access Control `[PILOT]`

- [ ] Document access: Qdrant filter on `uploaded_by` or `document_group` field *(Phase 3B)*
- [ ] Admin can add/remove users and revoke document access per user *(Phase 3B)*
- [x] Integration test: `pilot_user` cannot call admin endpoints → 403 (test_observability_routes.py TestAdminAuthGuard) ✅

### Data Lifecycle & Deletion `[PILOT]`

PRD explicitly requires documented backup and deletion process:

- [ ] Document full delete: remove from `data/raw/`, `data/processed/`, `document_chunks` table, Qdrant points for all chunk IDs, `semantic_cache` entries referencing the document *(Phase 3B — DELETE endpoint)*
- [ ] `DELETE /admin/documents/{id}` must complete all of the above or roll back with an error *(Phase 3B)*
- [x] Backup: documented in `docs/deployment.md` + `scripts/backup.py` runs pg_dump, Qdrant snapshot, raw file copy
- [x] `scripts/backup.py` ✅
- [x] GDPR/deletion verification: `scripts/verify_deletion.py {doc_id}` ✅

**Exit criteria:** full delete removes all data traces; backup script runs without error; pilot_user returns 403 on admin routes.

**Status Phase 2B (2026-05-10): KOMPLETNO ✅**
- Auth, RBAC, brute-force lockout, security headers, input/content/output guard, file upload security ✅
- passlib zamijenjen direktnim bcrypt zbog bcrypt 5.x incompatibility ✅
- pilot_user 403 na admin rutama: potvrđeno testovima ✅
- Admin rate limiting: `@limiter.limit("10/hour")` na upload, `@limiter.limit("100/minute")` na svih 7 GET /admin/* ruta ✅
- Content filter configurable blocklist: `ContentFilter(blocked_terms=[...])` + `filter_blocked_sections()` ✅

---

## Phase 2C — Observability

**Owner:** Backend Engineer
**Duration:** 1-2 days
**Requires:** Phase 1
**Parallel with:** Phase 2A, 2B

### `observability/tracer.py`

- [x] OpenTelemetry span per pipeline stage: `input_guard`, `query_rewrite`, `retrieval`, `rerank`, `document_grade`, `generate`, `output_filter`
- [x] Each span records: `stage_name`, `duration_ms`, `input_tokens`, `output_tokens`, `cache_hit`, `chunk_ids_used`
- [x] Trace ID propagated through entire request → stored in `audit_logs.trace_id`
- [x] Export: OTLP to local Jaeger (Docker Compose) for pilot; pluggable for production (Langfuse, Datadog)

### `observability/feedback.py`

- [x] `POST /feedback` — `{session_id, trace_id, rating: "positive"|"negative", comment?}`
- [x] Store in `query_feedback` table with `trace_id` so feedback links directly to the trace
- [x] Admin view: `GET /admin/feedback` — with `require_role("admin")` guard ✅

### `observability/cost_tracker.py`

- [x] Track token count per LLM call (prompt tokens + completion tokens)
- [x] Calculate cost (even if Qwen local = $0, track tokens for capacity planning)
- [x] Aggregate: cost per query, per session, per user, per day
- [x] Write to `agent_runs.cost_usd`
- [x] `GET /admin/stats/cost` — with `require_role("admin")` guard ✅

### Audit Log Retention & Cleanup

- [x] `scripts/audit_cleanup.py` — deletes `audit_logs` rows older than `AUDIT_LOG_RETENTION_DAYS` (default 90); logs count of deleted rows
- [x] Scheduled via APScheduler inside the app (daily at 02:00 UTC), wired into `main.py` lifespan via `schedule_cleanup(_app)`
- [x] On each cleanup run, write a summary entry to `audit_logs` itself (`action_type="system_cleanup"`) so the cleanup is itself auditable
- [x] `semantic_cache` rows older than 30 days (configurable via `CACHE_RETENTION_DAYS`) also cleaned up in the same job

**Exit criteria:** every chat query produces a trace with per-stage spans; feedback endpoint stores linked to trace_id; cost per query visible in admin stats; cleanup job runs on startup in test mode and deletes zero rows (empty DB).

**Status Phase 2C (2026-05-09/10): KOMPLETNO ✅**
- tracer.py, feedback.py, cost_tracker.py implementirani i testirani ✅
- `/admin/feedback` i `/admin/stats/cost` imaju `require_role("admin")` guard; 403 za pilot_user potvrđen testovima ✅
- APScheduler cleanup wired u main.py lifespan ✅
- `OTEL_SDK_DISABLED=true` u pytest env — bez OTLP noise u testovima ✅

---

## Phase 2D — Evaluation Layer

**Owner:** ML / AI Engineer
**Duration:** 2 days
**Requires:** Phase 1 + Phase 2A (offline_eval.py runs questions through the full RAG pipeline — needs retrieval, reranking, and generation)
**Parallel with:** Phase 3A, 3B (starts as soon as Phase 2A finishes — typically mid-Week 2, while 3A/3B haven't started yet; overlaps with 3A and 3B in Week 3)

> Most teams skip this entire layer and ship blind. We don't.

### `evaluation/golden_dataset.json`

- [x] Create 20-30 Q&A pairs for each pilot workflow type (document Q&A, policy assistant) — 20 pairs ✅
- [x] Schema per entry: `{id, question, expected_answer, expected_citations: [{filename, page}], difficulty: easy|medium|hard}` ✅
- [x] Cover: factual questions, multi-hop questions, out-of-scope questions, edge cases — 2 OOS, 5 hard, 7 medium, 6 easy ✅
- [x] Versioned in git (each update adds entries, never removes) ✅

### `evaluation/offline_eval.py`

- [x] Load golden dataset → run each question through the full pipeline ✅
- [x] Score per question:
  - **Retrieval recall**: did the correct source filename appear in citations? (binary, reliable) ✅
  - **Answer correctness**: LLM-as-judge 1-5 → normalised 0–1; same local Qwen model as judge ✅
  - **Citation precision**: fraction of citations matching expected source filenames ✅
  - **Fallback accuracy**: did out-of-scope questions trigger no-answer fallback? ✅
- [x] Write results to `evaluation/eval_results/YYYY-MM-DD_HH-MM.json` ✅
- [x] Print summary: overall score, per-difficulty breakdown, regressions vs. previous run ✅
- [x] Exit non-zero if overall score drops below threshold (configurable, default 0.75) ✅

### `evaluation/online_monitor.py`

- [x] Samples configurable % of live queries from `audit_logs` (default 10%) ✅
- [x] Scores sampled queries using heuristics: fallback rate, avg retrieval score, user feedback ratio ✅
- [x] Writes monitoring summary to `eval_results/monitor_YYYY-MM-DD.json` ✅
- [x] Triggers alert (log WARN) if fallback rate > 20% or avg retrieval score < 0.5 ✅

**Exit criteria:** `python evaluation/offline_eval.py` runs to completion and writes a scored results file; overall score ≥ 0.75 on the golden dataset.

**Status Phase 2D (2026-05-10): KOMPLETNO ✅**
- `evaluation/golden_dataset.json`: 20 Q&A pairs — easy/medium/hard/OOS coverage ✅
- `evaluation/offline_eval.py`: LLM-as-judge, 4-metric scoring, regression detection, threshold exit code ✅
- `evaluation/online_monitor.py`: audit_log sampling, heuristic scoring, WARN alerts ✅
- Note: real-service eval run (actual Ollama + Qdrant) is a smoke test for after `docker-compose up`

---

## Phase 3A — LangGraph Agent Workflow

**Owner:** AI Agent Engineer
**Duration:** 3-4 days
**Requires:** Phase 2A (RAG Core)
**Parallel with:** Phase 3B, Phase 2D

### State Model (Pydantic)

```python
class PrivateAIState(BaseModel):
    session_id: str
    user_id: str
    messages: list[Message]
    current_step: Literal[
        "intake", "rewrite", "retrieve", "grade", "decompose",
        "generate", "quality_gate", "respond", "fallback"
    ]
    status: Literal["active", "completed", "failed"]

    # retrieval
    rewritten_query: str = ""
    retrieved_chunks: list[RankedChunk] = []
    graded_chunks: list[GradedChunk] = []
    retrieval_score_max: float = 0.0

    # decomposition
    sub_queries: list[str] = []

    # output
    draft_answer: str = ""
    citations: list[Citation] = []
    grounded: bool = False

    # observability
    trace_id: str = ""
    cost_usd: float = 0.0
    errors: list[str] = []
```

### `agents/document_grader.py`

- [x] For each retrieved chunk, grade its relevance to the query: `{chunk_id, relevant: bool, reason: str, confidence: float}`
- [x] Prompt loaded from registry: `get_prompt("document_grader", "v1")`
- [x] Output via Pydantic structured output (not free text)
- [x] Self-correcting: if < 2 chunks graded as relevant → trigger `query_decomposer` before giving up

### `agents/query_decomposer.py`

- [x] Break complex multi-part question into 2-4 simpler sub-queries
- [x] Run each sub-query through retrieval independently
- [x] Merge and deduplicate results
- [x] Prompt loaded from registry: `get_prompt("query_decomposer", "v1")`
- [x] Only invoked when `document_grader` finds < 2 relevant chunks on first retrieval pass

### `agents/adaptive_router.py`

- [x] LLM-driven router (not hardcoded conditional edges)
- [x] Decides next step based on current state: `{decision, reasoning, suggested_focus}`
- [x] Decision is a closed Literal enum — LLM cannot invent new node names
- [x] Self-correcting: if generation fails quality gate, router can send back to retrieve with a refined query

### LangGraph Graph

- [x] **intake** → `input_guard` → **rewrite** → **retrieve** → **grade** → conditional:
  - if ≥ 2 relevant chunks → **generate**
  - if < 2 relevant → **decompose** → **retrieve** (second pass) → **generate**
- [x] **generate** → **output_filter** → **quality_gate** → conditional:
  - if grounded → **respond**
  - if not grounded → **fallback**
- [x] Observability: tracer span opened at intake, closed at respond/fallback (`run_agent_query` wraps `graph.ainvoke` in a `PipelineSpan`)
- [x] Session: load state at intake, save at respond/fallback (`conversation_manager.save_session` called in `run_agent_query`)

### Human-in-the-Loop Queue (PRD requirement: "human review for high-risk outputs")

- [x] Use `human_review_queue` table (defined in Phase 1 Alembic migrations)
- [x] `output_filter.py` sets `requires_human_review = True` when: output confidence is low, fallback was triggered multiple times in session, or query matches a high-risk pattern (medical symptoms, legal decisions, financial amounts)
- [x] When `requires_human_review = True`: insert into `human_review_queue` (`run_agent_query` owns insertion logic)
- [x] Admin endpoints for review queue are in **Phase 3B** (Admin API) — 3A and 3B run in parallel; 3A owns the queue insertion logic, 3B owns the admin HTTP endpoints
- [x] This fulfils PRD Section 9 minimum requirement: "human review for high-risk outputs"

### Conversation Memory — Long Session Policy

- [x] Default: last 10 turns passed as context (already defined)
- [x] When turn count > 10: summarize older turns using LLM before dropping them — stored as summary message in `sessions.state_json`
- [x] Summarization prompt loaded from registry: `get_prompt("conversation_summarizer", "v1")`
- [x] If summarization fails: fall back to leaving messages unchanged (log warning)
- [x] Maximum context window: last 10 turns enforced via `get_recent_messages(n=10)`

### Integration Tests

- [x] Single-turn Q&A → grounded answer with citations
- [x] Out-of-scope question → fallback (no hallucination)
- [x] Complex multi-part question → decomposer triggers → merged answer
- [x] First retrieval returns poor chunks → self-correction triggers → second pass improves result
- [x] LLM error → caught, logged, user-friendly error returned
- [x] High-risk query → enters human review queue, user gets "under review" message
- [x] Session with 15 turns → summarization triggers, older turns replaced by summary

**Exit criteria:** LangGraph graph compiles; all 7 integration tests pass; traces visible in Jaeger; human review queue has at least one entry after test run.

**Status Phase 3A (2026-05-10): KOMPLETNO ✅**
- ruff ✅ · mypy ✅ · pytest 129 passed, 4 skipped · coverage 89.98% ✅
- document_grader, query_decomposer, adaptive_router, graph, agent_runner, conversation summarization implementirani i testirani ✅
- 19 agent tests (7 scenario + 5 routing + 3 component unit + 4 runtime safety) ✅
- `decide_next_step` bug fiksiran: exceptions se propagiraju do graph node-ova koji pozivaju sync fallback (`route_after_grade`) ✅
- `grade_node` safety check: LLM ne može forsirati "generate" kad sync rule kaže "decompose" ✅
- `quality_gate_node` safety check: ungrounded state nikad ne može rutirati na "respond" ✅
- `run_agent_query` wrapper: session save + human review queue insert + pipeline tracing ✅

---

## Phase 3B — Admin API

**Owner:** Backend Engineer
**Duration:** 2-3 days
**Requires:** Phase 2A (document upload triggers RAG ingestion; delete clears Qdrant + semantic cache), Phase 2B (Auth), Phase 2C (Observability)
**Parallel with:** Phase 3A, Phase 3C, Phase 2D

- [x] `POST /admin/documents/upload` — multipart upload, stores to `data/raw/`, triggers background ingestion
- [x] `GET /admin/documents` — list with status (pending / ingesting / ready / failed / needs_review)
- [x] `DELETE /admin/documents/{id}` — delete from filesystem, database (`document_chunks`, `ingestion_jobs`), invalidate semantic cache *(Qdrant point deletion deferred — best-effort; documented in route docstring)*
- [x] `POST /admin/documents/{id}/reindex` — re-run ingestion
- [x] `GET /admin/documents/{id}/status` — poll ingestion progress
- [x] `POST /admin/users` — create user with role
- [x] `DELETE /admin/users/{id}` — deactivate (soft delete)
- [x] `GET /admin/users` — list with role and status
- [x] `GET /admin/audit-logs` — paginated JSON, supports `?start=&end=&user_id=`
- [x] `GET /admin/audit-logs/export.csv` — full export
- [x] `GET /admin/feedback` — feedback list with linked trace_id and query *(in `observability_routes.py`, implemented in Phase 2C)*
- [x] `GET /admin/stats` — pilot summary: total queries, avg latency, fallback rate, cache hit rate, cost
- [x] `GET /admin/stats/cost` — cost breakdown by user and date range *(in `observability_routes.py`, implemented in Phase 2C)*
- [x] `GET /admin/review-queue` — admin sees pending human review items with query, draft answer, risk reason
- [x] `POST /admin/review-queue/{id}/approve` — sends approved answer back to user session
- [x] `POST /admin/review-queue/{id}/reject` — sends rejection with explanation
- [x] Background ingestion: write `ingestion_jobs` record (status=pending) before starting; run via `asyncio` task; update status to `ingesting` → `ready` / `failed` on completion
- [x] **Restart recovery**: on app startup, query `ingestion_jobs` for any records stuck in `ingesting` status (started > 10 minutes ago) and re-queue them — prevents documents being permanently stuck after container restart
- [ ] **Document versioning / ingestion locking**: when a document is reindexed, new chunks are written with `chunk_version = documents.version + 1`; Qdrant payload also carries `chunk_version` so retrieval can filter without joining Postgres; new version only becomes `active` after ingestion completes successfully (`documents.active_version` swapped atomically) — users never see a partial reindex
- [ ] **Document update flow**: `POST /admin/documents/{id}/upload-new-version` — uploads replacement file, triggers ingestion of new version, atomically swaps `active_version` on success; old Qdrant points are **not deleted immediately** — they are retained for 24h with `chunk_version < active_version` so a rollback is possible; a cleanup job (`scripts/cleanup_stale_chunks.py`) deletes them after 24h
- [x] Add `version` (integer, default 1) and `active_version` (integer, default 1) columns to `documents` table — columns present in DB model; migration applied

**Exit criteria:** upload → ingest → ready completes within 60s for 100-page PDF; all admin endpoints documented in `docs/api-reference.md`.

**Status Phase 3B (2026-05-11): KOMPLETNO ✅**
- 15 routes implemented in `app/api/admin_routes.py` + `app/api/observability_routes.py`
- `app/services/ingestion_service.py`: `run_ingestion()` background task + `recover_stuck_jobs()` restart recovery
- Admin rate limiting: `@limiter.limit("10/hour")` na upload, `@limiter.limit("100/minute")` na svih 7 GET /admin/* ruta ✅
- `IngestionStatus` enum renamed to match handoff frontend spec: `pending→queued`, `ingesting→embedding`, `ready→indexed`, `needs_review→skipped` — all usages in `admin_routes.py`, `ingestion_service.py`, `rag_pipeline.py`, `seed.py`, and test files updated ✅
- `/admin/documents` response extended with `chunk_count` (LEFT JOIN subquery on `document_chunks`) ✅
- `/admin/audit-logs` pagination: `offset` parameter (not `skip`) ✅
- 34 tests, 173 ukupno passed, 0 warnings; `admin_routes.py` coverage: 94%; total: 91%
- Deferred to Phase 4: full Qdrant point deletion on doc delete, `POST /admin/documents/{id}/upload-new-version` versioning flow

---

## Phase 3C — Agent Runtime Hardening

**Owner:** AI Agent Engineer / Backend Observability Engineer
**Duration:** 1-2 days
**Requires:** Phase 3A (LangGraph Agent Workflow), Phase 2C (Observability)
**Parallel with:** Phase 3B, Phase 2D after Phase 3A is functionally complete

Phase 3A establishes the working LangGraph agent. Phase 3C is a hardening pass: no new user-facing product scope, only runtime safety, observability depth, and regression tests discovered during Phase 3A verification.

### Node-Level Observability

- [x] Add a `PipelineSpan` or equivalent child span around each LangGraph node: `intake`, `rewrite`, `retrieve`, `grade`, `decompose`, `generate`, `output_filter`, `quality_gate`, `respond`, `fallback`
- [x] Each node span records: `session_id`, unique run `trace_id`, `current_step`, errors, retrieval attempt count, relevant chunk count where applicable
- [x] Keep the existing top-level `pipeline` span as the parent span for the full run
- [x] Add a test proving child spans created inside `PipelineSpan` are parented under the pipeline span, not orphaned — `test_node_span_parented_under_pipeline_span` ✅

### Trace Identity Per Agent Run

- [x] Generate a unique `trace_id` per `run_agent_query()` invocation when one is not provided
- [x] Store `session_id` as a span/audit attribute, not as a fallback trace identifier for multiple turns
- [x] Verify two turns in the same session produce distinct trace IDs but share the same `session_id`

### Router Safety Guards

- [x] Add a hard safety guard in `grade_node`: if fewer than 2 chunks are relevant, do not allow the LLM router to force `generate`; route to `decompose`
- [x] Keep the existing `quality_gate_node` guard: ungrounded state must never route to `respond`
- [x] Add regression tests for malicious/malformed router responses at both `grade` and `quality_gate`

### Output Filter Source Context Robustness

- [x] Track the source context used for generation: `generation_context: list[GradedChunk]` field in `PrivateAIState`, set by `generate_node` ✅
- [x] `output_filter_node` uses `state.generation_context` (fallback to live `graded_chunks.relevant`) ✅
- [x] `test_generation_context_captured_in_final_state` verifies snapshot is populated ✅

### Runtime Integration Tests

- [x] Add an integration test that runs through `run_agent_query()` rather than direct `graph.ainvoke()` only
- [x] Verify wrapper side effects together: graph execution → session save → human review queue insertion → pipeline tracing context
- [x] Add a test for retrieval/generation error paths ending in fallback with `requires_human_review=True`

### Session State Persistence Hardening

- [x] Update conversation tests to expect `state.model_dump(mode="json")`, not Python-mode `model_dump()`
- [x] Add max-size validation for `sessions.state_json` before saving; fail gracefully if state grows beyond configured limit *(1 MB limit in `conversation.py`, raises ValueError, tested)*
- [x] Schema/shape validation: `load_session` catches `pydantic.ValidationError` and re-raises as `ValueError("Invalid session state…")` ✅
- [x] Strip unsafe control characters `[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]` from message content in `save_session`; tabs and newlines preserved ✅

**Exit criteria:** node-level spans visible under a single pipeline trace; each agent turn has a unique trace ID; router safety guards prevent unsafe `generate/respond` transitions; output filter validates against the exact generation context; `run_agent_query()` integration test covers persistence, queue insertion, and tracing; full `pytest`, `mypy`, and coverage gate pass.

**Status Phase 3C (2026-05-11): KOMPLETNO ✅**
- Node-level `_node_span()` wraps all 10 LangGraph nodes; child span parenting verified by `test_node_span_parented_under_pipeline_span` ✅
- Trace identity: unique UUID per `run_agent_query()`; session_id as span attribute ✅
- Router safety guards: grade enforces decompose (<2 relevant); quality_gate blocks ungrounded respond ✅
- Output filter source context: `generation_context` snapshot in state, tested ✅
- `load_session` ValidationError → ValueError; `save_session` strips control chars ✅
- 173 tests passing, 0 warnings; mypy strict clean; ruff clean; total coverage 90.93% ✅

---

## Phase 4 — Web UI

**Owner:** Frontend Engineer
**Duration:** 3-4 days
**Requires:** Phase 3A + Phase 3B + Phase 3C

### Chat Interface (Pilot User)

- [x] Login page → credentials posted to `POST /auth/login` → JWT set as HTTP-Only cookie by server (frontend never touches the token)
- [x] Chat window: message input, history, SSE streaming with per-word token delivery, loading pipeline steps display
- [x] SSE streaming endpoint: `POST /chat/stream` — FastAPI `StreamingResponse`, `text/event-stream`; emits `step|token|cite|done` events; consumes `graph.astream()` node-by-node via `_STEP_MAP`
- [x] Citation drawer sidebar: opens when citation chip `[n]` is clicked; shows `SourceRow` per cited chunk
- [x] Feedback buttons (thumbs up / down) per answer → calls `POST /feedback`
- [x] Session persistence: reload → resume session
- [x] Suggested prompts empty state (3 cards: Policy / Finance / IT)

### Admin Panel

- [x] Document upload (drag-and-drop zone + file picker, status polling via `getDocumentStatus`)
- [x] Document list table (filename, type, chunk count from DB, status chip, actions: delete / reindex)
- [x] User management (list with role/active chip, deactivate → `DELETE /admin/users/{id}`)
- [x] Audit log viewer (paginated table: timestamp, user, query preview, latency; `offset` pagination)
- [x] Feedback viewer (list/detail split; shows trace ID, session ID, user ID, note — only fields backend returns)
- [x] Stats dashboard (total queries, avg latency, cache total hits count, total cost — only real backend fields)
- [x] Export button (audit CSV via `GET /admin/audit-logs/export.csv`)

### Technical

- [x] React + Vite (no SSR needed for pilot)
- [x] React Query for all API calls + 30s refetch intervals
- [x] Tailwind CSS with full handoff design token system (ink/paper/surface/accent/line color scale, Geist + Instrument Serif fonts)
- [x] Design built from handoff spec: `handoff/tokens.css`, `handoff/component-contracts.ts`, `handoff/tailwind.config.ts`
- [x] `VITE_API_URL` env var (default empty = relative paths; nginx proxies API to backend)
- [x] Separate `frontend/Dockerfile` (multi-stage Node→Nginx) + `nginx.conf` (SPA fallback + SSE-safe `proxy_buffering off`)
- [x] `npm run build` via `node --no-warnings=ExperimentalWarning` — zero output warnings (Node 22.6+ type-stripping warning suppressed)
- [x] Auth guards: `RequireAuth` + `RequireAdmin` HOC wrapping all routes in `App.tsx`
- [x] `src/api/` layer matches exact backend response shapes: `uploaded_at` (not `created_at`), `doc_id` (not `id`) from upload, `offset` (not `skip`) for audit pagination, `cache_total_hits` (count, not rate), `avg_latency_ms` mapped to `avgMs`
- [x] `AuditKind` includes `"fallback"`; `mapKind()` handles all 5 kinds

**Exit criteria:** non-technical pilot user logs in, asks a question, sees cited answer with SSE streaming, rates it with thumbs up/down — all without touching a terminal.

**Status Phase 4 (2026-05-11): KOMPLETNO ✅**
- `POST /chat/stream` SSE endpoint: LangGraph `astream()` → `step/token/cite/done` events; backend `chat_routes.py` ✅
- Frontend rebuilt from scratch per handoff design (`handoff/` directory + `private-ai-standalone.html` prototype) ✅
- Atoms: Avatar, Button (5 variants × 3 sizes), Chip (5 tones × 2 variants), Logo ✅
- Chat components: StreamingPipeline, CitationChip, TrustSignal, SourceRow, AnswerBlock, Composer, MessageBubble, SuggestedPrompt ✅
- Admin components: Sparkline, DocumentRow, ActivityEvent, FeedbackListItem ✅
- Pages: LoginPage, ChatPage, AdminLayout, DocumentsPage, ActivityPage, OverviewPage, FeedbackPage, UsersPage ✅
- All frontend↔backend API contracts verified and corrected (5 bugs fixed post code-review): upload `doc_id` mapping, audit `offset` pagination, `DELETE` for deactivate, `chunk_count` backend subquery, real-field-only stats/feedback adapters ✅
- `npm run build`: 0 TypeScript errors, 0 Vite warnings, 0 Node warnings ✅
- Backend tests: 34 passed in `test_admin.py` (including `chunk_count` subquery test) ✅

### Phase 4 Follow-up Scope — Deferred UI/API Work Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this follow-up task-by-task. Keep each task independently shippable and verify backend API shape before touching the UI.

**Goal:** Convert the deferred handoff/UI audit items into explicit future work, while preserving the current Phase 4 completion status.

**Architecture:** Four items are real feature work because the frontend cannot render them without additional backend/API contracts. Two audit items are explicitly closed as no-change decisions: the logo triangle claim was verified incorrect, and ±2px button-height tuning is too fine-grained for pilot value.

**Tech Stack:** FastAPI + SQLAlchemy + Qdrant client on backend; React + Vite + React Query + Tailwind CSS on frontend; pytest for backend route/model tests; `npm run build` for frontend verification.

#### Files and responsibility map

- `safe4ai-pilot/app/api/admin_routes.py` — add admin-only document/chunk/audit helper routes that support the deferred UI panels.
- `safe4ai-pilot/app/db/models.py` — extend persistence only if a feature cannot be served from existing `AuditLog`, `Document`, or `DocumentChunk` rows.
- `safe4ai-pilot/app/services/rag_pipeline.py` — update ingestion persistence only if chunk detail is moved from Qdrant-only payloads into Postgres.
- `safe4ai-pilot/tests/test_admin.py` — backend route regression tests for document inspector, audit kind counts, and chunk detail endpoint.
- `safe4ai-pilot/tests/test_rag_pipeline.py` / `safe4ai-pilot/tests/test_models.py` — only needed if chunk schema/persistence changes.
- `safe4ai-pilot/frontend/src/api/documents.ts` — add typed API client functions for document inspector data.
- `safe4ai-pilot/frontend/src/api/audit.ts` — add typed API client function for per-kind audit counts.
- `safe4ai-pilot/frontend/src/api/chat.ts` — extend `SseCite` only after backend streaming emits stable chunk/detail identifiers.
- `safe4ai-pilot/frontend/src/pages/admin/DocumentsPage.tsx` — host the right-side inspector panel once its data contract exists.
- `safe4ai-pilot/frontend/src/pages/admin/ActivityPage.tsx` — host the left filter rail once per-kind counts exist.
- `safe4ai-pilot/frontend/src/components/chat/CitationChip.tsx` — host hover/focus popover behavior once citation detail can be hydrated.
- `safe4ai-pilot/frontend/src/components/chat/SourceRow.tsx` — show excerpt/location only after `SseCite` or `GET /chunks/{id}` exposes those fields.
- `safe4ai-pilot/frontend/src/components/Logo.tsx` — no work planned; current triangle matches the verified design.
- `safe4ai-pilot/frontend/src/components/Button.tsx` — no work planned for ±2px height deltas; current button sizing is accepted for pilot.

#### Task 4.F1 — DocumentsPage right-side inspector panel

**Status:** Deferred because the UI needs `DocumentInspectorProps` and a retrieval-series backend contract that does not exist today.

**Current evidence:** `DocumentsPage.tsx` only tracks `selected: string | null` and renders a list; `DocumentRecord` in `frontend/src/api/documents.ts` has `{id, name, type, size, bytes, chunks, status, addedAt, addedBy, note?}` only. Backend retrieval attempts exist in runtime state (`PrivateAIState.retrieval_attempts`, `graded_chunks`, `retrieval_score_max`) but are not persisted in `app/db/models.py`.

- [ ] **Step 1: Write backend failing test for document inspector response**

  Modify `safe4ai-pilot/tests/test_admin.py` with a test in `TestDocumentList`:

  ```python
  def test_get_document_inspector_returns_document_summary_and_retrieval_series(self) -> None:
      admin = _make_admin_user()
      db = _mock_db_with_admin(admin)
      doc = _make_document()
      db.get.side_effect = lambda model, pk: admin if model is User else doc

      with patch("pathlib.Path.mkdir"):
          client = _make_test_client(db, admin)
          resp = client.get("/admin/documents/doc-1/inspector")

      assert resp.status_code == 200
      body = resp.json()
      assert body["document"]["id"] == "doc-1"
      assert body["document"]["filename"] == "test.pdf"
      assert body["retrieval_series"] == []
      from app.main import app
      app.dependency_overrides.clear()
  ```

- [ ] **Step 2: Run backend red test**

  Run: `pytest tests/test_admin.py::TestDocumentList::test_get_document_inspector_returns_document_summary_and_retrieval_series -v`

  Expected: FAIL with `404 Not Found` because `/admin/documents/{doc_id}/inspector` is not implemented.

- [ ] **Step 3: Add minimal backend route**

  Modify `safe4ai-pilot/app/api/admin_routes.py` near the existing document status route:

  ```python
  @router.get("/admin/documents/{doc_id}/inspector")
  def get_document_inspector(
      doc_id: str,
      db: Session = Depends(get_db),
      _admin: User = Depends(require_role("admin")),
  ) -> dict[str, Any]:
      doc = db.get(Document, doc_id)
      if doc is None:
          raise HTTPException(status_code=404, detail="Document not found")
      return {
          "document": {
              "id": doc.id,
              "filename": doc.filename,
              "file_type": doc.file_type,
              "ingestion_status": doc.ingestion_status,
              "uploaded_at": doc.uploaded_at,
              "version": doc.version,
              "active_version": doc.active_version,
          },
          "retrieval_series": [],
      }
  ```

  This intentionally returns an empty `retrieval_series` until retrieval events are persisted; it gives the frontend a stable shape without inventing fake metrics.

- [ ] **Step 4: Run backend green test**

  Run: `pytest tests/test_admin.py::TestDocumentList::test_get_document_inspector_returns_document_summary_and_retrieval_series -v`

  Expected: PASS.

- [ ] **Step 5: Add frontend API type and client**

  Modify `safe4ai-pilot/frontend/src/api/documents.ts`:

  ```ts
  export interface RetrievalSeriesPoint {
    ts: string;
    score: number;
    query: string;
  }

  export interface DocumentInspectorResponse {
    document: {
      id: string;
      filename: string;
      file_type: string;
      ingestion_status: string;
      uploaded_at: string;
      version: number;
      active_version: number;
    };
    retrieval_series: RetrievalSeriesPoint[];
  }

  export const getDocumentInspector = (id: string) =>
    apiFetch<DocumentInspectorResponse>(`/admin/documents/${id}/inspector`);
  ```

- [ ] **Step 6: Create focused inspector component**

  Create `safe4ai-pilot/frontend/src/components/admin/DocumentInspector.tsx`:

  ```tsx
  import type { DocumentInspectorResponse } from "../../api/documents";
  import Chip from "../Chip";

  interface Props {
    data: DocumentInspectorResponse | null;
    loading: boolean;
    onClose: () => void;
  }

  export default function DocumentInspector({ data, loading, onClose }: Props) {
    return (
      <aside className="w-80 shrink-0 border-l border-line bg-surface px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-kicker text-text-mute">Document inspector</p>
            <h2 className="mt-1 text-[14px] font-semibold text-ink">
              {loading ? "Loading…" : data?.document.filename ?? "No document selected"}
            </h2>
          </div>
          <button onClick={onClose} className="text-text-mute hover:text-text-2">×</button>
        </div>

        {data && (
          <div className="mt-4 space-y-4">
            <div className="rounded-xl border border-line bg-paper px-3 py-3 text-[12px]">
              <div className="flex justify-between"><span className="text-text-mute">Type</span><span>{data.document.file_type}</span></div>
              <div className="mt-1 flex justify-between"><span className="text-text-mute">Version</span><span>{data.document.active_version}</span></div>
              <div className="mt-2"><Chip tone="neutral">{data.document.ingestion_status}</Chip></div>
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-kicker text-text-mute">Retrieval series</p>
              {data.retrieval_series.length === 0 ? (
                <p className="mt-2 text-[12px] text-text-3">No persisted retrieval series yet.</p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {data.retrieval_series.map((point) => (
                    <li key={`${point.ts}-${point.query}`} className="rounded-lg border border-line px-3 py-2 text-[12px]">
                      <span className="font-mono text-text-mute">{Math.round(point.score * 100)}%</span> {point.query}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </aside>
    );
  }
  ```

- [ ] **Step 7: Wire inspector into DocumentsPage**

  Modify `safe4ai-pilot/frontend/src/pages/admin/DocumentsPage.tsx` to import `useQuery`, `getDocumentInspector`, and `DocumentInspector`; query only when `selected` is set; render the inspector as a right-side sibling of the existing document list.

  ```tsx
  const { data: inspector, isLoading: inspectorLoading } = useQuery({
    queryKey: ["document-inspector", selected],
    queryFn: () => getDocumentInspector(selected!),
    enabled: !!selected,
  });
  ```

  Render:

  ```tsx
  {selected && (
    <DocumentInspector
      data={inspector ?? null}
      loading={inspectorLoading}
      onClose={() => setSelected(null)}
    />
  )}
  ```

- [ ] **Step 8: Run verification**

  Run: `pytest tests/test_admin.py::TestDocumentList::test_get_document_inspector_returns_document_summary_and_retrieval_series -v`

  Run: `npm run build`

  Expected: backend test PASS; frontend build exits 0.

#### Task 4.F2 — ActivityPage left filter rail with per-kind counts and API pagination state

**Status:** Deferred because the UI needs counts from API and the filter state must be wired into real backend pagination. Current `listAuditLogs()` only fetches `/admin/audit-logs?offset=&limit=` and maps rows into `AuditEvent`.

**Current evidence:** `frontend/src/api/audit.ts` has `AuditKind = "query" | "upload" | "feedback" | "login" | "fallback"`; backend `AuditLog.action_type` is the grouping field; `/admin/audit-logs` and `/admin/audit-logs/export.csv` exist, but no counts endpoint exists.

- [ ] **Step 1: Write backend failing test for kind counts**

  Add to `safe4ai-pilot/tests/test_admin.py` under `TestAuditLogs`:

  ```python
  def test_audit_kind_counts_returns_counts_by_action_type(self) -> None:
      admin = _make_admin_user()
      db = _mock_db_with_admin(admin)
      db.query.return_value.group_by.return_value.all.return_value = [("query", 2), ("upload", 1)]

      with patch("pathlib.Path.mkdir"):
          client = _make_test_client(db, admin)
          resp = client.get("/admin/audit-logs/kind-counts")

      assert resp.status_code == 200
      assert resp.json() == {"query": 2, "upload": 1, "feedback": 0, "login": 0, "fallback": 0}
      from app.main import app
      app.dependency_overrides.clear()
  ```

- [ ] **Step 2: Run backend red test**

  Run: `pytest tests/test_admin.py::TestAuditLogs::test_audit_kind_counts_returns_counts_by_action_type -v`

  Expected: FAIL with `404 Not Found`.

- [ ] **Step 3: Add minimal backend endpoint**

  Modify `safe4ai-pilot/app/api/admin_routes.py` near the audit routes:

  ```python
  @router.get("/admin/audit-logs/kind-counts")
  def audit_kind_counts(
      db: Session = Depends(get_db),
      _admin: User = Depends(require_role("admin")),
  ) -> dict[str, int]:
      allowed = {"query", "upload", "feedback", "login", "fallback"}
      counts = {kind: 0 for kind in allowed}
      rows = db.query(AuditLog.action_type, func.count(AuditLog.id)).group_by(AuditLog.action_type).all()
      for action_type, count in rows:
          if action_type in counts:
              counts[str(action_type)] = int(count)
      return counts
  ```

- [ ] **Step 4: Add frontend API client**

  Modify `safe4ai-pilot/frontend/src/api/audit.ts`:

  ```ts
  export type AuditKindCounts = Record<AuditKind, number>;

  export const getAuditKindCounts = () =>
    apiFetch<AuditKindCounts>("/admin/audit-logs/kind-counts");
  ```

- [ ] **Step 5: Add left rail UI in ActivityPage**

  Modify `safe4ai-pilot/frontend/src/pages/admin/ActivityPage.tsx` to query counts and keep selected kind in local state. The final implementation must reset `page` to `0` whenever `kind` changes, and `listAuditLogs()` must receive the active kind so pagination is server-backed, not just client-filtered after fetching one page:

  ```tsx
  const [kind, setKind] = useState<AuditKind | "all">("all");
  const { data: counts } = useQuery({ queryKey: ["audit-kind-counts"], queryFn: getAuditKindCounts });

  function selectKind(next: AuditKind | "all") {
    setKind(next);
    setPage(0);
  }
  ```

  Render a `w-48` left rail with buttons for `all`, `query`, `upload`, `feedback`, `login`, and `fallback`; each button calls `selectKind(nextKind)`.

- [ ] **Step 6: Wire audit API pagination to selected kind**

  Modify `safe4ai-pilot/frontend/src/api/audit.ts`:

  ```ts
  export const listAuditLogs = (offset = 0, limit = 50, kind: AuditKind | "all" = "all") => {
    const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
    if (kind !== "all") params.set("kind", kind);
    return apiFetch<RawAudit[]>(`/admin/audit-logs?${params.toString()}`).then((rows) =>
      rows.map(
        (r): AuditEvent => ({
          id: r.id,
          ts: r.timestamp,
          kind: mapKind(r.action_type),
          who: r.user_id,
          query: r.query_text ?? undefined,
          latencyMs: r.latency_ms ?? undefined,
          traceId: r.trace_id ?? undefined,
        }),
      ),
    );
  };
  ```

  Modify `safe4ai-pilot/frontend/src/hooks/useAuditStream.ts` so the query key includes `kind` and calls `listAuditLogs(page * limit, limit, kind)`. Keep `limit = 50` unchanged.

- [ ] **Step 7: Add backend kind filter to audit log route**

  Modify `safe4ai-pilot/app/api/admin_routes.py` in `list_audit_logs()`:

  ```python
  kind: str | None = None,
  ```

  Add after the existing optional filters:

  ```python
  if kind:
      q = q.filter(AuditLog.action_type == kind)
  ```

- [ ] **Step 8: Run verification**

  Run: `pytest tests/test_admin.py::TestAuditLogs::test_audit_kind_counts_returns_counts_by_action_type -v`

  Run: `npm run build`

  Expected: backend test PASS; frontend build exits 0.

#### Task 4.F3 — CitationChip hover popover and chunk detail API

**Status:** Deferred because `CitationChip` receives only a display id and `SseCite` currently lacks a backend-resolvable chunk id or excerpt. There is also no `GET /chunks/{id}` route.

**Current evidence:** `frontend/src/api/chat.ts` defines `SseCite` as `{ id, file, page, score }`. `CitationChip.tsx` only calls `onOpen(id)`. Streaming backend emits only `id`, `file`, `page`, and `score`; full chunk content exists in Qdrant payloads and `DocumentChunk.qdrant_point_id`, not in the SSE shape.

- [ ] **Step 1: Write backend failing test for chunk detail endpoint**

  Add to `safe4ai-pilot/tests/test_admin.py`:

  ```python
  def test_get_chunk_detail_returns_preview_and_document_filename(self) -> None:
      admin = _make_admin_user()
      db = _mock_db_with_admin(admin)
      doc = _make_document()
      chunk = MagicMock()
      chunk.id = "chunk-1"
      chunk.document_id = "doc-1"
      chunk.chunk_index = 3
      chunk.chunk_version = 1
      chunk.content_preview = "Policy excerpt"
      chunk.qdrant_point_id = "point-1"
      db.get.side_effect = lambda model, pk: admin if model is User else chunk
      db.query.return_value.filter.return_value.first.return_value = doc

      with patch("pathlib.Path.mkdir"):
          client = _make_test_client(db, admin)
          resp = client.get("/admin/chunks/chunk-1")

      assert resp.status_code == 200
      body = resp.json()
      assert body["id"] == "chunk-1"
      assert body["filename"] == "test.pdf"
      assert body["excerpt"] == "Policy excerpt"
      from app.main import app
      app.dependency_overrides.clear()
  ```

- [ ] **Step 2: Run backend red test**

  Run: `pytest tests/test_admin.py::test_get_chunk_detail_returns_preview_and_document_filename -v`

  Expected: FAIL with `404 Not Found`.

- [ ] **Step 3: Add minimal chunk detail endpoint**

  Modify `safe4ai-pilot/app/api/admin_routes.py`:

  ```python
  @router.get("/admin/chunks/{chunk_id}")
  def get_chunk_detail(
      chunk_id: str,
      db: Session = Depends(get_db),
      _admin: User = Depends(require_role("admin")),
  ) -> dict[str, Any]:
      chunk = db.get(DocumentChunk, chunk_id)
      if chunk is None:
          raise HTTPException(status_code=404, detail="Chunk not found")
      doc = db.query(Document).filter(Document.id == chunk.document_id).first()
      return {
          "id": chunk.id,
          "document_id": chunk.document_id,
          "filename": doc.filename if doc else "Unknown document",
          "page": None,
          "chunk_index": chunk.chunk_index,
          "excerpt": chunk.content_preview,
          "qdrant_point_id": chunk.qdrant_point_id,
      }
  ```

  This gives the popover a safe preview immediately. If exact page/full text is required, add a later persistence task to store `page_number` and full `content` in `DocumentChunk` during ingestion.

- [ ] **Step 4: Extend frontend citation type only after backend can identify chunks**

  Modify `safe4ai-pilot/frontend/src/api/chat.ts` only if streaming emits a real `chunkId`:

  ```ts
  export interface SseCite { id: string; file: string; page: number; score: number; chunkId?: string }

  export interface ChunkDetail {
    id: string;
    document_id: string;
    filename: string;
    page: number | null;
    chunk_index: number;
    excerpt: string;
    qdrant_point_id: string | null;
  }

  export const getChunkDetail = (chunkId: string) =>
    apiFetch<ChunkDetail>(`/admin/chunks/${chunkId}`);
  ```

- [ ] **Step 5: Add hover/focus popover to CitationChip**

  Modify `safe4ai-pilot/frontend/src/components/chat/CitationChip.tsx` so it remains a button and shows a small absolute-positioned panel on hover/focus. Do not add global positioning libraries until this simple version fails in browser testing.

  ```tsx
  interface Props {
    id: string;
    active?: boolean;
    excerpt?: string;
    onOpen?: (id: string) => void;
  }
  ```

  Render popover only when `excerpt` is present:

  ```tsx
  {excerpt && (
    <span className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden w-64 -translate-x-1/2 rounded-lg border border-line bg-surface px-3 py-2 text-left text-[12px] text-text shadow-lg group-hover:block group-focus-visible:block">
      {excerpt}
    </span>
  )}
  ```

- [ ] **Step 6: Run verification**

  Run: `pytest tests/test_admin.py::test_get_chunk_detail_returns_preview_and_document_filename -v`

  Run: `npm run build`

  Expected: backend test PASS; frontend build exits 0.

#### Task 4.F4 — SourceRow blockquote excerpt/location support

**Status:** Deferred because current streaming citations do not include excerpt or location metadata beyond page.

**Current evidence:** `SourceRow` takes `SseCite`; `SseCite` is only `{ id, file, page, score }`. Backend `Citation` has `excerpt`, but the SSE path strips it down before the frontend receives it.

- [ ] **Step 1: Decide data source before UI work**

  Use one of these two concrete approaches:

  1. **Preferred for pilot:** Extend the SSE `cite` event to include `excerpt` from backend `Citation`, then update `SseCite` and `SourceRow` directly.
  2. **Preferred for detailed inspection:** Use `GET /admin/chunks/{chunk_id}` from Task 4.F3 and hydrate excerpts on demand.

  Do not hardcode fake excerpts in frontend.

- [ ] **Step 2: If using SSE, write backend streaming test**

  Modify `safe4ai-pilot/tests/test_chat.py` to assert the `cite` event includes `excerpt`:

  ```python
  assert cite_payload["excerpt"] == "Expected excerpt text"
  ```

  Run: `pytest tests/test_chat.py -k cite -v`

  Expected before backend change: FAIL because `excerpt` is absent.

- [ ] **Step 3: Update `SseCite` and SourceRow**

  Modify `safe4ai-pilot/frontend/src/api/chat.ts`:

  ```ts
  export interface SseCite { id: string; file: string; page: number; score: number; excerpt?: string; loc?: string }
  ```

  Modify `safe4ai-pilot/frontend/src/components/chat/SourceRow.tsx`:

  ```tsx
  {source.excerpt && (
    <blockquote className="mt-2 border-l-2 border-line pl-2 text-[11.5px] leading-5 text-text-3">
      {source.excerpt}
    </blockquote>
  )}
  {source.loc && <p className="mt-1 text-[10.5px] text-text-mute">{source.loc}</p>}
  ```

- [ ] **Step 4: Run verification**

  Run: `pytest tests/test_chat.py -k cite -v`

  Run: `npm run build`

  Expected: backend cite-shape test PASS; frontend build exits 0.

#### Task 4.F5 — Session sidebar (ChatB) with session history API

**Status:** Deferred because `ChatPage.tsx` has a single active session flow and backend only resolves/creates sessions through `POST /chat` / `POST /chat/stream`. There is no session history/list API today.

**Current evidence:** `app/services/conversation.py` supports `new_session()`, `load_session()`, `save_session()`, and `get_recent_messages()`, but `app/api/chat_routes.py` exposes no `GET /sessions` or `GET /sessions/{id}`. Frontend `ChatPage.tsx` stores only the current chat state from `useChat()` and has no sidebar/history data source.

- [ ] **Step 1: Write backend failing test for session list**

  Add to `safe4ai-pilot/tests/test_chat.py`:

  ```python
  def test_list_sessions_returns_current_user_sessions() -> None:
      user = _make_user("user-1")
      db = MagicMock()
      rows = [MagicMock(id="sess-1", updated_at="2026-05-11T10:00:00Z", state_json={"messages": []})]
      db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = rows
      client = _make_chat_client(db, user)

      resp = client.get("/sessions")

      assert resp.status_code == 200
      assert resp.json()[0]["id"] == "sess-1"
  ```

  If `_make_user` / `_make_chat_client` do not exist in `tests/test_chat.py`, create them following the same dependency override pattern used in `tests/test_admin.py::_make_test_client()`.

- [ ] **Step 2: Run backend red test**

  Run: `pytest tests/test_chat.py::test_list_sessions_returns_current_user_sessions -v`

  Expected: FAIL with `404 Not Found` because `/sessions` is not implemented.

- [ ] **Step 3: Add session list endpoint**

  Modify `safe4ai-pilot/app/api/chat_routes.py`:

  ```python
  @router.get("/sessions")
  def list_sessions(
      current_user: User = Depends(get_current_user),
      db: Session = Depends(get_db),
  ) -> list[dict[str, Any]]:
      rows = (
          db.query(DbSession)
          .filter(DbSession.user_id == str(current_user.id))
          .order_by(DbSession.updated_at.desc())
          .limit(50)
          .all()
      )
      return [
          {
              "id": row.id,
              "updated_at": row.updated_at,
              "title": _session_title(row.state_json),
          }
          for row in rows
      ]

  def _session_title(state_json: dict[str, Any]) -> str:
      messages = state_json.get("messages", []) if isinstance(state_json, dict) else []
      for message in messages:
          if isinstance(message, dict) and message.get("role") == "user":
              content = str(message.get("content", "")).strip()
              return content[:64] or "Untitled session"
      return "Untitled session"
  ```

  Import `Any` and the SQLAlchemy `Session` DB model alias if not already present:

  ```python
  from typing import Any
  from app.db.models import Session as DbSession
  ```

- [ ] **Step 4: Add frontend API client and sidebar component**

  Create `safe4ai-pilot/frontend/src/api/sessions.ts`:

  ```ts
  import { apiFetch } from "./client";

  export interface ChatSessionSummary {
    id: string;
    title: string;
    updated_at: string;
  }

  export const listSessions = () => apiFetch<ChatSessionSummary[]>("/sessions");
  ```

  Create `safe4ai-pilot/frontend/src/components/chat/SessionSidebar.tsx`:

  ```tsx
  import type { ChatSessionSummary } from "../../api/sessions";

  interface Props {
    sessions: ChatSessionSummary[];
    activeSessionId: string | null;
    onSelect: (id: string) => void;
    onNew: () => void;
  }

  export default function SessionSidebar({ sessions, activeSessionId, onSelect, onNew }: Props) {
    return (
      <aside className="w-64 shrink-0 border-r border-line bg-surface-2 px-3 py-3">
        <button onClick={onNew} className="mb-3 w-full rounded-lg bg-ink px-3 py-2 text-[12px] font-medium text-paper">
          New chat
        </button>
        <div className="space-y-1">
          {sessions.map((session) => (
            <button
              key={session.id}
              onClick={() => onSelect(session.id)}
              className={[
                "w-full rounded-lg px-3 py-2 text-left text-[12px] transition-colors",
                activeSessionId === session.id ? "bg-accent text-white" : "text-text-2 hover:bg-surface",
              ].join(" ")}
            >
              <span className="block truncate">{session.title}</span>
            </button>
          ))}
        </div>
      </aside>
    );
  }
  ```

- [ ] **Step 5: Wire sidebar into ChatPage**

  Modify `safe4ai-pilot/frontend/src/pages/ChatPage.tsx` to query `listSessions()` and render `SessionSidebar` as the left sibling of the existing main column. Selecting a session must call a `useChat()` method that loads/replaces the active `sessionId`; if that hook lacks the method, add it before wiring the UI.

- [ ] **Step 6: Run verification**

  Run: `pytest tests/test_chat.py::test_list_sessions_returns_current_user_sessions -v`

  Run: `npm run build`

  Expected: backend test PASS; frontend build exits 0.

#### Task 4.F6 — Follow-up suggestions after answer generation

**Status:** Deferred because suggestions require LLM inference at answer time or deterministic backend generation from the final answer/citations. The current SSE `done` event does not include suggestions.

**Current evidence:** `ChatPage.tsx` has static empty-state `SUGGESTED` prompts only. `api/chat.ts` defines `SseDone` without follow-up suggestions, and `app/api/chat_routes.py` emits `done` metadata for trace/session/model/cache only.

- [ ] **Step 1: Write backend failing test for suggestions in done event**

  Modify `safe4ai-pilot/tests/test_chat.py` to assert the stream `done` payload includes suggestions:

  ```python
  assert done_payload["followups"] == ["What policy section supports this?", "Who owns this workflow?"]
  ```

  Run: `pytest tests/test_chat.py -k followups -v`

  Expected before implementation: FAIL because `followups` is absent.

- [ ] **Step 2: Add backend response shape**

  Modify `safe4ai-pilot/app/api/chat_routes.py` so the final `done` event includes a stable `followups: list[str]` field. For the first implementation, use deterministic suggestions derived from answer state to avoid a second LLM call:

  ```python
  "followups": _build_followups(final_state),
  ```

  Add helper:

  ```python
  def _build_followups(state: PrivateAIState) -> list[str]:
      if not state.citations:
          return ["Which document should I search next?", "Can you rephrase the question with more detail?"]
      return [
          "Which source supports this answer most strongly?",
          "Can you summarize this as an action list?",
          "What related policy should I check next?",
      ]
  ```

- [ ] **Step 3: Add frontend type and render follow-ups**

  Modify `safe4ai-pilot/frontend/src/api/chat.ts`:

  ```ts
  export interface SseDone {
    traceId: string;
    latencyMs: number;
    cache: boolean;
    model: string;
    kRetrieved: number;
    sessionId: string;
    followups?: string[];
    error?: string;
  }
  ```

  Modify `safe4ai-pilot/frontend/src/hooks/useChat.ts` and `ChatPage.tsx` so the final assistant message stores and renders `followups`. Clicking a follow-up should set the composer text, not auto-submit.

- [ ] **Step 4: Run verification**

  Run: `pytest tests/test_chat.py -k followups -v`

  Run: `npm run build`

  Expected: backend follow-up test PASS; frontend build exits 0.

#### Task 4.F7 — Real sparkline data from time-series stats API

**Status:** Deferred because `OverviewPage.tsx` renders `Sparkline` with frontend/static card data, while backend `/admin/stats` returns aggregate totals only.

**Current evidence:** `frontend/src/pages/admin/OverviewPage.tsx` imports `Sparkline` and renders `s.data`; backend `app/api/admin_routes.py::get_stats()` aggregates totals, latency, cache hits, and cost, but has no time-series endpoint.

- [ ] **Step 1: Write backend failing test for stats timeseries**

  Add to `safe4ai-pilot/tests/test_admin.py` under stats tests:

  ```python
  def test_stats_timeseries_returns_daily_query_counts(self) -> None:
      admin = _make_admin_user()
      db = _mock_db_with_admin(admin)
      db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = [
          ("2026-05-11", 3),
      ]

      with patch("pathlib.Path.mkdir"):
          client = _make_test_client(db, admin)
          resp = client.get("/admin/stats/timeseries?days=7")

      assert resp.status_code == 200
      assert resp.json() == {"queries": [{"date": "2026-05-11", "count": 3}]}
      from app.main import app
      app.dependency_overrides.clear()
  ```

- [ ] **Step 2: Run backend red test**

  Run: `pytest tests/test_admin.py::test_stats_timeseries_returns_daily_query_counts -v`

  Expected: FAIL with `404 Not Found`.

- [ ] **Step 3: Add backend timeseries endpoint**

  Modify `safe4ai-pilot/app/api/admin_routes.py`:

  ```python
  @router.get("/admin/stats/timeseries")
  def get_stats_timeseries(
      days: int = 7,
      db: Session = Depends(get_db),
      _admin: User = Depends(require_role("admin")),
  ) -> dict[str, list[dict[str, Any]]]:
      since = datetime.now(UTC) - timedelta(days=days)
      rows = (
          db.query(func.date(AuditLog.timestamp), func.count(AuditLog.id))
          .filter(AuditLog.timestamp >= since, AuditLog.action_type == "query")
          .group_by(func.date(AuditLog.timestamp))
          .order_by(func.date(AuditLog.timestamp))
          .all()
      )
      return {"queries": [{"date": str(day), "count": int(count)} for day, count in rows]}
  ```

  Ensure `timedelta` is imported from `datetime` in `admin_routes.py`.

- [ ] **Step 4: Add frontend API client and wire Sparkline**

  Modify `safe4ai-pilot/frontend/src/api/stats.ts`:

  ```ts
  export interface StatsTimeseries {
    queries: { date: string; count: number }[];
  }

  export const getStatsTimeseries = (days = 7) =>
    apiFetch<StatsTimeseries>(`/admin/stats/timeseries?days=${days}`);
  ```

  Modify `safe4ai-pilot/frontend/src/pages/admin/OverviewPage.tsx` to query `getStatsTimeseries(stats.days)` and pass `timeseries.queries.map((p) => p.count)` into `Sparkline` instead of static/sample data.

- [ ] **Step 5: Run verification**

  Run: `pytest tests/test_admin.py::test_stats_timeseries_returns_daily_query_counts -v`

  Run: `npm run build`

  Expected: backend test PASS; frontend build exits 0.

#### Explicit no-change audit decisions

- [x] **Logo triangle audit claim — no change needed.** `safe4ai-pilot/frontend/src/components/Logo.tsx` already renders the verified triangle mark; the audit claim was incorrect.
- [x] **Button height ±2px — skip.** `safe4ai-pilot/frontend/src/components/Button.tsx` uses the accepted design-token sizing; a ±2px visual delta is too fine-grained to justify code churn for the pilot.

#### Self-review checklist for this follow-up plan

- [x] Every deferred item from both scopes is represented: Documents inspector, Activity filter rail and real pagination, Citation hover popover, SourceRow excerpt/location, Session sidebar, follow-up suggestions, real sparkline time-series data, Logo no-change, Button no-change.
- [x] No task asks the frontend to render data that the backend does not expose.
- [x] Backend routes are introduced with failing tests first.
- [x] Frontend build verification is listed for every UI-affecting task.
- [x] No fake metrics, fake excerpts, or prototype-only data are allowed in implementation.

---

## Phase 5 — Pilot Results & Report

**Owner:** Founder / Full-stack
**Duration:** 1-2 days (at end of pilot)
**Requires:** Phase 4

- [ ] Run `evaluation/offline_eval.py` on customer documents → attach results to report
- [ ] Run `evaluation/online_monitor.py` summary for pilot period
- [ ] Pull metrics from `GET /admin/stats` — total queries, avg latency, fallback rate, cache hit rate
- [ ] Collect user feedback summary from `GET /admin/feedback`
- [ ] Compute before/after comparison (manual, based on discovery baseline)
- [ ] Fill final report template:
  - Executive summary
  - Workflow tested and documents indexed
  - Users and total queries
  - Key findings (what AI answered well, what it missed)
  - Evaluation scores (retrieval recall, answer correctness)
  - Security and compliance gaps identified
  - Recommendation: stop / repeat / expand
  - Estimated production scope and cost
- [ ] Export report as PDF

**Exit criteria:** report is fillable and exportable after each pilot without additional development.

---

## Parallel Work Summary

| Phase | Requires | Parallel with |
|---|---|---|
| Phase 0 (Business) | Nothing | Phase 1 |
| Phase 1 (Infrastructure) | Nothing | Phase 0 |
| Phase 2A (RAG Core) | Phase 1 | 2B, 2C |
| Phase 2B (Security & Auth) | Phase 1 | 2A, 2C |
| Phase 2C (Observability) | Phase 1 | 2A, 2B |
| Phase 2D (Evaluation) | Phase 1 + **Phase 2A** | 3A, 3B, 3C (starts mid-Week 2 after 2A done) |
| Phase 3A (LangGraph Agents) | Phase 2A | 3B, 2D |
| Phase 3B (Admin API) | **Phase 2A** + 2B + 2C | 3A, 3C, 2D |
| Phase 3C (Agent Runtime Hardening) | Phase 3A + 2C | 3B, 2D |
| Phase 4 (UI) | Phase 3A + 3B + 3C | — |
| Phase 5 (Report) | Phase 4 | — |

## Engineer / Agent Assignments

| Phase | Role |
|---|---|
| Phase 0 | Founder / Sales |
| Phase 1 | Backend Engineer or DevOps |
| Phase 2A | ML Engineer (RAG, embeddings, reranking) |
| Phase 2B | Backend Engineer |
| Phase 2C | Backend Engineer (can be same as 2B) |
| Phase 2D | ML Engineer (can be same as 2A) |
| Phase 3A | AI Agent Engineer (LangGraph, self-correcting agents) |
| Phase 3B | Backend Engineer (can be same as 2B/2C) |
| Phase 3C | AI Agent Engineer + Backend Observability Engineer |
| Phase 4 | Frontend Engineer |
| Phase 5 | Founder / Full-stack |

## Total Estimated Duration (with parallelization)

```
Week 1:     Phase 0 + Phase 1 (parallel)
Week 2 M-W: Phase 2A + 2B + 2C start simultaneously (3 engineers)
Week 2 Th-F: Phase 2D starts as soon as 2A finishes (ML engineer pivots)
Week 3:     Phase 3A + 3B (parallel, 2 engineers); Phase 2D may still be running
Week 3 F:   Phase 3C hardening pass after Phase 3A stabilizes; can overlap with late 3B/2D
Week 4:     Phase 4 → Phase 5
```

Minimum: ~4 weeks with 3-4 engineers in parallel.
Solo: ~10-12 weeks sequentially.

---

## Overall Project Status (as of 2026-05-11)

| Phase | Status | Key metric |
|---|---|---|
| Phase 0 — Business Offer | ⬜ Not started | — |
| Phase 1 — Infrastructure | ✅ Complete | 12 tests, 92% cov, live smoke ✅ |
| Phase 2A — RAG Core | ✅ Complete | hybrid retrieve, rerank, HyDE, semantic cache, conversation |
| Phase 2B — Security & Auth | ✅ Complete | JWT, RBAC, brute-force, rate limits, guards, upload security |
| Phase 2C — Observability | ✅ Complete | OTel spans, feedback, cost tracker, APScheduler cleanup |
| Phase 2D — Evaluation | ✅ Complete | golden_dataset (20 Q&A), offline_eval, online_monitor |
| Phase 3A — LangGraph Agents | ✅ Complete | 10-node graph, self-correction loop, human review queue |
| Phase 3B — Admin API | ✅ Complete | 15 routes, ingestion jobs, rate limiting |
| Phase 3C — Agent Hardening | ✅ Complete | node spans, output filter context, state hardening |
| Phase 4 — Web UI | ✅ Complete | SSE streaming, handoff design, 8 pages, all API contracts verified |
| Phase 5 — Pilot Report | ⬜ Not started | — |

**Current codebase health (2026-05-11):**
- `pytest`: 177 passed, 4 skipped, **0 warnings** (backend only; frontend has no backend tests added this phase)
- Coverage: **88%** (`app/`) — gate at 80% ✅
- `mypy --strict`: **0 errors** (40 source files)
- `ruff check .`: **0 errors**
- `pip-audit`: **0 known CVEs**
- `npm run build` (frontend): **0 TypeScript errors, 0 Vite warnings, 0 Node warnings** ✅
