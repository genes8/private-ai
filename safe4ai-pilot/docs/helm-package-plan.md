# Kubernetes and Helm Package Plan

Date: 2026-06-12
Audience: Safe4AI engineering and Enterprise deployment reviewers

This plan defines the Helm package Safe4AI will ship when an Enterprise
customer requires Kubernetes. Docker Compose remains the supported default for
Evaluation and small pilots until this chart is built and tested in a customer
cluster.

## Delivery boundary

The Helm package deploys only Safe4AI-owned runtime services:

- FastAPI backend image.
- React/nginx frontend image.
- Runtime environment configuration, secrets references, ingress, health
  probes, and resource controls.

The Helm package does not bundle customer-owned stateful services by default.
PostgreSQL, Qdrant, object/file storage, backups, immutable retention, and the
local model runtime are supplied by the customer platform or by explicitly
enabled chart values.

## Chart layout

```text
charts/safe4ai/
  Chart.yaml
  values.yaml
  templates/
    backend-deployment.yaml
    backend-service.yaml
    frontend-deployment.yaml
    frontend-service.yaml
    ingress.yaml
    configmap.yaml
    secret-env.yaml
    serviceaccount.yaml
    networkpolicy.yaml
    NOTES.txt
```

## Required values

```yaml
image:
  backend:
    repository: ghcr.io/<org>/<repo>/safe4ai-backend
    tag: "1.0.0"
  frontend:
    repository: ghcr.io/<org>/<repo>/safe4ai-frontend
    tag: "1.0.0"

externalPostgres:
  urlSecretName: safe4ai-postgres-url
  urlSecretKey: POSTGRES_URL

externalQdrant:
  url: http://qdrant.safe4ai.svc.cluster.local:6333

runtime:
  allowedOrigins: https://safe4ai.example.com
  enforceHttps: true
  auditLogRetentionDays: 365
  cacheRetentionDays: 30
  maxUploadSizeMb: 50

secrets:
  secretKeySecretName: safe4ai-secret-key
  secretKeySecretKey: SECRET_KEY
  providerApiKeySecretName: ""
  providerApiKeySecretKey: PROVIDER_API_KEY

ingress:
  enabled: true
  className: nginx
  host: safe4ai.example.com
  tlsSecretName: safe4ai-tls

storage:
  rawFiles:
    existingClaim: safe4ai-raw-files
  processedFiles:
    existingClaim: safe4ai-processed-files
  auditArchive:
    existingClaim: safe4ai-audit-archive

resources:
  backend:
    requests:
      cpu: "1"
      memory: 2Gi
    limits:
      cpu: "4"
      memory: 8Gi
  frontend:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: "1"
      memory: 512Mi
```

## Workloads

Backend deployment:

- Runs the versioned backend image.
- Loads `POSTGRES_URL` from a secret.
- Sets `QDRANT_URL`, retention settings, upload size, and provider defaults
  from chart values.
- Mounts persistent volumes for `data/raw`, `data/processed`, and
  `data/audit-archive`.
- Uses `/health` as readiness and liveness probe.
- Runs startup migrations through the existing backend startup path.

Frontend deployment:

- Runs the versioned nginx frontend image.
- Exposes port 80 through a ClusterIP service.
- Uses the existing nginx proxy to reach the backend service.
- Has no persistent state.

## Stateful dependencies

PostgreSQL:

- Default: external managed PostgreSQL with pgvector enabled.
- Required extension: `vector`.
- Backup, restore, encryption, and WORM/retention are customer platform
  controls.

Qdrant:

- Default: external Qdrant service or separately managed Qdrant chart.
- Backups and snapshots are customer platform controls.

Model runtime:

- Local Ollama can be supplied as a separate deployment if the customer wants
  local mode.
- vLLM is configured through the OpenAI-compatible provider preset in
  `docs/vllm-openai-compatible-preset.md`.

## Network and security controls

- Backend service is private inside the namespace.
- Frontend is the only ingress target.
- NetworkPolicy allows frontend to backend, backend to PostgreSQL, Qdrant, and
  configured model endpoints.
- Secrets are referenced by name, not rendered into chart values.
- Image tags must be immutable release tags and verified against the release
  evidence package before upgrade.

## Acceptance checks

The Helm package is complete only when these checks pass in a disposable
cluster:

```bash
helm lint charts/safe4ai
helm template safe4ai charts/safe4ai -f values.example.yaml >/tmp/safe4ai.yaml
kubectl apply --dry-run=server -f /tmp/safe4ai.yaml
helm upgrade --install safe4ai charts/safe4ai -f values.example.yaml
kubectl rollout status deploy/safe4ai-backend
kubectl rollout status deploy/safe4ai-frontend
curl -fsS https://safe4ai.example.com/health
```

The chart must not be described as supported until these checks are run against
the exact chart and image tags delivered to the customer.
