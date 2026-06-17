# Threat Model

Date: 2026-06-12
Audience: customer security reviewers

This threat model covers the default single-tenant Safe4AI runtime deployed in
customer-controlled infrastructure.

## Assets

- Uploaded source documents and parsed document text.
- Vector embeddings and chunk metadata.
- Chat sessions, prompts, answers, citations, and feedback.
- Audit logs, agent runs, and tamper-evident audit archives.
- Admin settings, provider credentials, JWT cookies, and CSRF tokens.
- Release images, SBOMs, vulnerability reports, and image signatures.

## Trust boundaries

- Browser to frontend over HTTPS.
- Frontend to backend through the nginx reverse proxy.
- Backend to PostgreSQL, Qdrant, local model runtime, and OTLP collector.
- Backend to optional OpenAI-compatible provider when non-local mode is
  explicitly configured.
- Release pipeline to GHCR and GitHub release artifacts.

## STRIDE summary

| Threat | Risk | Current control |
|---|---|---|
| Spoofing | Stolen session cookie or forged admin identity | JWT auth, secure cookie settings, CSRF on unsafe methods, role checks |
| Tampering | Modified release image or audit archive | Immutable image tags, cosign signatures, HMAC-chained audit archive manifests |
| Repudiation | User denies query, upload, provider change, or deletion | `audit_logs`, `agent_runs`, feedback rows, deletion verification endpoint |
| Information disclosure | Prompt/document leakage to unapproved provider | Local mode default, explicit provider mode, settings audit, provider URL validation |
| Denial of service | Oversized upload/body, expensive queries, dependency outage | Upload limits, body size checks, quota/cost ceilings, health checks, dependency probes |
| Elevation of privilege | Pilot user reaches admin APIs | `RequireAdmin` frontend guard plus backend admin dependency checks |

## Abuse cases and mitigations

Prompt injection:

- Input guard blocks common injection patterns.
- Retrieval content filter removes blocked content before generation.
- Output filter checks answer grounding and PII leakage.

SSRF and provider abuse:

- OpenAI-compatible provider URLs are validated.
- Runtime HTTP clients use pinned transports for provider calls.
- Local Ollama mode ignores stale provider base URLs.

Audit deletion:

- Retention cleanup writes JSONL archives and signed manifests before deleting
  expired rows.
- WORM retention, if required, is applied by the customer storage layer.

Release tampering:

- Release workflow builds versioned backend/frontend images.
- Images are scanned, SBOMs are generated, and images are signed after push.
- Customers verify signatures and release evidence before deployment.

Cross-workspace data exposure (intra-deployment trust boundary):

- A deployment may be sub-divided into workspaces (e.g. Legal, Finance). A
  member of one workspace must never read another workspace's documents, cached
  answers, sessions, audit, feedback, or review items.
- Retrieval is fail-closed: every chat query is scoped to the user's single
  active workspace on BOTH the dense (Qdrant `workspace_id` filter) and sparse
  (BM25) paths; an empty scope retrieves nothing. The only `retriever.retrieve`
  call sites (the graph retrieve/decompose nodes) always pass the membership-
  derived scope.
- The semantic cache is workspace-keyed (lookup and store) so a cached answer
  cannot cross workspaces; it is currently latent (no runtime call site) and
  gated against unsafe activation.
- Chat sessions are immutable to their workspace (cross-workspace replay → 409).
- Admin surfaces (documents, audit, stats, feedback, review) are scoped:
  org-admin is unrestricted, a workspace-admin sees only their workspaces, and
  foreign objects return 404 (no IDOR enumeration). Workspace authority is
  resolved per request from the DB, never trusted from the JWT.
- Migration window: vectors written before the workspace upgrade carry no
  `workspace_id` and are intentionally unsearchable (fail-closed) until a
  background backfill assigns them to the default workspace; `/health` does not
  flip, but an admin status endpoint reports the pending state.
- Quotas remain a per-deployment commercial boundary (not per-workspace).

## Residual risks

- Customer-operated PostgreSQL, Qdrant, object/file storage, WORM retention,
  and backups are outside the application boundary.
- Hybrid/cloud provider mode sends approved prompts/context to the configured
  provider.
- vLLM operation, GPU scheduling, and model security are customer platform
  responsibilities when vLLM is used through the OpenAI-compatible preset.
