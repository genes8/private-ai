# Safe4AI Readiness Pilot — Package Index

This directory holds the repeatable templates used to **sell, start, operate, and close** a Safe4AI Private AI Readiness Pilot. Each template is a fill-in document — copy it per customer, replace the `<placeholder>` tokens, and keep the completed copy in the engagement folder.

The pilot platform itself (private RAG chat, document ingestion, admin/audit, provider settings, evaluation tooling) is already built. These templates wrap that platform in a repeatable service motion so each pilot does not need improvisation.

## Pilot lifecycle

| Stage | Template | Purpose |
|---|---|---|
| 1. Discover | [`discovery-questionnaire.md`](discovery-questionnaire.md) | Capture the customer's goal, workflow, data, users, and constraints. |
| 2. Select | [`workflow-selection-template.md`](workflow-selection-template.md) | Choose **one** workflow to pilot, with a defensible rationale. |
| 3. Intake | [`data-inventory-template.md`](data-inventory-template.md) | Inventory the documents to ingest, their volume and sensitivity. |
| 4. Secure | [`security-review-checklist.md`](security-review-checklist.md) | Pre-pilot security review + deployment/IP boundary decisions. |
| 5. Run | [`pilot-runbook.md`](pilot-runbook.md) | Operate the pilot day-to-day: provision, ingest, monitor, evaluate. |
| 6. Report | [`final-readiness-report-template.md`](final-readiness-report-template.md) | The deliverable: what worked, what missed, recommendation. |
| 7. Score | [`production-readiness-scorecard.md`](production-readiness-scorecard.md) | Go/no-go scorecard across quality, security, ops, deployment. |
| 8. Scope | [`rollout-scope-cost-template.md`](rollout-scope-cost-template.md) | Production scope and rough cost drivers for expansion. |

A `smoke-run-log.md` is also kept here to record real-service smoke runs of the platform.

## Scope guardrails (do not over-promise)

These are **not** available as product features today and must not be presented as such in any completed template:

- SAML SSO — only **OIDC SSO** exists.
- Signed / tamper-evident **CSV** export — audit CSV export exists, but is not signed. (A tamper-evident JSONL audit *archive* does exist for retention cleanup.)
- App-owned **WORM / immutable storage** — immutability is a deployment/storage-layer responsibility, not an app guarantee.
- **Multi-tenant** workspaces — the product is one workspace / evaluation boundary.
- Bundled **vLLM** runtime — vLLM is documented only as an OpenAI-compatible
  provider preset; Safe4AI does not operate vLLM itself.

"Data never leaves your network" is true only in **local / on-prem mode**. In cloud or hybrid provider modes, scope the claim accordingly.

## Product facts to reuse

- **Tiers:** Evaluation, Team, Enterprise (Evaluation seeded by default: 5 seats, 5,000 queries/month).
- **Roles:** `admin`, `pilot_user`.
- **Providers:** local (Ollama) and OpenAI-compatible HTTP endpoints, with SSRF validation and pinned outbound transport.
- **Supported uploads:** `.pdf`, `.docx`, `.xlsx`, `.txt`, plus scanned/image PDF via the OCR path.
- **Evaluation tooling:** `evaluation/offline_eval.py`, `evaluation/online_monitor.py`, `evaluation/golden_dataset.json`.
- **Observability:** OpenTelemetry/OTLP spans (local Jaeger supported) plus admin stats, audit, feedback, and cost tables.
