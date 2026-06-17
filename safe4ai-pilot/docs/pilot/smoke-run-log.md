# Smoke Run Log

Record of real-service smoke runs of the Safe4AI pilot platform. Each run exercises the live stack (Postgres, Qdrant, app) plus a model provider, end to end, in five stages. A stage failure records the **boundary reached** rather than failing the whole run.

---

## Run: 2026-06-03

- **Operator:** automated (Claude Code, Phase A smoke)
- **Environment:** macOS host; Docker Compose stack (`docker-compose.yml` + `docker-compose.override.yml`); model provider = **host Ollama** reached from the app container via `host.docker.internal` (override file `OLLAMA_URL=http://host.docker.internal:11434`).
- **Images/build:** local `docker compose up --build` (backend `safe4ai-pilot-app:latest`).
- **Result:** **PASS (5/5 stages)** for the paths exercised (stack, model readiness, PDF/DOCX/TXT ingestion, grounded cited answer, persistence), with two documented environmental fixes and one product-tuning observation. **Scanned-PDF OCR was not part of this run and remains unverified by smoke** (see "Not exercised" below).

### Stage results

| Stage | Check | Result |
|---|---|---|
| 1. Stack readiness | Postgres + Qdrant + app healthy; `/health` green | **PASS** — `{"status":"ok","checks":{"postgres":"ok","qdrant":"ok","provider":"ok"}}` |
| 2. Model readiness | Chat + embedding + vision models available | **PASS** — `qwen3.5:9b` (chat **and** vision/OCR — single multimodal model) and `nomic-embed-text` (embeddings) all present on the host |
| 3. Ingestion | Upload PDF, DOCX, scanned PDF; jobs complete | **PASS for PDF/DOCX/TXT** — all reached `indexed` (txt 1 chunk, pdf 17 chunks, docx 35 chunks). **Scanned-PDF OCR not exercised in this run** — no scanned PDF was uploaded; the vision model (`qwen3.5:9b`) was present, so OCR was available but is **unverified by this smoke** |
| 4. Query / citation | Grounded answer cites filename + page + excerpt | **PASS** — "What is the Business AI Alliance…" returned a grounded answer with **6 citations**, each carrying filename, page number, excerpt, and score (e.g. `Business-AI-Alliance-…-Welcome-Pack-November-2025.pdf` p2, score 6.05) |
| 5. Persistence | `chat_query` audit row + `agent_runs` row written | **PASS** — audit row (trace `615d63d4…`, model `qwen3.5:9b`, latency 11579 ms) and matching `agent_runs` row (status `completed`, session `009de34d…`) both persisted by `app/services/chat_finalizer.py` |

### Findings

1. **Docker VM disk exhaustion (fixed).** Initial `docker compose up --build` failed extracting an image layer: *no space left on device*. The host disk was fine (≈480 GB free); the Docker Desktop VM disk was full. Reclaimed ≈24 GB of build cache (`docker builder prune -af`); rebuild then succeeded. Data volumes were left intact.

2. **Stale DB provider URL masked by env split (fixed for the run).** Chat **generation** failed with `All connection attempts failed`, while retrieval/embeddings and `/health` were green. Cause: the persisted runtime config (`app_config.provider_base_url`) was `http://localhost:11434`, which is unreachable **from inside the container** (localhost = the container). Embeddings and the health check used the env `OLLAMA_URL` (pointed at `host.docker.internal`), so only the generation path surfaced the break. Setting `provider_base_url` to `http://host.docker.internal:11434` produced a correct grounded answer. **Reverted to `http://localhost:11434` after the run** to leave the dev volume as found.
   - *Takeaway:* provider configuration is split between the env default (`settings.ollama_url`) and the DB runtime config (`provider_base_url`); they can diverge, and only chat generation reveals it. Worth a health-check that pings the **chat** provider, not just embeddings.
   - *Resolved permanently (post-run):* the local setup now runs Postgres in Docker on host port 5433, wires the app to host Ollama via `host.docker.internal` in `docker-compose.override.yml`, and the DB `provider_base_url` is set to `http://host.docker.internal:11434` — so chat generation works without per-run overrides.

3. **Routing needs ≥2 relevant chunks for the direct generate path (product tuning).** A single-fact document (1 chunk) is graded relevant but `route_after_grade` (`app/agents/adaptive_router.py`) routes to `decompose` unless ≥2 chunks are relevant; the single-fact query then landed in the grounding fallback. Multi-chunk corpora answered and cited correctly. Not a defect — a tuning characteristic to note for pilots with sparse documents.

### Not exercised / boundaries

- **Scanned-PDF OCR** — not exercised because no scanned/image PDF was uploaded in this run. The vision/OCR model is `qwen3.5:9b` (the single multimodal model, present during the run), and the OCR ingestion path is implemented — but OCR output quality on a real scanned document is **unverified by this smoke**. A follow-up run should upload a scanned PDF and confirm extracted text + citations.
- **Containerized Ollama path** (`docker-compose.ollama.yml`) — not used; the run reused the already-running host Ollama to avoid re-pulling ~13 GB of models on the space-constrained Docker VM.

---

## Follow-up: automated document-flow smoke (added 2026-06-13)

Three real-service smoke tests now cover the previously unverified flows. They
live in `tests/test_real_services_smoke.py` (marked `@pytest.mark.smoke`) and use
a generated image-only PDF fixture (`tests/fixtures/scanned_pdf.py`) plus a small
authenticated client (`tests/helpers/smoke_client.py`).

- `test_real_scanned_pdf_ocr_ingest` — uploads an image-only PDF (no text layer,
  forcing the vision/OCR path), waits for `indexed`, and asserts the inspector
  reports OCR-produced chunks whose previews contain the fixture's text. **This
  closes the long-standing "scanned-PDF OCR unverified" gap.**
- `test_real_upload_new_version_no_retrieval_gap` — uploads a doc, then a new
  version, and polls throughout the staged ingest asserting the document never
  leaves a servable state and a previous version stays active until the atomic
  flip.
- `test_real_delete_then_verify_deletion_clean` — deletes a doc and asserts
  `GET /admin/documents/{id}/verify-deletion` returns `clean: true` with every
  remnant count at zero.

### How to run

```bash
cd safe4ai-pilot
docker compose up -d                       # or the host-Ollama override setup
export RUN_REAL_SMOKE=1
export SMOKE_ADMIN_PASSWORD=...             # or SEED_ADMIN_PASSWORD used at seed
.venv/bin/pytest tests/test_real_services_smoke.py -v
```

Without `RUN_REAL_SMOKE=1` the suite skips. **Status: written and passing
collection/skip locally; pending one execution against a live stack** (requires
Docker + the `qwen3.5:9b` vision model pulled). Record the live PASS/FAIL here
after that run.
