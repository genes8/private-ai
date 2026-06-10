# Audit Log and Agent Trail Field Reference

Date: 2026-06-10
Audience: customer security reviewers (enterprise security pack artifact)

Safe4AI records operational evidence in the customer's own PostgreSQL
database. Nothing in these tables leaves the customer environment. This
document describes what is recorded, field by field, and what is deliberately
**not** recorded.

## Privacy guarantees

- Audit rows are append-only in normal operation; the only deletion path is
  the retention cleanup job, which first writes a tamper-evident JSONL archive
  (HMAC-chained) before deleting expired rows.
- Query text is truncated to the **first 500 characters**.
- Passwords, JWTs, session cookies, and API keys are never written to audit
  rows or logs.
- Retention is configurable (`audit_log_retention_days`, default 365); the
  admin Activity page displays the active retention.

## `audit_logs` — user/admin activity

One row per audited action. Exported via `GET /admin/audit-logs/export.csv`.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | Row identifier |
| `user_id` | uuid, nullable | Acting user; null for system actions. FK to `users` |
| `session_id` | uuid, nullable | Chat session the action belongs to, when applicable |
| `timestamp` | timestamptz | Server-side time of the action |
| `action_type` | string | Raw action name, e.g. `chat_query`, `settings_provider_change`. The admin UI groups these into kinds (query/upload/feedback/login/fallback/admin/other) via a server-side classifier |
| `query_text` | string(500), nullable | First 500 chars of the user query, when the action is a query |
| `response_metadata` | json, nullable | Action-specific evidence: for chats — `trace_id`, retrieved-chunk count, completion status, token usage and its source (`actual` vs `estimated`); for provider changes — before/after of provider type, embedding source, base URL, and whether a key is configured (never the key itself) |
| `latency_ms` | integer, nullable | End-to-end latency for query actions |
| `model_used` | string, nullable | Model that produced the answer |
| `trace_id` | string, nullable | Correlates with OpenTelemetry spans and `query_feedback.trace_id` |

## `agent_runs` — agent pipeline trail

One row per agent pipeline execution (i.e. per answered query), giving the
agent-level audit trail referenced in the security review.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | Run identifier |
| `session_id` | uuid | Owning chat session |
| `started_at` / `finished_at` | timestamptz | Run window |
| `status` | string | `completed`, `failed`, or fallback outcomes |
| `final_output` | text, nullable | The answer as delivered (post output-filter) |
| `error` | text, nullable | Failure reason when status is failed |
| `cost_usd` | float | Estimated/actual cost attributed to the run |

Step-level detail (retrieve → grade → generate → output filter → quality gate)
is exported as OpenTelemetry spans, correlated by `trace_id`; in the default
deployment these go to the local Jaeger instance and never leave the
environment.

## `query_feedback` — user feedback

| Field | Type | Description |
|---|---|---|
| `id` | uuid | Row identifier |
| `trace_id` | string | Links feedback to the exact answer/run |
| `session_id` | uuid | Owning session |
| `user_id` | uuid | Rating user (FK `users`) |
| `rating` | enum | `positive` / `negative` |
| `comment` | text, nullable | Free-text note |
| `created_at` | timestamptz | Submission time |

## `ingestion_jobs` — document processing trail

| Field | Type | Description |
|---|---|---|
| `id` | uuid | Job identifier |
| `document_id` | uuid | FK `documents` (cascade delete) |
| `status` | enum | `pending` / `embedding` / `completed` / `failed` |
| `created_at` / `completed_at` | timestamptz | Job window |
| `error` | text, nullable | Failure reason (truncated to 2000 chars) |

## Deletion evidence

`GET /admin/documents/{id}/verify-deletion` (admin-only) returns per-store
remnant counts after a document delete — Qdrant vectors, DB chunk rows,
ingestion jobs, semantic-cache entries, in-memory BM25 entries — with a
`clean` flag that is true only when every count is zero. Suitable as an
attachment to deletion requests under data-protection processes.
