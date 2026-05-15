# Safe4AI Pilot

Private AI readiness pilot with a FastAPI backend, React admin/chat frontend, PostgreSQL + pgvector, Qdrant, Ollama, and Jaeger.

## Quick start with Docker Compose

This is the recommended way to run the full project locally because it starts all required services together.

### 1. Prepare environment

```bash
cd safe4ai-pilot
cp .env.example .env
```

After copying, set `SECRET_KEY` in `.env` to a strong random 64-character hex string.

### 2. Start everything

```bash
docker compose up --build
```

The first run can take a while because `ollama-init` pulls these models:

- `qwen3.5:9b`
- `nomic-embed-text`
- `qwen2.5vl:7b`

### 3. Open the app

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/health
- Qdrant: http://localhost:6333
- Ollama: http://localhost:11434
- Jaeger UI: http://localhost:16686

### 4. Seed an admin user, if needed

In another terminal, install backend dependencies locally and run the seed script against the Docker Postgres service:

```bash
cd safe4ai-pilot
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m scripts.seed
```

Default seeded admin login:

- Email: `admin@safe4ai.local`
- Password: printed by `scripts/seed.py` at runtime, or set explicitly with `SEED_ADMIN_PASSWORD`

## Useful Docker commands

```bash
# Start in background
docker compose up --build -d

# See logs
docker compose logs -f app
docker compose logs -f frontend

# Stop services
docker compose down

# Stop and remove local volumes/data for Postgres, Qdrant, and Ollama
docker compose down -v
```

## Local development mode

Use this when you want hot reload for backend or frontend while still using Docker for dependencies.

### 1. Start dependencies

```bash
cd safe4ai-pilot
cp .env.example .env
docker compose up postgres qdrant ollama ollama-init jaeger
```

### 2. Run backend locally

```bash
cd safe4ai-pilot
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Run frontend locally

```bash
cd safe4ai-pilot/frontend
npm install
npm run dev
```

Vite runs on http://localhost:3000 and proxies `/auth`, `/chat`, `/me`, `/admin`, and `/feedback` to `http://localhost:8000`.

## Verification

After the stack is running, check core services:

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:6333/readyz
curl -fsS http://localhost:11434/api/tags
```

Frontend build check:

```bash
cd safe4ai-pilot/frontend
npm run build
```

Backend tests require Python dependencies from `.[dev]`:

```bash
cd safe4ai-pilot
pytest tests/
```

More deployment and smoke-test details are in [`docs/deployment.md`](docs/deployment.md).

## Production TODO

- **GPU-enabled PyTorch for production:** The `app/Dockerfile` currently installs CPU-only PyTorch (`--index-url https://download.pytorch.org/whl/cpu`) to avoid pulling ~1 GB of NVIDIA/CUDA packages during local development. For production deployments on GPU hardware, replace or conditionalize this to install the full CUDA-enabled PyTorch build.
