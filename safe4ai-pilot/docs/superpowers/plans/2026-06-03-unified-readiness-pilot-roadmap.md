# Safe4AI Unified Readiness Pilot Roadmap

Date: 2026-06-03 (updated 2026-06-10)
Status: canonical working plan

## 2026-06-10 Status Update

Regression check on `main` (2026-06-10): backend `pytest tests/ -q` — 416 passed, 4 skipped; frontend `npm run build` — clean. No app file exceeds 1k lines.

Work landed since 2026-06-03 (not yet reflected below in the original text):

- Grounded inference answer contract (`rag_answer` v2): numbered context sources `[1], [2], ...` aligned with citation chips, inference/model-knowledge labeling rules, entity-specific fact restrictions. `generate_node` now answers the user's real question instead of the HyDE rewrite.
- Output filter Rule 3: blocks answers that use inference/model-knowledge language without a "not in the documents" disclaimer.
- Backend import unblock, SSE `trace_id` definition, safe delete order; compose Postgres single configurable host port.
- In progress (uncommitted): `load_runtime_config` ignores persisted `provider_base_url` for local Ollama mode so a URL persisted in one runtime (host vs Docker) cannot break chat in the other. This addresses the root cause behind the 2026-06-03 smoke finding about chat-provider health.

New hardening follow-ups from the 2026-06-10 code review — fold into Phase C as "C0" items:

- [x] **Finish the `provider_base_url` ownership invariant.** (Done 2026-06-10.) Canonical helper `effective_provider_base_url()` in `provider_settings.py` is now the single source of truth: `provider_base_url` is an `openai_compatible`-only setting; every ollama-mode path (runtime, settings serializer `baseUrl`, `POST /settings/provider/test`) reads the env `settings.ollama_url`. The local-mode persisting write was deleted, which made the entire `ProviderPatch.pre_updates` mechanism dead — removed (`expand_provider_mode` now returns plain body overrides; `ProviderPatch` dataclass deleted). Covered by unit tests in `test_provider_settings.py`, `test_runtime_config.py`, and a flipped `test_admin.py` test asserting local mode persists no base URL.
- [x] **Make output filter Rule 3 robust to answer language.** (Done 2026-06-10, scoped as planned.) Canonical `INFERENCE_DISCLAIMER` constant lives in `app/prompts/templates.py`, is embedded in the v2 template, and a contract test (`test_inference_disclaimer_contract_between_prompt_and_filter`) pins it against the filter's marker lists so drift on either side fails CI. The English-only language limitation (non-English fail-open; mixed-language false block) is documented in `output_filter.py` as an accepted trade-off until a language-aware check exists. Docstring rules renumbered to 0, 1, 2, 3.
- [x] **Re-verify the chat-provider health gap after the runtime fix.** (Verified 2026-06-10.) `/health` local branch pings `settings.ollama_url`, which is now by construction the same URL chat uses (`effective_provider_base_url`); the `openai_compatible` branch pings `runtime.provider_base_url + "/models"` — the chat provider itself, with the pinned transport. No remaining divergence between health and chat.
- [ ] Scanned-PDF OCR remains smoke-unverified (carried over from the 2026-06-03 run).

What "full production" still needs, in priority order:

1. **Phase E (closed-runtime packaging + release pipeline)** — the single biggest blocker. There are no production images, no CI/CD release gates, no SBOM/vuln/license reporting, no versioned update path. Nothing can ship to a customer-controlled environment as a product today.
2. **Phase D (atomic document lifecycle)** — data-correctness risk for live pilots with changing corpora; reindex is not atomic from the user's point of view.
3. **Phase C (pilot operations in the app)** — operator efficiency: audit kind counts/filtering, document inspector, real stats time series, session sidebar, follow-up suggestions. None of these endpoints exist yet (verified 2026-06-10).
4. **C0 hardening items above** — small, do them first inside Phase C.

This document consolidates these older planning sources:

- `safe4ai-private-ai-readiness-pilot-prd-roadmap.md`
- `safe4ai-implementation-plan.md`
- `Roadmap-nadogradnje.md`

Those source files are now historical inputs. Continue planning and execution from this document.

## Product Decision

Safe4AI should be packaged as one product motion:

**Private AI Readiness + Pilot**

The product motion has two parts:

1. A working Safe4AI pilot platform: private RAG chat, document ingestion, admin controls, audit, observability, provider settings, RBAC, OIDC, quota/tier enforcement, and evaluation tools.
2. A repeatable readiness service package: discovery, workflow selection, data intake, security review, pilot operation, final readiness report, rollout recommendation, and production scope estimate.

This resolves the confusion across the three plans:

- The PRD roadmap defines the commercial offer.
- The implementation plan defines the application build.
- `Roadmap-nadogradnje.md` defines architecture notes and future production tooling ideas.

The app is mostly built. The missing work is product packaging, pilot operations, production hardening documentation, and a few explicit enterprise features.

## Commercial Deployment Model

Preferred commercial model: **hybrid/on-prem deployment with a closed Safe4AI runtime**.

This is the best fit for private-ai.uk because it preserves Safe4AI's product IP while still giving regulated customers control over their sensitive data plane.

### What stays as Safe4AI IP

These should remain in Safe4AI-controlled source repositories and should not be delivered to customers as open source by default:

- Agent orchestration.
- Prompt logic and prompt registry.
- Retrieval pipeline.
- Chunking strategy.
- Ranking/reranking logic.
- Guardrail and output-quality logic.
- Evaluation and monitoring logic.
- Deployment automation.
- Update/maintenance automation.
- Product-specific UI and admin workflows.

Customers receive a runnable package, not the full source tree.

### What stays in the customer's environment

The customer's environment owns the data layer and operational evidence:

- Documents and uploaded source files.
- PostgreSQL database.
- Qdrant/vector database.
- Users and roles.
- Audit logs.
- Feedback records.
- Local LLM/model runtime when local inference is required.
- Backups, retention storage, and WORM/immutable storage if required.

This separation makes the privacy claim stronger: customer data stays in the customer's controlled environment, while Safe4AI can still operate as a maintainable product business.

### Delivery shape

Default delivery should be one of these packaged forms:

- Docker Compose package for Evaluation and smaller pilots.
- Kubernetes/Helm package for larger customers.
- Air-gapped image/model bundle for locked-down environments.

The customer should not need source access for ordinary operation. They should receive:

- Versioned backend image.
- Versioned frontend image.
- Database migrations.
- Compose/Helm manifests.
- Environment variable reference.
- Admin runbook.
- Backup/restore runbook.
- Security documentation.

Updates should be delivered through Safe4AI-controlled CI/CD:

- Build signed/versioned images.
- Run tests, vulnerability scan, and SBOM generation.
- Push to a private registry or provide an offline image bundle.
- Apply migrations through a documented release process.
- Offer subscription/license terms for updates, support, maintenance, and security patches.

### Security-friendly enterprise variant

Large regulated customers will still need transparency without receiving unrestricted source by default. Enterprise packaging should include:

- Architecture diagram.
- Data-flow diagram.
- Threat model.
- SBOM for shipped images.
- Vulnerability scan report.
- Dependency/license report.
- Security headers and auth model documentation.
- Audit-log field reference.
- Agent audit trail description.
- Model/provider configuration guide.
- Penetration/security review process.
- Air-gap installation runbook.
- Backup/restore and deletion verification process.
- Source escrow option for enterprise contract, not standard delivery.

### Product boundary

Safe4AI should sell:

- Runtime license/subscription.
- Deployment support.
- Updates and security patches.
- Monitoring/evaluation support.
- Pilot/readiness service package.
- Enterprise support and source escrow if commercially required.

Safe4AI should not position the product as:

- Open-source software delivered to the customer by default.
- A consulting-only repo handoff.
- A guarantee that the app itself provides immutable storage.
- A guarantee that customer data never leaves the network in cloud/hybrid modes.

## Source-by-Source Analysis

### 1. `safe4ai-private-ai-readiness-pilot-prd-roadmap.md`

Purpose: product offer and paid pilot roadmap.

Already done in the app:

- Private RAG pilot platform exists.
- Authenticated app with `admin` and `pilot_user` roles exists.
- Document upload, ingestion, chunking, embeddings, Qdrant indexing, and citations exist.
- Chat with SSE streaming, model name in SSE `done`, session persistence, and citation events exists.
- Audit log, CSV export, user email display, provider-change audit, and chat finalization exist.
- Observability exists via OpenTelemetry/OTLP and local Jaeger.
- Evaluation tooling exists: golden dataset, offline eval, and online monitor.
- Admin pages exist for documents, users, activity/audit, feedback, overview, and settings.
- OIDC SSO exists; SAML does not.
- Provider settings exist for local, OpenAI-compatible, and cloud-style providers, with SSRF validation and pinned outbound transport.
- Air-gap runbook and static verifier exist.

Not done or only partially done:

- Repeatable discovery questionnaire.
- Workflow-selection template.
- Pilot data inventory template.
- Final readiness report template.
- Before/after workflow comparison template.
- Production-readiness scorecard.
- Security/compliance gap-list template.
- Rollout scope and cost-estimate template.
- Public controls mapping document.
- Customer-facing pilot operating playbook.

Needs reframing:

- Old pricing bands should not be treated as app tiers. Use current Evaluation / Team / Enterprise product tiers, and treat paid pilot services as a sales package around the app.
- "Data never leaves your network" should stay scoped to local mode only.
- vLLM should remain "OpenAI-compatible provider" until a deployment preset or runbook exists.

### 2. `safe4ai-implementation-plan.md`

Purpose: full technical build plan.

Already done:

- Phase 1 infrastructure is done: FastAPI, PostgreSQL/pgvector, Qdrant, Ollama/local provider path, Docker Compose, migrations, CI/test scaffolding.
- Phase 2A RAG core is done: hybrid retrieval, BM25, reranking, ingestion, parser support, OCR path, chunking, embeddings, semantic cache, citations.
- Phase 2B security/auth is done: cookie JWT, RBAC, brute-force lockout, security headers, rate limits, upload validation, guards.
- Phase 2C observability is done: tracing, feedback, cost tracker, cleanup.
- Phase 2D evaluation is done: golden dataset, offline eval, online monitor.
- Phase 3A LangGraph agent workflow is done: graph, grading, decomposition, routing, output gate, human-review insertion.
- Phase 3B admin API is mostly done: document upload/list/status/delete/reindex, users, audit logs, CSV export, review queue, stats.
- Phase 3C runtime hardening is done: node spans, trace identity, router guards, generation context, session-state validation.
- Phase 4 Web UI is done enough for pilot: chat, admin, settings, document management, feedback, audit export, error boundary, session persistence.
- Review follow-up hardening is done according to `bug-report.md`: pinned provider/OIDC outbound calls, async SSE finalization, model-name SSE, ingestion task cancel, frontend stream/error/session fixes.

Open technical follow-ups from this plan:

- Real-service smoke tests for upload/query/citation across PDF, DOCX, and scanned PDF are still a pilot-run task, not a mocked unit-test claim.
- Document replacement/versioning is not a full atomic rollback workflow. Reindex increments version and deletes old vectors first; `upload-new-version` with delayed old-vector cleanup is not implemented.
- Activity kind-count endpoint and server-backed audit kind filtering are not implemented.
- Document inspector panel and retrieval series are not implemented.
- Session history sidebar API/UI is not implemented.
- Follow-up suggestions after answers are not implemented.
- Stats time-series endpoint for real sparklines is not implemented.
- Chunk detail endpoint and hydrated citation popovers are not implemented, though SSE citations now include excerpts.
- The final pilot report phase is not done.

Needs cleanup:

- `safe4ai-implementation-plan.md` contains old status counts and some stale statements. Treat it as historical, not authoritative.
- Some implementation details in `docs/db-layer.md` are stale against current chat finalizer and audit/cost persistence.

### 3. `Roadmap-nadogradnje.md`

Purpose: architecture explanation plus production upgrade ideas.

Already done:

- React SPA, protected routes, FastAPI backend, auth/chat/admin/observability routes exist.
- PostgreSQL, Qdrant, Ollama/local provider path, LangGraph, hybrid retriever, reranker, and Jaeger/OTLP exist.
- Admin settings now support provider mode, model settings, blocked terms, OIDC/tier/security/cost settings.
- Local-first and OpenAI-compatible provider positioning exists.

Partially done:

- Dokploy is a deployment recommendation, not a current app feature.
- Langfuse is not integrated. Current observability is OpenTelemetry/OTLP with Jaeger plus internal audit/feedback/cost tables.
- Prometheus/Grafana are future production tooling, not current product scope.
- n8n/workflow-engine automation is not implemented and should not be included in the core pilot unless a customer workflow requires it.
- Tenant/client/project tagging is not implemented as a multi-tenant model. Current product copy can say one workspace/evaluation boundary, not multi-tenant workspaces.
- Reviewer/staff/client roles are not implemented; current roles are `admin` and `pilot_user`.

Needs reframing:

- Keep Dokploy/Langfuse/Prometheus/Grafana as deployment/observability roadmap, not core app completion criteria.
- Keep n8n/workflow automation as optional integration work after the pilot validates a workflow.
- Avoid adding role or tenant scope until the product explicitly needs it.

## Current Completed Scope

The following should be considered done for the pilot platform, subject to normal regression testing:

- Private RAG chat with cited answers.
- SSE streaming chat UI.
- Session persistence keyed by user.
- Document ingestion for supported file types.
- Scanned-document OCR path.
- Qdrant vector index and BM25 hybrid retrieval.
- Reranking, query rewriting, decomposition, grading, and fallback.
- Citation enforcement for grounded answers.
- Input/content/output guards and configurable blocked terms.
- Cookie-based auth, RBAC, login/logout, password change, OIDC SSO.
- Admin user management with tier seat cap enforcement.
- Evaluation/Team/Enterprise tier settings and monthly query quota enforcement.
- Admin document management: upload, status, list, delete, reindex.
- Ingestion task cancellation by document ID on delete.
- Audit rows for chat/admin/provider activity where implemented.
- Audit CSV export.
- Tamper-evident JSONL audit archive before cleanup deletion.
- Feedback capture and admin feedback view.
- Cost/token tracking and admin stats.
- OpenTelemetry spans exported over OTLP; local Jaeger supported.
- Provider settings for local and OpenAI-compatible runtime.
- SSRF validation and pinned outbound HTTP for provider and OIDC flows.
- Air-gap runbook and static verifier.
- Frontend error boundary and stream error handling.
- Marketing copy cleanup removing SAML, signed CSV, fake logos, hard vLLM, and absolute no-egress claims.

## Not Done Yet

These are real gaps and should stay visible:

- Pilot discovery and readiness-report artifacts.
- Final pilot report generation/export workflow.
- Public or customer-ready controls mapping document.
- Closed-runtime deployment package and release process.
- SBOM/vulnerability/license reporting for shipped images.
- Kubernetes/Helm production package.
- Private registry/offline image update process.
- Source escrow terms for enterprise contracts.
- Agent audit trail documentation for security review.
- Atomic document replacement flow with rollback window.
- Document inspector/retrieval-history UI.
- Audit kind counts and server-side audit kind filtering.
- Chat session list/sidebar.
- Follow-up suggestions after answer generation.
- Stats time-series endpoint and real sparkline data.
- Chunk-detail endpoint for richer citation popovers.
- Customer-specific production deployment checklist beyond current deployment docs.
- Langfuse preset/integration.
- Dokploy deployment guide.
- Prometheus/Grafana deployment option.
- SAML SSO.
- Multi-tenant workspace model.
- App-provided WORM/immutable storage guarantee.
- Signed/tamper-evident CSV.
- Explicit vLLM deployment support with docs/preset.

## Do Not Count As Product Scope Yet

Do not pull these into the next build unless there is a specific customer reason:

- SAML SSO.
- Multi-tenant workspace model.
- Reviewer/staff/client role hierarchy.
- n8n/workflow engine integration.
- Hard 1024-token output block.
- App-owned immutable storage guarantee.
- Signed CSV.
- vLLM-specific deployment claim.
- Langfuse as required default.
- Dokploy as required default.

## Unified Execution Plan

### Phase A - Close the current branch as a pilot platform

Goal: make the existing app releasable as the Safe4AI pilot platform.

Status: mostly done.

Remaining tasks:

- [x] Run the full backend suite from `safe4ai-pilot`: `.venv/bin/pytest tests/ -q`. (2026-06-03: 407 passed, 6 skipped.)
- [x] Run the frontend production build from `safe4ai-pilot/frontend`: `npm run build`. (2026-06-03: clean `tsc` + `vite build`.)
- [x] Run targeted real-service smoke with Docker/Ollama/Qdrant when local services are available:
  - upload PDF, DOCX (scanned-PDF OCR not exercised this run — vision model `qwen3.5:9b` present but no scanned PDF uploaded; OCR unverified by smoke),
  - ask a cited question,
  - confirm source filename/page/excerpt,
  - confirm audit row and agent run are written.
  - (2026-06-03: PASS 5/5 stages, documented in `docs/pilot/smoke-run-log.md`.)
- [x] Update or archive stale internal docs, especially statements in `docs/db-layer.md` that contradict current chat finalization/audit persistence. (2026-06-03: `db-layer.md` corrected and live-verified.)
- [x] Decide whether old root-level plans should be moved to an archive folder or kept with a "superseded" banner. (Kept in place with Superseded banners — verified present on all three.)

Exit criteria — **met (2026-06-03)**:

- [x] Backend tests pass.
- [x] Frontend build passes.
- [x] One real-service pilot smoke run is documented.
- [x] Stale docs are either corrected or clearly marked historical.

### Phase B - Package the readiness pilot offer

Goal: make the service/product package repeatable without custom improvisation every time.

Deliverables — **created 2026-06-03** (plus `docs/pilot/README.md` index and `docs/pilot/smoke-run-log.md`):

- [x] `docs/pilot/discovery-questionnaire.md`
- [x] `docs/pilot/workflow-selection-template.md`
- [x] `docs/pilot/data-inventory-template.md`
- [x] `docs/pilot/security-review-checklist.md` (incl. deployment/IP-boundary decision fields)
- [x] `docs/pilot/pilot-runbook.md` (incl. deployment/IP-boundary operating notes)
- [x] `docs/pilot/final-readiness-report-template.md`
- [x] `docs/pilot/production-readiness-scorecard.md`
- [x] `docs/pilot/rollout-scope-cost-template.md` (incl. deployment/IP-boundary decision fields)

Minimum report sections:

- Executive summary.
- Workflow tested.
- Data sources and document volume.
- Users and roles.
- Queries, latency, fallback rate, feedback, and cost.
- Evaluation scores.
- What the assistant answered well.
- What it missed.
- Security/compliance gaps.
- Production requirements.
- Recommendation: stop, repeat, or expand.

Exit criteria:

- A pilot can be sold, started, operated, and closed using the same templates.
- No template claims SAML, signed CSV, app-owned WORM storage, multi-tenant workspace, or vLLM support as already available.

### Phase C - Productize pilot operations in the app

Goal: remove the most obvious admin/operator gaps that would slow repeated pilots.

Tasks (C0 — hardening first, see 2026-06-10 status update for detail):

- [x] C0: finish `provider_base_url` ownership invariant — done 2026-06-10 (`effective_provider_base_url()` helper; `pre_updates` mechanism deleted).
- [x] C0: output filter Rule 3 — done 2026-06-10 (shared `INFERENCE_DISCLAIMER` constant + contract test, language-limitation note, docstring renumber).
- [x] C0: chat-provider health check re-verified 2026-06-10 — health and chat now share the same URL source by construction.

Tasks — **all done 2026-06-10**:

- [x] Add audit kind-count endpoint and server-backed kind filter. (`app/audit/kinds.py` classifier + `/admin/audit-logs/kind-counts`; also fixed the frontend bug where `chat_query` events showed as "Other".)
- [x] Add document inspector endpoint and UI panel. (`GET /admin/documents/{id}/inspect` — metadata, chunk sample, job history; wired into the existing documents side panel.)
- [x] Add stats time-series endpoint and use real sparkline data. (`GET /admin/stats/timeseries`, zero-filled daily buckets; 14-day sparklines on overview traffic cards.)
- [x] Add session list API and chat session sidebar. (`GET /chat/sessions` + `/chat/sessions/{id}/messages` with ownership check; sidebar with new-chat + restore.)
- [x] Add deterministic follow-up suggestions in the SSE `done` payload. (`build_follow_up_suggestions()` templated from cited documents, no extra LLM call; chips in chat UI.)
- [x] Chunk detail endpoint — **decision: skip.** SSE citations already carry excerpts for popovers, and the new inspect endpoint gives admins chunk previews. Revisit only if a customer needs full chunk text in citation popovers.
- [x] Review-queue actions — **decision: admin-status only for the pilot.** No end-user notification; the operator communicates outcomes through the pilot runbook process. Revisit for production if a customer workflow requires in-app notification.

Exit criteria — met (2026-06-10):

- Admin can inspect pilot activity without database access.
- Chat users can return to previous sessions.
- Pilot metrics are visible as real data, not static UI decoration.

### Phase D - Harden document lifecycle

Goal: make document updates/deletes reliable enough for customer pilots with changing corpora.

Tasks — **all done 2026-06-10**:

- [x] Implement `POST /admin/documents/{id}/upload-new-version`.
- [x] Ingest replacement chunks under a new version before switching `active_version`. (Staged ingest: `is_active=False` in Qdrant payload, excluded from retrieval and BM25; switch happens in `run_ingestion` only after full success — Qdrant flip first, then DB `active_version`, then BM25 rebuild.)
- [x] Keep old vectors for a short rollback window. (Superseded points get `superseded_at`; 24h window.)
- [x] Add cleanup job for stale old-version vectors. (Daily 02:30 UTC job: `delete_superseded_points` + `cleanup_superseded_chunk_rows`.)
- [x] Ensure retrieval filters on active document/chunk version. (Dense filter `must_not is_active=false`, BM25 payload skip, startup BM25 rebuild skip; legacy points without the field remain retrievable.)
- [x] Add tests proving users never retrieve a partial reindex. (`test_document_versioning.py`: failed replacement leaves previous version serving with `active_version` untouched and document still `indexed`; staged ingest never enters retrieval.)
- [x] Extend deletion verification to cover Qdrant, semantic cache, chunks, jobs, and BM25 state. (`GET /admin/documents/{id}/verify-deletion` returns per-store remnant counts + `clean` flag. Raw-file check is not included: after delete the doc row — and with it `storage_filename` — is gone; the delete path itself unlinks the file and logs failures.)

Exit criteria — met (2026-06-10):

- Reindex/replacement is atomic from the user's point of view. (Old `reindex` endpoint still uses delete-then-ingest and is kept for recovery scenarios; `upload-new-version` is the gap-free path.)
- Delete leaves no retrievable vectors for the deleted document, with auditable verification.

### Phase E - Production deployment options

Goal: turn the commercial deployment model into a production-ready packaging and release path.

**2026-06-10 progress** — the decision layer and the release pipeline are done; see `docs/release-process.md` (canonical Phase E decisions). Done: delivery-target decision (Compose default, air-gap supported, Helm = open roadmap), closed-runtime boundary, production image pipeline (`.github/workflows/release.yml`: test gates, trivy vulnerability scans, SPDX SBOMs, license reports, immutable GHCR version tags, evidence attached to GitHub releases), private-registry + offline update flows with rollback notes, licensing decision (contract entitlement, no runtime license server, air-gap never gated), source escrow decision (enterprise-only, contract-triggered), observability decisions (Langfuse/Prometheus/Dokploy out of current support; vLLM not claimed), and the first security-pack artifact (`docs/security-pack/audit-log-reference.md` — audit + agent trail field reference incl. deletion evidence).

Still open: Kubernetes/Helm package, data-flow diagram, threat model, controls mapping document, Enterprise WORM storage guide, image signing (deferred until a customer registry requires it).

Tasks:

- [x] Decide the default customer delivery target (2026-06-10, `docs/release-process.md`):
  - Docker Compose for Evaluation and small pilots,
  - Kubernetes/Helm for Enterprise,
  - air-gapped bundle for locked-down environments.
- [x] Define the closed-runtime boundary:
  - Safe4AI-owned source: orchestration, prompts, retrieval, chunking, reranking, guards, eval, deployment automation, UI workflows,
  - customer-owned data layer: documents, Postgres, Qdrant, users, audit logs, local model runtime, backups.
- [x] Add production image build pipeline:
  - backend image,
  - frontend image,
  - version labels,
  - immutable image tags,
  - release notes.
- [x] Add CI/CD release gates:
  - backend tests,
  - frontend build,
  - vulnerability scan,
  - SBOM generation,
  - dependency/license report,
  - image signing if registry supports it.
- [x] Write private registry update flow:
  - customer pulls approved versioned images,
  - migrations run through documented command,
  - rollback procedure is documented.
- [x] Write offline update flow:
  - export images,
  - export required model files,
  - transfer bundle,
  - load images,
  - run verifier,
  - apply migrations.
- [ ] Write Kubernetes/Helm package plan:
  - app deployment,
  - frontend deployment,
  - Postgres external dependency or chart value,
  - Qdrant external dependency or chart value,
  - secrets,
  - ingress,
  - persistent volumes,
  - resource requests/limits.
- [x] Write license/subscription enforcement decision:
  - prefer contract/support entitlement first,
  - add runtime license check only if necessary,
  - never make customer data access depend on a remote license server in air-gapped mode.
- [ ] Write enterprise security pack:
  - architecture diagram,
  - data-flow diagram,
  - threat model,
  - SBOM,
  - vulnerability scan report,
  - dependency/license report,
  - audit-log field reference,
  - agent audit trail reference,
  - backup/restore/deletion verification docs.
- [x] Define source escrow option:
  - enterprise-only,
  - contract-triggered release conditions,
  - excludes routine source handoff from standard package.
- [ ] Write Dokploy deployment guide if Dokploy is chosen as a supported deployment path.
- [x] Write Langfuse integration plan or explicitly keep Langfuse out of current support.
- [ ] Add Prometheus/Grafana only if customer deployment needs metrics beyond current OTLP/Jaeger/admin stats.
- [ ] Write vLLM/OpenAI-compatible deployment preset before mentioning vLLM in copy.
- [ ] Write Enterprise WORM storage guide that explains storage-layer responsibility.
- [ ] Write controls mapping document as an Enterprise service artifact.

Exit criteria:

- Customers can run Safe4AI without seeing the full source tree.
- Safe4AI can ship updates through versioned images/bundles.
- Security reviewers receive enough transparency without default source handoff.
- Deployment docs clearly separate supported paths from optional examples.
- Marketing copy only mentions supported deployment paths.

### Phase F - Enterprise expansion

Goal: add larger-account features only after the pilot package proves repeatable.

Candidates:

- [ ] SAML SSO.
- [ ] Multi-tenant workspace model.
- [ ] Workspace/project/client-level document access.
- [ ] Reviewer/staff/client role hierarchy.
- [ ] Customer-managed keys.
- [ ] Signed CSV, if explicitly required.
- [ ] Workflow automation via n8n or another engine.

Exit criteria:

- Each item has a named buyer requirement before implementation starts.

## Canonical Status Table

| Area | Current status | Next action |
|---|---|---|
| Core private RAG app | Done | Regression + real-service smoke |
| Auth/RBAC/OIDC | Done for OIDC | Do not claim SAML |
| Provider runtime hardening | Done | Keep pinned helper shared |
| Audit CSV | Done | Do not call it signed |
| Tamper-evident audit archive | Done for JSONL archive | WORM remains deployment responsibility |
| Admin UI | Done (2026-06-10) | Inspector, kind counts/filter, real sparklines shipped |
| Chat UX (sessions, follow-ups) | Done (2026-06-10) | Session sidebar + follow-up chips shipped |
| Evaluation tooling | Implemented | Run during pilots and attach to report |
| Final pilot report | Template done (2026-06-03) | Fill per pilot from `docs/pilot/final-readiness-report-template.md` |
| Paid pilot package | Templates done (2026-06-03) | Use `docs/pilot/` to sell/run/close pilots |
| Real-service smoke | Done (2026-06-03) | PASS 5/5; see `docs/pilot/smoke-run-log.md`; scanned-PDF OCR still unverified |
| Grounded inference contract | Done (2026-06-03, commit 9b21a02) | Rule 3 language robustness is a C0 task |
| Regression (tests + build) | Re-verified 2026-06-10 | 416 passed / 4 skipped; clean frontend build |
| Provider base URL invariant | Done (2026-06-10) | `effective_provider_base_url()` is the single source; commit pending |
| Closed-runtime deployment | Decisions + release pipeline done (2026-06-10) | `docs/release-process.md`; open: Helm, threat model, controls mapping |
| Document lifecycle (Phase D) | Done (2026-06-10) | upload-new-version, rollback window, verify-deletion shipped |
| Multi-tenant workspace | Not done | Enterprise candidate only |
| vLLM | Partial via OpenAI-compatible provider | Need docs/preset before claiming |
| Dokploy/Langfuse | Not integrated | Optional production guides |

## Immediate Next Step

**Phase A and Phase B are complete (2026-06-03).** Backend tests and frontend build pass (re-verified 2026-06-10), stale docs are corrected, a real-service smoke run is documented (`docs/pilot/smoke-run-log.md`, PASS 5/5), and the repeatable pilot package exists under `docs/pilot/`. The grounded inference answer contract landed 2026-06-03 (commit 9b21a02).

Next, in order:

1. ~~**C0 hardening**~~ — **done 2026-06-10**.
2. ~~**Phase C — Productize pilot operations**~~ — **done 2026-06-10** (all five features; two decisions recorded as deliberate pilot skips).
3. ~~**Phase D — Harden document lifecycle**~~ — **done 2026-06-10** (atomic `upload-new-version`, 24h rollback window + cleanup job, version-filtered retrieval, verify-deletion endpoint; 474 tests pass).
4. **Phase E — packaging/release** — decisions and the release pipeline are **done 2026-06-10** (`docs/release-process.md`, `.github/workflows/release.yml`, `docs/security-pack/audit-log-reference.md`). Remaining Phase E items are documentation/packaging work that should be driven by the first paying customer: Kubernetes/Helm package, data-flow diagram, threat model, controls mapping, WORM storage guide, image signing.
5. **Validate the pipeline**: push a `v0.x.y` tag and confirm the release workflow goes green end-to-end (images in GHCR, SBOM/scan/license artifacts on the release).
6. **Phase F** stays gated on named buyer requirements.

Operational follow-ups worth doing in the next working session:

- Run a real-service smoke covering the new flows: upload → new-version upload mid-conversation → confirm no retrieval gap; delete → `verify-deletion` clean. Include a scanned PDF to finally exercise OCR.
- The legacy `reindex` endpoint still uses delete-then-ingest; consider routing the admin UI "Reindex" through the staged path too, or documenting it as a recovery tool.

Earlier smoke-run findings, current status:

- ~~Add a health check that pings the **chat** provider, not just embeddings~~ — root cause (stale DB `provider_base_url`) addressed by the in-progress runtime fix; verify as C0.
- Note for sparse-corpus pilots: `route_after_grade` needs ≥2 relevant chunks for the direct generate path; single-fact docs detour through decompose and can hit the grounding fallback. (Still true.)

Original reasoning (kept for context): the application is already strong enough for a pilot, but the product package was not yet repeatable. Building more enterprise features before the discovery/report/runbook artifacts would increase scope without making the offer easier to sell or deliver.
