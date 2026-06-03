# Safe4AI Air-Gap Runbook

This runbook is for deployments where the runtime network has no outbound
internet access. Build and mirror artifacts on an approved connected builder,
then move only the resulting image/model/archive bundle into the air-gapped
environment.

## 1. Build And Verify On Connected Builder

Run the static package verifier before exporting anything:

```bash
python scripts/verify_airgap_package.py
```

Build the application, frontend, PostgreSQL/Qdrant/Jaeger, and Ollama overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.ollama.yml build
docker compose -f docker-compose.yml -f docker-compose.ollama.yml pull postgres qdrant jaeger ollama
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up ollama ollama-init
```

Confirm Ollama contains the required local models:

```bash
docker compose -f docker-compose.yml -f docker-compose.ollama.yml exec ollama ollama list
```

Required models:

- `qwen3.5:9b`
- `nomic-embed-text`
- `qwen2.5vl:7b`

## 2. Export Artifacts

Export Docker images:

```bash
docker save \
  safe4ai-pilot-app safe4ai-pilot-frontend \
  pgvector/pgvector:0.8.0-pg16 qdrant/qdrant:v1.13.3 \
  jaegertracing/all-in-one:latest ollama/ollama:latest \
  -o safe4ai-images.tar
```

Export the warmed Ollama model volume:

```bash
docker run --rm \
  -v safe4ai-pilot_ollama_data:/root/.ollama \
  -v "$PWD":/bundle \
  busybox tar czf /bundle/ollama-models.tgz -C /root/.ollama .
```

Package source configuration and docs:

```bash
tar czf safe4ai-runtime-files.tgz \
  docker-compose.yml docker-compose.ollama.yml .env.example \
  docs/air-gap-runbook.md scripts/verify_airgap_package.py
```

Transfer `safe4ai-images.tar`, `ollama-models.tgz`, and
`safe4ai-runtime-files.tgz` through the approved media process.

## 3. Import In Air-Gapped Runtime

Load Docker images:

```bash
docker load -i safe4ai-images.tar
tar xzf safe4ai-runtime-files.tgz
cp .env.example .env
```

Set at minimum:

```text
SECRET_KEY=<strong random value>
AUDIT_ARCHIVE_DIR=data/audit-archive
OLLAMA_URL=http://ollama:11434
```

Restore the Ollama model volume:

```bash
docker volume create safe4ai-pilot_ollama_data
docker run --rm \
  -v safe4ai-pilot_ollama_data:/root/.ollama \
  -v "$PWD":/bundle \
  busybox tar xzf /bundle/ollama-models.tgz -C /root/.ollama
```

Start the offline stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d
```

## 4. No Outbound Verification

Confirm services are healthy:

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:6333/readyz
curl -fsS http://localhost:11434/api/tags
```

Run a no outbound check from the app container. This should fail fast for an
external host while local service calls remain healthy:

```bash
docker compose exec app sh -lc 'curl -m 3 -fsS https://example.com >/dev/null && exit 1 || exit 0'
docker compose exec app sh -lc 'curl -fsS http://ollama:11434/api/tags >/dev/null'
docker compose exec app sh -lc 'python scripts/verify_airgap_package.py'
```

## 5. Audit Archive Mount

`docker-compose.yml` mounts `./data/audit-archive` into the app container.
Scheduled cleanup writes JSONL archives and HMAC-signed manifests there before
deleting expired `audit_logs` rows.

For WORM retention, mount `./data/audit-archive` to the approved immutable
storage destination or sync the generated `.jsonl` and `.manifest.json` files to
an object store with retention lock enabled.
