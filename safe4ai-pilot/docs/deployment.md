# Safe4AI Pilot Deployment Guide

This pilot is designed to run fully inside approved customer infrastructure. The
default local deployment uses Docker Compose with PostgreSQL + pgvector, Qdrant,
Ollama, Jaeger, and the FastAPI app.

## Runtime profile

| Component | Recommended | CPU-only fallback |
|---|---:|---:|
| Qwen 3.5 9B Q4 via Ollama | ~6 GB VRAM | ~12 GB RAM |
| Qwen2.5-VL 7B for scanned-document OCR | ~5-6 GB VRAM | ~10 GB RAM |
| `nomic-embed-text` | ~500 MB RAM/VRAM | ~500 MB RAM |
| Cross-encoder reranker | ~200 MB RAM | ~200 MB RAM |
| PostgreSQL + Qdrant + app | ~4 GB RAM | ~4 GB RAM |

Minimum practical pilot machine:

- **GPU path:** NVIDIA GPU with 12 GB VRAM is acceptable if the chat and vision
  models are swapped; 16 GB+ VRAM is preferred for smoother operation.
- **CPU-only path:** 28 GB RAM minimum. Expect local generation to be roughly
  5-10x slower; Qwen 3.5 9B Q4 should be treated as an interactive-demo fallback,
not a high-throughput production setting.

Settings responses include a small per-process live metadata cache for values
such as model lists and daily cost. In multi-worker deployments, each worker can
serve its own cached live metadata for up to 60 seconds; persisted settings are
still read from PostgreSQL on each request. Use a single app worker for strict
operator-console consistency, or replace the cache with a shared store in larger
deployments.

`OLLAMA_KEEP_ALIVE=24h` is set in `docker-compose.ollama.yml` to keep the chat model warm
between requests when the local Ollama overlay is enabled. The app also pre-warms Ollama on startup by calling
`/api/generate` with an empty prompt.

## Compose startup

1. Copy the environment file:

   ```bash
   cp .env.example .env
   ```

   Then set `SECRET_KEY` in `.env` to a strong random 64-character hex string.

2. Start the stack. For the local Ollama profile, include the Ollama overlay:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.ollama.yml up --build
   ```

3. Wait for `ollama-init` to finish pulling:

   - `qwen3.5:9b`
   - `nomic-embed-text`
   - `qwen2.5vl:7b`

4. Run the healthcheck script from another terminal:

   ```bash
   python scripts/healthcheck.py
   ```

## Required smoke checks

These checks are the Phase 1 real-service exit criteria. They require the Compose
stack to be running.

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:6333/readyz
curl -fsS http://localhost:11434/api/tags
docker compose exec postgres psql -U safe4ai -d safe4ai \
  -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

Expected result:

- FastAPI `/health` returns JSON with `status` equal to `ok` or a dependency-level
  reason for degradation.
- Qdrant `/readyz` returns 200.
- Ollama `/api/tags` returns the pulled local models.
- PostgreSQL returns one row for the `vector` extension.

## Running integration tests with Docker

Unit tests do not require Docker. Testcontainer-backed integration tests are
marked with `integration` and skipped automatically if Docker is unavailable.

```bash
pytest tests/ -m integration
```

Real-service smoke tests require `docker compose up --build` to be running and
are opt-in so normal CI does not hang on local model downloads:

```bash
RUN_REAL_SMOKE=1 pytest tests/ -m smoke
```

These tests validate the live FastAPI health endpoint, Qdrant readiness, Ollama
model tags, and PostgreSQL pgvector extension.

Run the full CI-style local suite with:

```bash
ruff check .
ruff format --check .
mypy app/
pytest tests/ --cov=app --cov-report=xml --cov-fail-under=80
detect-secrets scan --baseline .secrets.baseline
```

`pip-audit` is intentionally part of CI. If it fails, update vulnerable pins or
record a time-limited vulnerability exception before accepting the risk.

Current exception: `GHSA-rrmf-rvhw-rf47` is ignored in the release workflow
because the advisory currently has no fixed PyTorch release in the audit feed.
Remove the exception as soon as `pip-audit` reports a fixed version.

## Air-gapped deployments

Use `docs/air-gap-runbook.md` for mirrored image/model export, offline import,
no-outbound checks, and the static verifier:

```bash
python scripts/verify_airgap_package.py
```

## Backup and deletion process

For pilot deployments, back up all customer data daily:

1. PostgreSQL: `pg_dump` the `safe4ai` database.
2. Qdrant: create a snapshot through the Qdrant snapshot API.
3. Filesystem: copy `data/raw/` and `data/processed/` to the approved backup
   destination.

Retention should match `AUDIT_LOG_RETENTION_DAYS` unless the customer contract
requires shorter retention.

Deletion verification must confirm that a removed document has no remaining data
in PostgreSQL, Qdrant, `data/raw/`, `data/processed/`, or `semantic_cache`.
