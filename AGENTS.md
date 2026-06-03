# Repository Guidelines

## Project Structure & Module Organization

The main application lives in `safe4ai-pilot/`. Backend FastAPI code is under `safe4ai-pilot/app/`, with route handlers in `app/api/`, business logic in `app/services/`, agent/RAG components in `app/agents/` and `app/components/`, and database models/migrations in `app/db/`. Tests are in `safe4ai-pilot/tests/`. The React/Vite frontend lives in `safe4ai-pilot/frontend/`, with pages, hooks, API clients, and components under `frontend/src/`. Operational docs are in `safe4ai-pilot/docs/`; scripts are in `safe4ai-pilot/scripts/`; design handoff files and screenshots are kept in root-level `design/`, `handoff/`, `e2e-screenshots/`, and `promo-screenshots/`.

## Build, Test, and Development Commands

Run commands from `safe4ai-pilot/` unless noted.

- `docker compose up --build`: start the full local stack: backend, frontend, Postgres, Qdrant, Ollama, and Jaeger.
- `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`: install backend development dependencies.
- `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`: run the backend with hot reload.
- `pytest tests/`: run backend tests.
- `ruff check .` and `mypy .`: run Python linting and strict type checks.
- `cd frontend && npm install && npm run dev`: run the Vite frontend on port 3000.
- `cd frontend && npm run build`: type-check and build the frontend.

## Coding Style & Naming Conventions

Python targets 3.11+, uses Ruff with 100-character lines, and enables `E`, `F`, `I`, `UP`, and `S` lint rules. Keep modules snake_case, test files named `test_*.py`, and service code separated from API route handlers. Type annotations should satisfy strict mypy where practical. Frontend files use TypeScript React; prefer PascalCase components, `use*` hook names, and colocated API helpers under `frontend/src/api/`.

## Testing Guidelines

Use pytest for backend coverage. Mark Docker/Testcontainers or real-service checks with `integration` or `smoke`. Keep new tests close to the behavior changed, and prefer focused unit or route tests before broad smoke coverage. For frontend work, run `npm run build` and include manual verification notes or screenshots when UI behavior changes.

## Commit & Pull Request Guidelines

Recent history uses conventional-style prefixes such as `feat:`, `fix+refactor:`, and `refactor(H4):`. Keep commits scoped and descriptive, for example `feat(ui): add admin settings controls`. Pull requests should describe the change, list verification commands, link related issues or plans, and include screenshots for visible UI changes.

## Security & Configuration Tips

Copy `safe4ai-pilot/.env.example` to `.env` for local development and set a strong `SECRET_KEY`. Do not commit secrets, local volumes, generated caches, or `.venv/`. Use `scripts/verify_airgap_package.py` and related scripts when preparing deployable or air-gapped packages.
