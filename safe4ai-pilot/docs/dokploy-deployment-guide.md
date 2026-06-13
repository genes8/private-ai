# Dokploy Deployment Guide

Date: 2026-06-12
Audience: operators evaluating Dokploy for Safe4AI hosting

Dokploy is not a default supported deployment target. Safe4AI's supported
delivery paths are Docker Compose, air-gapped bundles, and Enterprise
Kubernetes/Helm when required. This guide records the supported boundary if a
customer chooses Dokploy as the VPS control plane.

## Supported boundary

Dokploy may orchestrate the same Docker Compose package documented in
`docs/deployment.md`. It must not change the runtime contract:

- Safe4AI images remain versioned release images.
- PostgreSQL, Qdrant, file volumes, audit archive storage, and backups remain
  customer-owned.
- TLS termination, DNS, firewalling, and backup retention are operator
  responsibilities.
- No source code is delivered as part of the runtime package.

## Recommended layout

Run one Dokploy project with these services:

- `postgres` from `pgvector/pgvector:0.8.0-pg16`.
- `qdrant` from `qdrant/qdrant:v1.13.3`.
- `app` from the versioned Safe4AI backend image.
- `frontend` from the versioned Safe4AI frontend image.
- Optional `ollama` overlay only when local model mode is required.

Persist these volumes outside the application containers:

- PostgreSQL data.
- Qdrant data.
- `data/raw`.
- `data/processed`.
- `data/audit-archive`.
- Ollama model data, if local mode is enabled.

## Environment

Set at minimum:

```text
SECRET_KEY=<strong random value>
POSTGRES_URL=postgresql+psycopg2://safe4ai:<password>@postgres:5432/safe4ai
QDRANT_URL=http://qdrant:6333
ALLOWED_ORIGINS=https://<customer-hostname>
ENFORCE_HTTPS=true
AUDIT_ARCHIVE_DIR=data/audit-archive
```

Use `docker-compose.ollama.yml` only when the customer accepts the local model
resource profile.

## Verification

After Dokploy starts the stack, run the same checks as the Compose guide:

```bash
curl -fsS https://<customer-hostname>/health
curl -fsS http://<qdrant-host>:6333/readyz
docker compose exec postgres psql -U safe4ai -d safe4ai \
  -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

For production use, confirm backup restore on a separate Dokploy project before
the first customer go-live.

## Not supported without extra work

- Dokploy-specific autoscaling or blue/green release automation.
- App-provided WORM storage.
- Customer registry image signing verification inside Dokploy.
- Multi-node Qdrant/PostgreSQL operations.

If any of those are required, use the Enterprise Kubernetes/Helm path or write a
funded deployment addendum.
