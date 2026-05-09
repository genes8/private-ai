# Safe4AI Private AI Pilot — Implementation Plan

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

[Phase 1: Infrastructure & Project Setup]  ←── START HERE, blocks everything
         │
    ┌────┴──────────────────────┐
    │                           │
[Phase 2A: RAG Core]   [Phase 2B: Security & Auth]
         │             [Phase 2C: Observability]
         │             (2B + 2C parallel with 2A)
         │
    ┌────┴──────────────────────┐
    │                           │
[Phase 2D: Evaluation]  [Phase 3A: Agents & LangGraph]
(needs 2A)              [Phase 3B: Admin API]
                        (3B needs 2A + 2B + 2C; 3A needs 2A only)
                        (3A and 3B parallel with each other)
                                │
                          [Phase 4: Web UI]
                                │
                          [Phase 5: Pilot Report]
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
- [x] `documents` — `(id, filename, storage_filename, file_type, ingestion_status ENUM[pending,ingesting,ready,failed,needs_review], uploaded_by, uploaded_at, doc_metadata, ingestion_started_at)`
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

- [ ] Dense retrieval: embedding similarity search via Qdrant (cosine, top-k=10)
- [ ] Sparse retrieval: BM25 keyword search over chunk content (`rank-bm25`)
- [ ] Hybrid fusion: Reciprocal Rank Fusion (RRF) to merge dense + sparse results
- [ ] Metadata filtering: filter by `document_ids` list to enforce access boundaries

### `app/components/reranker.py`

- [ ] Cross-encoder reranking using `cross-encoder/ms-marco-MiniLM-L-6-v2` (local, no API call)
- [ ] Input: top-20 from hybrid retriever; output: top-6 reranked by relevance score
- [ ] Expose `rerank(query: str, chunks: list[Chunk]) -> list[RankedChunk]`

### `app/services/rag_pipeline.py`

- [ ] Document ingestion:
  - PDF loader (`PyPDFLoader`, fallback `UnstructuredPDFLoader` for scanned)
  - DOCX loader (`Docx2txtLoader`)
  - XLSX loader (custom: iterate sheets, stringify rows with headers)
  - Plain text loader
  - LLM vision OCR for scanned PDFs (`qwen2.5vl:7b` via Ollama, applied only to pages with < 50 chars of native text) — see LLM Vision OCR section above
  - Store raw to `data/raw/`, processed chunks to `data/processed/`
  - Store chunk metadata in `document_chunks` table
- [ ] Chunking: `RecursiveCharacterTextSplitter` chunk_size=800, overlap=150; preserve `{doc_id, filename, page_number, chunk_index}` per chunk
- [ ] Embedding: batch via `nomic-embed-text` (Ollama), 100 chunks/batch, retry on failure
- [ ] Store vectors + metadata payload in Qdrant collection
- [ ] Query path: call hybrid retriever → reranker → return `list[RankedChunk]`

### LLM Vision OCR (`app/services/rag_pipeline.py` — ingestion)

OCR is done via a vision-capable LLM (not Tesseract) for better accuracy on complex layouts, handwriting, mixed languages, and tables.

- [ ] PDF page → image: use `pdf2image.convert_from_path()` (requires `poppler-utils`), 200 DPI, PNG output to temp directory
- [ ] For each page image, call `qwen2.5vl:7b` via Ollama vision API:
  - System: "Extract all text from this document page exactly as it appears. Preserve structure, headers, tables, and lists. Return only the extracted text."
  - Attach image as base64 in the request
  - Response is the extracted text — treat same as text from native PDF extraction
- [ ] OCR is applied only when native text extraction yields < 50 characters per page (i.e. page is an image or scanned)
- [ ] **Quality gate**: ask the same vision model to self-assess: "Rate your confidence in the text extraction on this page: high / medium / low. Return JSON `{confidence, reason}`."
  - `low` → mark chunk metadata `ocr_quality = "low"`, set `documents.ingestion_status = "needs_review"` if > 50% of pages are low
  - `medium` or `high` → proceed normally
- [ ] Admin sees "needs_review" documents in list with warning; can approve or delete
- [ ] Low-confidence chunks included in retrieval but citation shows: "Source quality: low (scanned document — review recommended)"
- [ ] Remove `pytesseract` and Tesseract apt packages entirely from stack

### `app/services/query_rewriter.py`

- [ ] HyDE (Hypothetical Document Embeddings): generate a hypothetical answer, embed it, use that embedding for retrieval instead of the raw query — improves retrieval for vague questions
- [ ] Query expansion: add synonyms / rephrased variants, merge results
- [ ] Prompt loaded from registry: `get_prompt("query_rewriter", "v1")`
- [ ] Falls back to original query if rewrite fails

### `app/services/semantic_cache.py`

- [ ] Cache LLM responses keyed by query embedding (not exact string match)
- [ ] Cache hit threshold: cosine similarity > 0.92 (configurable via env)
- [ ] Store: `{embedding, query, response, citations, created_at}` in PostgreSQL (`semantic_cache` table with pgvector — Redis not used)
- [ ] Cache invalidation: per document (when document is deleted or reindexed, clear related cache entries)
- [ ] Log cache hit/miss to observability tracer

### `app/services/conversation.py`

- [ ] Load session state from `sessions` table
- [ ] Maintain `messages` list (last 10 turns passed to LLM)
- [ ] Save updated state after each turn
- [ ] `new_session(user_id) -> session_id`
- [ ] `load_session(session_id) -> PrivateAIState`
- [ ] `save_session(state: PrivateAIState)`

### `app/services/query_router.py`

- [ ] Route query to correct Qdrant collection (if multiple document sets indexed)
- [ ] Rule-based first (collection name from session config); LLM-assisted if ambiguous
- [ ] Returns: `{collection: str, confidence: float, reason: str}`

### Citation Tracking

- [ ] Every generated answer links to `chunk_ids` used as context
- [ ] Citation schema: `{filename, page_number, excerpt (first 200 chars), score}`
- [ ] No-answer fallback: if top chunk score < 0.45 after reranking → do not generate, return fixed fallback string

### Integration Test

- [ ] Upload 20-page PDF → query → cited answer with filename + page number
- [ ] Hybrid retrieval returns better results than dense-only on keyword query
- [ ] Semantic cache returns cached response on paraphrased repeat query
- [ ] Out-of-scope question triggers no-answer fallback

**Exit criteria:** ingest → embed → hybrid retrieve → rerank → cited answer works for PDF, DOCX, and scanned image PDF.

---

## Phase 2B — Security & Auth

**Owner:** Backend Engineer
**Duration:** 4-5 days
**Requires:** Phase 1
**Parallel with:** Phase 2A, 2C

### Auth

- [ ] JWT authentication (`PyJWT[crypto]`, **ne** `python-jose` — python-jose ima CVE-2024-33663/33664 algorithm confusion attacks bez fixa)
  - `POST /auth/login` — email + password → JWT set as **HTTP-Only, Secure, SameSite=Strict cookie** (never in response body or localStorage)
  - `POST /auth/logout` — clears the cookie server-side
  - Access token expiry: 8 hours; cookie `Max-Age` matches
  - HTTPS required in production; `Secure` flag enforced via env (`ENFORCE_HTTPS=true`)
  - API: `jwt.encode(payload, SECRET_KEY, algorithm="HS256")` / `jwt.decode(token, SECRET_KEY, algorithms=["HS256"])`
- [ ] CSRF protection: `SameSite=Strict` covers same-origin requests; if cross-origin ever needed, add CSRF double-submit cookie pattern
- [ ] RBAC middleware: read JWT from cookie on every request; `admin` and `pilot_user` enforced
- [ ] Role decorators: `@require_role("admin")`, `@require_role("pilot_user")`

### Password Hashing

- [ ] `passlib[bcrypt]` — `pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")`
- [ ] `verify_password(plain, hashed)` and `hash_password(plain)` — only two password-touching functions in the codebase
- [ ] Minimum password length: 12 characters, enforced at registration

### Brute-Force Protection

- [ ] `POST /auth/login` — max 5 attempts per IP per minute; return 429 with `Retry-After` header
- [ ] Lock account for 15 minutes after 10 failed attempts within 1 hour; log each failure to audit_logs
- [ ] Never reveal whether email exists or password is wrong — always return the same generic message

### CORS

- [ ] Configure `CORSMiddleware` in `main.py`
- [ ] `allow_origins` reads from env `ALLOWED_ORIGINS` — never `*` in production
- [ ] `allow_credentials=True` (required for HTTP-Only cookies)
- [ ] `allow_methods=["GET", "POST", "PUT", "DELETE"]`
- [ ] `allow_headers=["Content-Type"]` — no `Authorization` header needed (cookie-based)

### Security Headers

- [ ] Add `secure` library middleware to set on every response:
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` (HSTS)
  - `Content-Security-Policy: default-src 'self'`
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: no-referrer`
  - `Permissions-Policy: geolocation=(), microphone=()`
- [ ] Verify headers present on every response in `test_security.py`

### Rate Limiting

- [ ] `POST /chat` — max 30 requests per user per minute (protects LLM budget)
- [ ] `POST /admin/documents/upload` — max 10 uploads per user per hour
- [ ] `GET /admin/*` — max 100 requests per user per minute
- [ ] Return 429 with `Retry-After` header; log rate limit hits to audit_logs

### File Upload Security

- [ ] Maximum file size: 50 MB per file (configurable via env `MAX_UPLOAD_SIZE_MB`)
- [ ] Validate MIME type against `Content-Type` header AND actual file magic bytes (`python-magic`)
- [ ] Allowed extensions whitelist: `.pdf`, `.docx`, `.xlsx`, `.txt` — reject everything else with 400
- [ ] Store uploaded files outside the web root (`data/raw/` — never served directly)
- [ ] Generate a UUID-based filename on server side; never use the client-supplied filename for storage

### Request Body Limits

- [ ] **Request body limiting requires three layers** — uvicorn alone has no built-in global body cap:
  1. **Reverse proxy** (Nginx/Caddy in front of uvicorn): `client_max_body_size 60m;` (Nginx) or `request_body_size 60MB` (Caddy) — first line of defense, rejects before the app process sees the bytes
  2. **ASGI middleware** (`app/auth/middleware.py` or a dedicated `LimitBodyMiddleware`): check `Content-Length` header on every request; if > threshold → return 413 immediately without reading the body. Note: `Content-Length` can be absent or spoofed, so this is a fast-path check, not the only check
  3. **Streaming chunk validation**: for file uploads, read in chunks (`await file.read(chunk_size)`) and abort with 413 if accumulated bytes exceed `MAX_UPLOAD_SIZE_MB` — catches streams without `Content-Length`
- [ ] Chat endpoint: max query body 10 KB — reject with 413 if exceeded

### Dependency Scanning

- [ ] `pip-audit` in CI on every PR; fail build on known CVEs with CVSS ≥ 7.0
- [ ] Pin all production dependencies with exact versions in `pyproject.toml`

### Logging — Sensitive Data Rules

- [ ] Never log: passwords, JWT tokens, cookie values, raw query text in DEBUG level
- [ ] `audit_logs.query_text` stores only the first 500 characters; full content never in application logs
- [ ] Structured logging only (`structlog`); no f-string log interpolation of user data
- [ ] Log files excluded from Docker image (`.dockerignore`); logs written to stdout only in containers

### `app/security/input_guard.py`

- [ ] Maximum query length (512 tokens); reject if exceeded
- [ ] Detect and block prompt injection patterns (instruction override attempts: "ignore previous instructions", "you are now", etc.)
- [ ] Block known jailbreak fragments (maintain a list, configurable)
- [ ] Sanitize: strip HTML, control characters
- [ ] Return `GuardResult(allowed: bool, reason: str)` — never raise raw exceptions to the user

### `app/security/content_filter.py`

- [ ] Filter retrieved chunks before passing to LLM
- [ ] Remove chunks flagged as containing PII patterns (regex: SSN, credit card, passport formats) — log a warning but do not crash
- [ ] Configurable blocklist of document sections that must not be passed to LLM (e.g., annexes marked confidential)

### `app/security/output_filter.py`

- [ ] Validate LLM output before it reaches the user
- [ ] Detect if answer contains PII that was not in the retrieved chunks (LLM hallucinated PII)
- [ ] Detect if answer contradicts a retrieved chunk (basic factual grounding check)
- [ ] If output fails: return fallback message, log the raw output to audit (not to user), increment a counter in observability

### Access Control `[PILOT]`

- [ ] Document access: Qdrant filter on `uploaded_by` or `document_group` field
- [ ] Admin can add/remove users and revoke document access per user
- [ ] Integration test: `pilot_user` cannot call admin endpoints; token expiry returns 401

### Data Lifecycle & Deletion `[PILOT]`

PRD explicitly requires documented backup and deletion process:

- [ ] Document full delete: remove from `data/raw/`, `data/processed/`, `document_chunks` table, Qdrant points for all chunk IDs, `semantic_cache` entries referencing the document — single atomic operation wrapped in a transaction where possible
- [ ] `DELETE /admin/documents/{id}` must complete all of the above or roll back with an error — no partial deletes
- [ ] Backup: document `docs/deployment.md` with backup procedure — at minimum: daily `pg_dump` + Qdrant snapshot + `data/raw/` backup; retention aligned with `AUDIT_LOG_RETENTION_DAYS`
- [ ] `scripts/backup.py` — runs pg_dump, triggers Qdrant snapshot API, copies raw files to backup location
- [ ] GDPR/deletion verification: `scripts/verify_deletion.py {doc_id}` — checks that no traces remain in DB, Qdrant, filesystem, or cache

**Exit criteria:** full delete removes all data traces; backup script runs without error; pilot_user returns 403 on admin routes.

---

## Phase 2C — Observability

**Owner:** Backend Engineer
**Duration:** 1-2 days
**Requires:** Phase 1
**Parallel with:** Phase 2A, 2B

### `observability/tracer.py`

- [ ] OpenTelemetry span per pipeline stage: `input_guard`, `query_rewrite`, `retrieval`, `rerank`, `document_grade`, `generate`, `output_filter`
- [ ] Each span records: `stage_name`, `duration_ms`, `input_tokens`, `output_tokens`, `cache_hit`, `chunk_ids_used`
- [ ] Trace ID propagated through entire request → stored in `audit_logs.trace_id`
- [ ] Export: OTLP to local Jaeger (Docker Compose) for pilot; pluggable for production (Langfuse, Datadog)

### `observability/feedback.py`

- [ ] `POST /feedback` — `{session_id, message_id, rating: "positive"|"negative", comment?}`
- [ ] Store in `query_feedback` table with `trace_id` so feedback links directly to the trace
- [ ] Admin view: `GET /admin/feedback` — shows feedback alongside the query and retrieved chunks

### `observability/cost_tracker.py`

- [ ] Track token count per LLM call (prompt tokens + completion tokens)
- [ ] Calculate cost (even if Qwen local = $0, track tokens for capacity planning)
- [ ] Aggregate: cost per query, per session, per user, per day
- [ ] Write to `agent_runs.cost_usd`
- [ ] `GET /admin/stats/cost` — summary by user and date range

### Audit Log Retention & Cleanup

- [ ] `scripts/audit_cleanup.py` — deletes `audit_logs` rows older than `AUDIT_LOG_RETENTION_DAYS` (default 90); logs count of deleted rows
- [ ] Scheduled via APScheduler inside the app (daily at 02:00 UTC); no external cron dependency needed for pilot
- [ ] On each cleanup run, write a summary entry to `audit_logs` itself (`action_type="system_cleanup"`) so the cleanup is itself auditable
- [ ] `semantic_cache` rows older than 30 days (configurable via `CACHE_RETENTION_DAYS`) also cleaned up in the same job

**Exit criteria:** every chat query produces a trace with per-stage spans; feedback endpoint stores linked to trace_id; cost per query visible in admin stats; cleanup job runs on startup in test mode and deletes zero rows (empty DB).

---

## Phase 2D — Evaluation Layer

**Owner:** ML / AI Engineer
**Duration:** 2 days
**Requires:** Phase 1 + Phase 2A (offline_eval.py runs questions through the full RAG pipeline — needs retrieval, reranking, and generation)
**Parallel with:** Phase 3A, 3B (starts as soon as Phase 2A finishes — typically mid-Week 2, while 3A/3B haven't started yet; overlaps with 3A and 3B in Week 3)

> Most teams skip this entire layer and ship blind. We don't.

### `evaluation/golden_dataset.json`

- [ ] Create 20-30 Q&A pairs for each pilot workflow type (document Q&A, policy assistant)
- [ ] Schema per entry: `{id, question, expected_answer, expected_citations: [{filename, page}], difficulty: easy|medium|hard}`
- [ ] Cover: factual questions, multi-hop questions, out-of-scope questions, edge cases
- [ ] Versioned in git (each update adds entries, never removes)

### `evaluation/offline_eval.py`

- [ ] Load golden dataset → run each question through the full pipeline
- [ ] Score per question:
  - **Retrieval recall**: did the correct chunk appear in top-6? (binary, reliable)
  - **Answer correctness**: use **LLM-as-judge**, not cosine similarity — cosine similarity of embeddings misses semantic quality. Prompt: "Given the question and expected answer, rate the generated answer 1–5 for correctness and completeness. Return JSON `{score, reasoning}`." Use same local Qwen model as judge.
  - **Citation precision**: did citations match expected source filename + page?
  - **Fallback accuracy**: did out-of-scope questions trigger fallback?
- [ ] Write results to `evaluation/eval_results/YYYY-MM-DD_HH-MM.json`
- [ ] `eval_results/` is in `.gitignore` — real pilot eval outputs may contain customer-derived data; only commit `evaluation/golden_dataset.json` and `evaluation/eval_results/sample_sanitized.json` (anonymized example)
- [ ] Print summary: overall score, per-difficulty breakdown, regressions vs. previous run
- [ ] Exit non-zero if overall score drops below threshold (configurable, default 0.75)

### `evaluation/online_monitor.py`

- [ ] Runs as background job (every hour in production, daily in pilot)
- [ ] Samples 10% of live queries from `audit_logs`
- [ ] Scores sampled queries using the same metrics as offline eval (no ground truth — uses heuristics: fallback rate, avg retrieval score, user feedback ratio)
- [ ] Writes monitoring summary to `eval_results/monitor_YYYY-MM-DD.json`
- [ ] Triggers alert (log WARN) if fallback rate > 20% or avg retrieval score < 0.5

**Exit criteria:** `python evaluation/offline_eval.py` runs to completion and writes a scored results file; overall score ≥ 0.75 on the golden dataset.

---

## Phase 3A — LangGraph Agent Workflow

**Owner:** AI Agent Engineer
**Duration:** 3-4 days
**Requires:** Phase 2A (RAG Core)
**Parallel with:** Phase 3B

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

- [ ] For each retrieved chunk, grade its relevance to the query: `{chunk_id, relevant: bool, reason: str, confidence: float}`
- [ ] Prompt loaded from registry: `get_prompt("document_grader", "v1")`
- [ ] Output via Pydantic structured output (not free text)
- [ ] Self-correcting: if < 2 chunks graded as relevant → trigger `query_decomposer` before giving up

### `agents/query_decomposer.py`

- [ ] Break complex multi-part question into 2-4 simpler sub-queries
- [ ] Run each sub-query through retrieval independently
- [ ] Merge and deduplicate results
- [ ] Prompt loaded from registry: `get_prompt("query_decomposer", "v1")`
- [ ] Only invoked when `document_grader` finds < 2 relevant chunks on first retrieval pass

### `agents/adaptive_router.py`

- [ ] LLM-driven router (not hardcoded conditional edges)
- [ ] Decides next step based on current state: `{decision, reasoning, suggested_focus}`
- [ ] Decision is a closed Literal enum — LLM cannot invent new node names
- [ ] Self-correcting: if generation fails quality gate, router can send back to retrieve with a refined query

### LangGraph Graph

- [ ] **intake** → `input_guard` → **rewrite** → **retrieve** → **grade** → conditional:
  - if ≥ 2 relevant chunks → **generate**
  - if < 2 relevant → **decompose** → **retrieve** (second pass) → **generate**
- [ ] **generate** → **output_filter** → **quality_gate** → conditional:
  - if grounded → **respond**
  - if not grounded → **fallback**
- [ ] Observability: tracer span opened at intake, closed at respond/fallback
- [ ] Session: load state at intake, save at respond/fallback

### Human-in-the-Loop Queue (PRD requirement: "human review for high-risk outputs")

- [ ] Use `human_review_queue` table (defined in Phase 1 Alembic migrations)
- [ ] `output_filter.py` sets `requires_human_review = True` when: output confidence is low, fallback was triggered multiple times in session, or query matches a high-risk pattern (medical symptoms, legal decisions, financial amounts)
- [ ] When `requires_human_review = True`: insert into `human_review_queue`, return to user: "Your question has been flagged for expert review. You will be notified when a response is ready."
- [ ] Admin endpoints for review queue are in **Phase 3B** (Admin API) — 3A and 3B run in parallel; 3A owns the queue insertion logic, 3B owns the admin HTTP endpoints
- [ ] This fulfils PRD Section 9 minimum requirement: "human review for high-risk outputs"

### Conversation Memory — Long Session Policy

- [ ] Default: last 10 turns passed as context (already defined)
- [ ] When turn count > 10: summarize older turns using LLM before dropping them — store summary in `sessions.state_json` as `context_summary`; prepend summary to system prompt
- [ ] Summarization prompt loaded from registry: `get_prompt("conversation_summarizer", "v1")`
- [ ] If summarization fails: fall back to dropping oldest turns without summary (log warning)
- [ ] Maximum context window: 4000 tokens total (query + summary + recent turns + retrieved chunks); chunking strategy must account for this budget

### Integration Tests

- [ ] Single-turn Q&A → grounded answer with citations
- [ ] Out-of-scope question → fallback (no hallucination)
- [ ] Complex multi-part question → decomposer triggers → merged answer
- [ ] First retrieval returns poor chunks → self-correction triggers → second pass improves result
- [ ] LLM error → caught, logged, user-friendly error returned
- [ ] High-risk query → enters human review queue, user gets "under review" message
- [ ] Session with 15 turns → summarization triggers, older turns replaced by summary

**Exit criteria:** LangGraph graph compiles; all 7 integration tests pass; traces visible in Jaeger; human review queue has at least one entry after test run.

---

## Phase 3B — Admin API

**Owner:** Backend Engineer
**Duration:** 2-3 days
**Requires:** Phase 2A (document upload triggers RAG ingestion; delete clears Qdrant + semantic cache), Phase 2B (Auth), Phase 2C (Observability)
**Parallel with:** Phase 3A

- [ ] `POST /admin/documents/upload` — multipart upload, stores to `data/raw/`, triggers background ingestion
- [ ] `GET /admin/documents` — list with status (pending / ingesting / ready / failed / needs_review)
- [ ] `DELETE /admin/documents/{id}` — delete from filesystem, Qdrant, database, invalidate semantic cache
- [ ] `POST /admin/documents/{id}/reindex` — re-run ingestion
- [ ] `GET /admin/documents/{id}/status` — poll ingestion progress
- [ ] `POST /admin/users` — create user with role
- [ ] `DELETE /admin/users/{id}` — deactivate (soft delete)
- [ ] `GET /admin/users` — list with role and status
- [ ] `GET /admin/audit-logs` — paginated JSON, supports `?start=&end=&user_id=`
- [ ] `GET /admin/audit-logs/export.csv` — full export
- [ ] `GET /admin/feedback` — feedback list with linked trace_id and query
- [ ] `GET /admin/stats` — pilot summary: total queries, avg latency, fallback rate, cache hit rate, cost
- [ ] `GET /admin/stats/cost` — cost breakdown by user and date range
- [ ] `GET /admin/review-queue` — admin sees pending human review items with query, draft answer, risk reason
- [ ] `POST /admin/review-queue/{id}/approve` — sends approved answer back to user session
- [ ] `POST /admin/review-queue/{id}/reject` — sends rejection with explanation
- [ ] Background ingestion: write `ingestion_jobs` record (status=pending) before starting; run via `asyncio` task; update status to `ingesting` → `ready` / `failed` on completion
- [ ] **Restart recovery**: on app startup, query `ingestion_jobs` for any records stuck in `ingesting` status (started > 10 minutes ago) and re-queue them — prevents documents being permanently stuck after container restart
- [ ] **Document versioning / ingestion locking**: when a document is reindexed, new chunks are written with `chunk_version = documents.version + 1`; Qdrant payload also carries `chunk_version` so retrieval can filter without joining Postgres; new version only becomes `active` after ingestion completes successfully (`documents.active_version` swapped atomically) — users never see a partial reindex
- [ ] **Document update flow**: `POST /admin/documents/{id}/upload-new-version` — uploads replacement file, triggers ingestion of new version, atomically swaps `active_version` on success; old Qdrant points are **not deleted immediately** — they are retained for 24h with `chunk_version < active_version` so a rollback is possible; a cleanup job (`scripts/cleanup_stale_chunks.py`) deletes them after 24h
- [ ] Add `version` (integer, default 1) and `active_version` (integer, default 1) columns to `documents` table via Alembic migration — this migration runs in Phase 3B; Phase 2A retrieval is version-agnostic by default (no version filter = reads all chunks, correct when only one version exists); after this migration, retrieval must filter `chunk_version = documents.active_version`

**Exit criteria:** upload → ingest → ready completes within 60s for 100-page PDF; all admin endpoints documented in `docs/api-reference.md`.

---

## Phase 4 — Web UI

**Owner:** Frontend Engineer
**Duration:** 3-4 days
**Requires:** Phase 3A + Phase 3B

### Chat Interface (Pilot User)

- [ ] Login page → credentials posted to `POST /auth/login` → JWT set as HTTP-Only cookie by server (frontend never touches the token)
- [ ] Chat window: message input, history, loading spinner, error display
- [ ] Citation panel: filename, page, excerpt per source; click → full chunk modal
- [ ] Feedback buttons (thumbs up / down) per answer → calls `POST /feedback`
- [ ] Session persistence: reload → resume session

### Admin Panel

- [ ] Document upload (drag-and-drop, progress bar, status polling)
- [ ] Document list table (filename, type, status, actions: delete / reindex)
- [ ] User management (list, add, deactivate)
- [ ] Audit log viewer (paginated table: timestamp, user, query preview, latency, cache hit)
- [ ] Feedback viewer (query, rating, comment, trace link)
- [ ] Stats dashboard (total queries, fallback rate, avg latency, cache hit %, cost today)
- [ ] Export buttons (audit CSV, stats JSON)

### Technical

- [ ] React + Vite (no SSR needed for pilot)
- [ ] React Query for API calls
- [ ] Tailwind CSS
- [ ] `VITE_API_URL` env var
- [ ] Separate `frontend/Dockerfile`

**Exit criteria:** non-technical pilot user logs in, asks a question, sees cited answer, rates it with thumbs up/down — all without touching a terminal.

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
| Phase 2D (Evaluation) | Phase 1 + **Phase 2A** | 3A, 3B (starts mid-Week 2 after 2A done) |
| Phase 3A (LangGraph Agents) | Phase 2A | 3B, 2D |
| Phase 3B (Admin API) | **Phase 2A** + 2B + 2C | 3A, 2D |
| Phase 4 (UI) | Phase 3A + 3B | — |
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
| Phase 4 | Frontend Engineer |
| Phase 5 | Founder / Full-stack |

## Total Estimated Duration (with parallelization)

```
Week 1:     Phase 0 + Phase 1 (parallel)
Week 2 M-W: Phase 2A + 2B + 2C start simultaneously (3 engineers)
Week 2 Th-F: Phase 2D starts as soon as 2A finishes (ML engineer pivots)
Week 3:     Phase 3A + 3B (parallel, 2 engineers); Phase 2D may still be running
Week 4:     Phase 4 → Phase 5
```

Minimum: ~4 weeks with 3-4 engineers in parallel.
Solo: ~10-12 weeks sequentially.
