# Safe4AI Release Process and Deployment Packaging

Date: 2026-06-10
Status: canonical Phase E decisions (roadmap: `docs/superpowers/plans/2026-06-03-unified-readiness-pilot-roadmap.md`)

This document records the closed-runtime packaging decisions and the release
pipeline. Operational install steps live in `docs/deployment.md` and
`docs/air-gap-runbook.md`; this document is about *what we ship, how it is
built, and what the customer is entitled to*.

## Delivery targets (decision)

| Tier | Delivery | Status |
|---|---|---|
| Evaluation / small pilot | Docker Compose package (`docker-compose.yml` + versioned images) | **Default, supported now** |
| Locked-down environments | Air-gapped image/model bundle (`docs/air-gap-runbook.md`) | Supported now |
| Enterprise | Kubernetes/Helm chart | **Not built — roadmap item; do not claim in copy** |

The customer receives versioned backend/frontend images, migrations, compose
manifests, an environment variable reference, and runbooks — not the source
tree.

## Closed-runtime boundary (decision)

Safe4AI-owned (ships only as images; source stays in Safe4AI repositories):
agent orchestration, prompt registry, retrieval pipeline, chunking, reranking,
guardrails/output filters, evaluation and monitoring logic, deployment
automation, admin/UI workflows.

Customer-owned (lives and stays in the customer environment): uploaded
documents and raw files, PostgreSQL, Qdrant, users/roles, audit logs, feedback,
local model runtime (Ollama), backups and retention/WORM storage.

Consequences:

- The app never claims to provide immutable/WORM storage; that is the
  customer's storage layer (Enterprise guide is a roadmap item).
- "Data never leaves your network" applies to **local mode only**; hybrid and
  cloud provider modes send prompts to the configured provider.

## Release pipeline

`.github/workflows/release.yml`, triggered by `v*.*.*` tags:

1. **Gates** — backend test suite, `pip-audit`, frontend production build,
   and Trivy CRITICAL/HIGH image vulnerability scans.
2. **Evidence** — dependency/license reports (backend `pip-licenses`,
   frontend `license-checker`), SBOMs (SPDX via syft) and vulnerability scans
   (trivy, CRITICAL/HIGH) for both images. All attached to the GitHub release;
   these artifacts feed the enterprise security pack.
3. **Images** — backend and frontend images built with
   `org.opencontainers.image.version/revision/source` labels and pushed to
   GHCR under an **immutable version tag** (no `latest`).

Images are signed after push with cosign keyless signing through GitHub Actions
OIDC. Customer verification steps are documented in
`docs/security-pack/image-signing-verification.md`.

## Update flows

### Private registry flow (connected customers)

1. Customer pulls the approved version: `docker pull ghcr.io/<org>/safe4ai-backend:<version>` (and frontend).
2. Update the image tags in the compose file (or `.env`), then `docker compose up -d`.
3. Migrations run automatically at backend startup (`app/startup_migrations.py`);
   no separate migration command is required for compose deployments.
4. **Rollback**: set the previous image tag and `docker compose up -d` again.
   Startup migrations are additive (column/table adds, backfills), so the
   previous app version runs against the newer schema. A release that ever
   needs a destructive migration must say so in its release notes and provide
   an explicit rollback note.

### Offline / air-gapped flow

Documented in `docs/air-gap-runbook.md`: export images with `docker save`,
export required Ollama models, transfer the bundle, `docker load`, run the
static verifier, start the stack (startup migrations apply automatically).
Release evidence files (SBOM, scan report, license report) should accompany
the bundle for the customer's security review.

## Licensing and entitlement (decision)

- Updates, support, and security patches are sold as a **contract/support
  entitlement** — enforced commercially (registry access), not by a runtime
  license check.
- **No runtime license server.** Customer data access must never depend on a
  remote license check, and an air-gapped deployment must keep working if the
  contract lapses; the customer simply stops receiving updates.
- Revisit a runtime check only if commercial reality forces it, and even then
  never gate data-plane access.

## Source escrow (decision)

Enterprise-only, contract-triggered (e.g. vendor insolvency or end-of-support),
via a third-party escrow service. Routine delivery never includes source.

## Observability and deployment tooling (decisions)

- **Current support**: OpenTelemetry/OTLP export (Jaeger locally) + internal
  audit/feedback/cost tables + admin stats endpoints. This is what copy may
  claim.
- **Langfuse**: not integrated; out of current support. Write an integration
  plan only when a customer requires it.
- **Prometheus/Grafana**: not part of the default product; the add-on plan is
  documented in `docs/prometheus-grafana-plan.md`.
- **Dokploy**: a deployment recommendation, not a default supported path; the
  operator guide is documented in `docs/dokploy-deployment-guide.md`.
- **vLLM**: supported only through the OpenAI-compatible provider path; the
  deployment preset is documented in `docs/vllm-openai-compatible-preset.md`.

## Enterprise security pack (inventory)

What a regulated customer's security review receives, and where it comes from:

| Artifact | Source | Status |
|---|---|---|
| SBOM (both images, SPDX) | release workflow | Automated per release |
| Vulnerability scan report | release workflow (trivy SARIF) | Automated per release |
| Dependency/license report | release workflow | Automated per release |
| Architecture diagram | `docs/architecture.md` | Exists; export per release |
| Data-flow diagram | `docs/security-pack/data-flow-diagram.md` | Written 2026-06-12 |
| Threat model | `docs/security-pack/threat-model.md` | Written 2026-06-12 |
| Security headers / auth model | `docs/architecture.md` + `.qoder` security docs | Consolidate |
| Audit-log field reference | `docs/security-pack/audit-log-reference.md` | Written 2026-06-10 |
| Agent audit trail description | `docs/security-pack/audit-log-reference.md` | Written 2026-06-10 |
| Backup/restore + deletion verification | `docs/security-pack/backup-restore-deletion-verification.md` | Written 2026-06-12 |
| Air-gap installation runbook | `docs/air-gap-runbook.md` | Exists |
| Controls mapping | `docs/security-pack/controls-mapping.md` | Written 2026-06-12 |
| WORM storage guide | `docs/security-pack/worm-storage-guide.md` | Written 2026-06-12 |
| Image signing verification | `docs/security-pack/image-signing-verification.md` | Written 2026-06-12 |
| Pen-test/security review process | customer-specific addendum | Define with first Enterprise customer |

## Customer-specific follow-ups

- Build and validate the Helm chart when a named Enterprise customer requires
  Kubernetes delivery; the package plan is in `docs/helm-package-plan.md`.
- Fill customer-specific registry, WORM, SIEM, backup, and pen-test details in
  the deployment addendum.
- Push a version tag and confirm the release workflow publishes images,
  signatures, SBOMs, vulnerability reports, license reports, and release notes.
