Now I have a thorough understanding. Let me compile the full structured summary.

---

## Database Layer Summary — Safe4AI Pilot

---

### 1. Database Type and Connection

| Property | Value |
|---|---|
| **Type** | PostgreSQL (with `pgvector` extension) |
| **Connection** | `postgresql+psycopg2://safe4ai:safe4ai@localhost:5432/safe4ai` |
| **ORM** | SQLAlchemy (`create_engine` with `pool_pre_ping=True`) |
| **Session** | `SessionLocal` — `sessionmaker(autocommit=False, autoflush=False)` |
| **Schema creation** | `Base.metadata.create_all(bind=engine)` called in the FastAPI lifespan |
| **Vector extension** | `CREATE EXTENSION IF NOT EXISTS vector` executed first in lifespan |
| **Migrations** | Alembic configured in `app/db/migrations/` with `env.py` reading URL from `settings.postgres_url`, but **the `versions/` directory is empty** — no migration scripts exist; schema is auto-created by SQLAlchemy directly |

---

### 2. Full Schema — 10 Tables

#### 2.1 `users`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | String | PK | UUID |
| `email` | String | UNIQUE, NOT NULL, INDEX | User email |
| `password_hash` | String | NOT NULL | bcrypt hash |
| `role` | Enum(UserRole) | NOT NULL, default=`pilot_user` | `admin` or `pilot_user` |
| `created_at` | DateTime(tz) | server_default=func.now() | |
| `is_active` | Boolean | default=True | Soft-delete flag |
| `failed_login_count` | Integer | default=0 | Brute-force counter |
| `locked_until` | DateTime(tz) | nullable | Account lock time |

**Relationships**: Referenced by `sessions.user_id`, `documents.uploaded_by`, `audit_logs.user_id`, `query_feedback.user_id`, `human_review_queue.user_id` (all via FK).

#### 2.2 `sessions`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | String | PK | UUID |
| `user_id` | String | FK→users.id ON DELETE CASCADE, NOT NULL, INDEX | |
| `created_at` | DateTime(tz) | server_default=func.now() | |
| `updated_at` | DateTime(tz) | onupdate=func.now() | |
| `state_json` | JSON | nullable | Full `PrivateAIState` serialized |

#### 2.3 `documents`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | String | PK | UUID |
| `filename` | String | NOT NULL | Original filename |
| `storage_filename` | String | NOT NULL | Filesystem safe name (`{stem}-{uuid}.ext`) |
| `file_type` | String | NOT NULL | Extension without dot (e.g. `pdf`, `txt`) |
| `ingestion_status` | Enum(IngestionStatus) | NOT NULL, default=`queued` | `queued`→`embedding`→`indexed`/`failed`/`skipped` |
| `uploaded_by` | String | FK→users.id, NOT NULL | |
| `uploaded_at` | DateTime(tz) | server_default=func.now() | |
| `doc_metadata` | JSON | nullable | |
| `ingestion_started_at` | DateTime(tz) | nullable | Set when embedding begins |
| `version` | Integer | default=1 | Document version |
| `active_version` | Integer | default=1 | |

**Relationships**: Referenced by `document_chunks.document_id`, `ingestion_jobs.document_id` (both CASCADE).

#### 2.4 `document_chunks`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | String | PK | UUID |
| `document_id` | String | FK→documents.id ON DELETE CASCADE, NOT NULL, INDEX | |
| `chunk_index` | Integer | NOT NULL | Position in document |
| `chunk_version` | Integer | default=1 | |
| `content_preview` | String(500) | nullable | First 200 chars of chunk |
| `qdrant_point_id` | String | nullable | Qdrant point UUID |

#### 2.5 `semantic_cache`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | String | PK | UUID |
| `query_embedding` | Vector(768) | NOT NULL | pgvector embedding |
| `query_text` | Text | NOT NULL | Original query |
| `response_json` | JSON | NOT NULL | Cached answer text |
| `citations_json` | JSON | nullable | List of Citation dicts |
| `source_document_ids` | JSON | nullable | Array of doc IDs |
| `source_chunk_ids` | JSON | nullable | Array of chunk IDs |
| `created_at` | DateTime(tz) | server_default=func.now() | |
| `hit_count` | Integer | default=0 | Incremented on lookup |

#### 2.6 `audit_logs`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | String | PK | UUID |
| `user_id` | String | FK→users.id, nullable, INDEX | |
| `session_id` | String | nullable | |
| `timestamp` | DateTime(tz) | server_default=func.now(), INDEX | |
| `action_type` | String | NOT NULL | e.g. `system_cleanup` |
| `query_text` | String(500) | nullable | |
| `response_metadata` | JSON | nullable | |
| `latency_ms` | Integer | nullable | |
| `model_used` | String | nullable | |
| `trace_id` | String | nullable | |

> **Note:** The `audit_logs` table is defined with all columns needed for per-query auditing (`action_type`, `query_text`, `latency_ms`, `model_used`, `trace_id`), but **no write operations exist in the current chat/query flows**. Currently, audit log rows are only written by the scheduled cleanup task (`action_type = "system_cleanup"`). The frontend maps expected `action_type` values: `"login"`, `"query"`, `"upload"`, `"feedback"`, `"fallback"` — but the backend does not insert these yet.

#### 2.7 `agent_runs`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | String | PK | UUID |
| `session_id` | String | NOT NULL, INDEX | |
| `started_at` | DateTime(tz) | server_default=func.now() | |
| `finished_at` | DateTime(tz) | nullable | |
| `status` | String | NOT NULL | e.g. `"completed"`, `"failed"` |
| `final_output` | Text | nullable | |
| `error` | Text | nullable | |
| `cost_usd` | Float | default=0.0 | |

#### 2.8 `query_feedback`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | String | PK | UUID |
| `trace_id` | String | NOT NULL, INDEX | |
| `session_id` | String | NOT NULL | |
| `user_id` | String | FK→users.id ON DELETE CASCADE, NOT NULL | |
| `rating` | Enum(FeedbackRating) | NOT NULL | `positive` or `negative` |
| `comment` | Text | nullable | |
| `created_at` | DateTime(tz) | server_default=func.now() | |

#### 2.9 `ingestion_jobs`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | String | PK | UUID |
| `document_id` | String | FK→documents.id ON DELETE CASCADE, NOT NULL, INDEX | |
| `status` | Enum(IngestionJobStatus) | NOT NULL, default=`pending` | `pending`→`embedding`→`completed`/`failed` |
| `created_at` | DateTime(tz) | server_default=func.now() | |
| `completed_at` | DateTime(tz) | nullable | |
| `error` | Text | nullable | Truncated to 2000 chars |

#### 2.10 `human_review_queue`
| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | String | PK | UUID |
| `session_id` | String | NOT NULL | |
| `user_id` | String | FK→users.id ON DELETE CASCADE, NOT NULL | |
| `query` | Text | NOT NULL | Truncated to 500 chars |
| `draft_answer` | Text | nullable | |
| `citations_json` | JSON | nullable | |
| `risk_reason` | Text | nullable | `"Automatic flagging: low retrieval quality or output blocked"` |
| `status` | Enum(ReviewStatus) | NOT NULL, default=`pending` | `pending`→`approved`/`rejected` |
| `reviewed_by` | String | nullable | Admin user ID who reviewed |
| `reviewed_at` | DateTime(tz) | nullable | |

---

### 3. Data Flows per User Action

#### 3.1 Login (`POST /auth/login`)

**Tables affected: `users`**

| Operation | Records |
|---|---|
| **Conditional UPDATE** | `users.failed_login_count` incremented, and if ≥10 → `users.locked_until` set (now + 15 min) |
| **Conditional UPDATE** | On success: `users.failed_login_count = 0` |

**Flow:**
1. Query `users` by `email`
2. If user exists and `locked_until > now` → 429
3. Verify bcrypt password
4. If password fails: increment `failed_login_count`, possibly set `locked_until`
5. If password succeeds: reset `failed_login_count = 0`, issue JWT in HTTP‑Only cookie

**Validation query:**
```sql
-- Check login failures
SELECT email, failed_login_count, is_active, locked_until
FROM users
WHERE email = 'admin@safe4ai.local';
```

#### 3.2 Logout (`POST /auth/logout`)

**No DB writes.** Clears the `access_token` cookie only.

#### 3.3 Send Chat Message (`POST /chat` or `POST /chat/stream`)

**Tables affected: `sessions`, `human_review_queue`**

| Operation | Records |
|---|---|
| **INSERT** | `sessions` — if `session_id` not provided in request, one new row created via `ConversationManager.new_session()` |
| **UPDATE** | `sessions.state_json` — updated after graph completes with full conversation history + final answer |
| **Conditional INSERT** | `human_review_queue` — if `requires_human_review` is `True` (determined during quality gate) |

**Flow (detailed):**
1. `_resolve_session()` — if `session_id` provided, loads via `ConversationManager.load_session()` (reads `sessions.state_json`); otherwise creates new `sessions` row
2. Runs LangGraph through nodes: `intake → rewrite → retrieve → grade → [decompose?] → generate → output_filter → quality_gate → respond/fallback`
3. On completion: `ConversationManager.save_session()` updates `sessions.state_json` with final `PrivateAIState` (includes message history + citations + metadata)
4. If `requires_human_review`: inserts `human_review_queue` row

**Note:** `audit_logs` and `agent_runs` are **not currently written** by the chat flow. The `CostTracker.record_run()` and `AuditLog` inserts exist as reusable functions but are not called from the chat routes. The graph is stateless with respect to DB (it only operates on `PrivateAIState`).

**Validation queries:**
```sql
-- Check session state JSON
SELECT id, user_id, updated_at, length(state_json::text) AS state_size
FROM sessions
WHERE user_id = '<user_id>'
ORDER BY updated_at DESC
LIMIT 5;

-- Check if human review was triggered
SELECT id, session_id, user_id, query, status
FROM human_review_queue
WHERE session_id = '<session_id>';

-- For a given trace, verify no agent_run was recorded (current gap)
SELECT COUNT(*) FROM agent_runs WHERE session_id = '<session_id>';
```

#### 3.4 Submit Feedback (`POST /feedback`)

**Tables affected: `query_feedback`**

| Operation | Records |
|---|---|
| **INSERT** | `query_feedback` — one row with `rating` (`positive`/`negative`), optional `comment` |

**Validation query:**
```sql
SELECT id, trace_id, session_id, user_id, rating, comment, created_at
FROM query_feedback
WHERE trace_id = '<trace_id>'
ORDER BY created_at DESC;
```

#### 3.5 Upload Document (`POST /admin/documents/upload`) — Admin only

**Tables affected: `documents`, `ingestion_jobs`, `document_chunks` (async)**

| Operation | Records |
|---|---|
| **INSERT** | `documents` — one row, status=`queued` |
| **INSERT** | `ingestion_jobs` — one row, status=`pending` |
| **Async INSERT** (x N) | `document_chunks` — one row per chunk created during ingestion |
| **Async UPDATE** | `documents.ingestion_status` → `embedding` → `indexed`/`failed`/`skipped` |
| **Async UPDATE** | `ingestion_jobs.status` → `embedding` → `completed`/`failed` |

**Flow:**
1. File validated via `UploadValidator` (type/size/magic bytes)
2. File saved to `data/raw/{storage_name}`
3. `documents` row created (`ingestion_status=queued`, `uploaded_by=current_admin`)
4. `ingestion_jobs` row created (`status=pending`, `document_id=doc_id`)
5. Background task `run_ingestion()`:
   - Sets `ingestion_jobs.status = embedding`, `documents.ingestion_status = embedding`, `documents.ingestion_started_at = now`
   - Processes file (PDF with OCR fallback, DOCX, XLSX, or text)
   - Chunks via `RecursiveCharacterTextSplitter` (chunk_size=800, overlap=150)
   - Embeds via Ollama (`nomic-embed-text`), upserts to Qdrant
   - Creates `document_chunks` rows (one per chunk with `qdrant_point_id`)
   - Sets `documents.ingestion_status = indexed` (or `skipped` if OCR confidence low, `failed` on error)
   - Sets `ingestion_jobs.status = completed` (or `failed`) with `completed_at`

**Validation queries:**
```sql
-- Document status
SELECT d.id, d.filename, d.ingestion_status, d.uploaded_at, d.version,
       ij.status AS job_status, ij.error AS job_error, ij.completed_at
FROM documents d
LEFT JOIN ingestion_jobs ij ON ij.document_id = d.id
WHERE d.id = '<doc_id>'
ORDER BY ij.created_at DESC;

-- Chunk count
SELECT d.id, d.filename, COUNT(dc.id) AS chunk_count
FROM documents d
LEFT JOIN document_chunks dc ON dc.document_id = d.id
WHERE d.id = '<doc_id>'
GROUP BY d.id, d.filename;
```

#### 3.6 List Documents (`GET /admin/documents`) — Admin only

**Read-only.** Queries `documents` LEFT JOIN with subquery count of `document_chunks`.

**Validation query:**
```sql
-- Same as admin endpoint
SELECT d.id, d.filename, d.file_type, d.ingestion_status, d.uploaded_at,
       d.version, d.active_version,
       COALESCE(dc_counts.cnt, 0) AS chunk_count
FROM documents d
LEFT JOIN (
    SELECT document_id, COUNT(id) AS cnt
    FROM document_chunks
    GROUP BY document_id
) dc_counts ON d.id = dc_counts.document_id
ORDER BY d.uploaded_at DESC;
```

#### 3.7 Delete Document (`DELETE /admin/documents/{doc_id}`) — Admin only

**Tables affected: `documents`, `document_chunks`, `ingestion_jobs`, `semantic_cache`, filesystem, Qdrant**

| Operation | Records |
|---|---|
| **DELETE** | `document_chunks` — all rows for this `document_id` |
| **DELETE** | `ingestion_jobs` — all rows for this `document_id` |
| **DELETE** | `documents` — the document row |
| **DELETE** | `semantic_cache` — entries referencing this `doc_id` via JSONB `@>` |
| **DELETE** | Qdrant — points with `doc_id` filter |
| **DELETE** | File — `data/raw/{storage_filename}` removed |

**Validation query:**
```sql
-- Verify deletion
SELECT COUNT(*) AS remaining_chunks FROM document_chunks WHERE document_id = '<doc_id>';
SELECT COUNT(*) AS remaining_jobs FROM ingestion_jobs WHERE document_id = '<doc_id>';
SELECT * FROM documents WHERE id = '<doc_id>';
SELECT COUNT(*) AS remaining_cache_entries
FROM semantic_cache
WHERE source_document_ids::jsonb @> '["<doc_id>"]'::jsonb;
```

#### 3.8 Reindex Document (`POST /admin/documents/{doc_id}/reindex`) — Admin only

**Tables affected: `documents`, `ingestion_jobs`, `document_chunks`**

| Operation | Records |
|---|---|
| **UPDATE** | `documents.ingestion_status = queued` |
| **INSERT** | `ingestion_jobs` — new job with `status=pending` |
| **Async DELETE + INSERT** | `document_chunks` — old chunks replaced via `run_ingestion` (which recreates chunks + Qdrant points) |

**Validation query:**
```sql
SELECT d.id, d.ingestion_status, ij.status AS job_status, ij.id AS job_id
FROM documents d
JOIN ingestion_jobs ij ON ij.document_id = d.id
WHERE d.id = '<doc_id>'
ORDER BY ij.created_at DESC;
```

#### 3.9 List/Export Audit Logs (`GET /admin/audit-logs`, `GET /admin/audit-logs/export.csv`) — Admin only

**Read-only.** Queries `audit_logs` with optional `start`, `end`, `user_id` filters, pagination. Export limited to 50k rows as CSV.

**Validation query:**
```sql
-- As used by the admin endpoint
SELECT id, user_id, session_id, timestamp, action_type, query_text, latency_ms, model_used, trace_id
FROM audit_logs
WHERE timestamp >= '<start>' AND timestamp <= '<end>'
  AND user_id IS NOT DISTINCT FROM '<user_id>'
ORDER BY timestamp DESC
LIMIT 100 OFFSET 0;
```

#### 3.10 Create User (`POST /admin/users`) — Admin only

**Tables affected: `users`**

| Operation | Records |
|---|---|
| **INSERT** | `users` — one row with bcrypt-hashed password |

**Validation query:**
```sql
SELECT id, email, role, is_active, created_at
FROM users
WHERE email = '<email>';
```

#### 3.11 Deactivate User (`DELETE /admin/users/{user_id}`) — Admin only

**Tables affected: `users`**

| Operation | Records |
|---|---|
| **UPDATE** | `users.is_active = False` (soft-delete, not actual DELETE) |

**Validation query:**
```sql
SELECT id, email, is_active
FROM users
WHERE id = '<user_id>';
```

#### 3.12 List Users (`GET /admin/users`) — Admin only

**Read-only.** Queries `users` ordered by `created_at DESC`.

#### 3.13 Get Stats (`GET /admin/stats`) — Admin only

**Read-only aggregate queries:**
- `COUNT(audit_logs)` where `timestamp >= cutoff` → total queries
- `AVG(audit_logs.latency_ms)` where `timestamp >= cutoff` → avg latency
- `SUM(agent_runs.cost_usd)` where `started_at >= cutoff` → total cost
- `SUM(semantic_cache.hit_count)` → total cache hits
- `COUNT(users)` where `is_active = True` → unique users

**Validation query:**
```sql
-- All stats in one query
SELECT
    (SELECT COUNT(*) FROM audit_logs WHERE timestamp >= now() - INTERVAL '30 days') AS total_queries,
    (SELECT AVG(latency_ms) FROM audit_logs WHERE timestamp >= now() - INTERVAL '30 days') AS avg_latency_ms,
    (SELECT COALESCE(SUM(cost_usd), 0) FROM agent_runs WHERE started_at >= now() - INTERVAL '30 days') AS total_cost,
    (SELECT COALESCE(SUM(hit_count), 0) FROM semantic_cache) AS cache_hits,
    (SELECT COUNT(*) FROM users WHERE is_active = TRUE) AS active_users;
```

#### 3.14 Human Review Queue — Review (Approve/Reject)

**Tables affected: `human_review_queue`**

| Operation | Records |
|---|---|
| **UPDATE** | `status` → `approved` or `rejected` |
| **UPDATE** | `reviewed_by` = admin user ID |
| **UPDATE** | `reviewed_at` = now |

**Validation query:**
```sql
SELECT id, session_id, user_id, query, status, reviewed_by, reviewed_at
FROM human_review_queue
WHERE id = '<item_id>';
```

#### 3.15 Cost Stats (`GET /admin/stats/cost`) — Admin only

**Read-only.** Queries `agent_runs` filtered by `started_at >= cutoff`, optionally joined with `sessions` table for per-user filtering. Returns total cost, run count, and daily breakdown.

#### 3.16 System Cleanup (Daily Cron)

**Tables affected: `audit_logs`, `semantic_cache`**

| Operation | Records |
|---|---|
| **DELETE** | `audit_logs` — rows where `timestamp < now() - 90 days` |
| **DELETE** | `semantic_cache` — rows where `created_at < now() - 30 days` |
| **INSERT** | `audit_logs` — one summary row with `action_type = 'system_cleanup'` |

**Validation query:**
```sql
-- Verify cleanup ran
SELECT id, timestamp, action_type, response_metadata
FROM audit_logs
WHERE action_type = 'system_cleanup'
ORDER BY timestamp DESC
LIMIT 1;
```

---

### 4. Validation Queries (Master List)

```sql
-- 1. Users
SELECT * FROM users ORDER BY created_at DESC;

-- 2. Active sessions for a user
SELECT s.id, s.user_id, s.created_at, s.updated_at
FROM sessions s
WHERE s.user_id = '<user_id>'
ORDER BY s.updated_at DESC;

-- 3. Document with ingestion status
SELECT d.id, d.filename, d.file_type, d.ingestion_status, d.uploaded_at,
       d.version, d.active_version, ij.status AS job_status, ij.error
FROM documents d
LEFT JOIN ingestion_jobs ij ON ij.document_id = d.id
ORDER BY d.uploaded_at DESC;

-- 4. Chunks for a document
SELECT dc.id, dc.document_id, dc.chunk_index, dc.chunk_version,
       dc.content_preview, dc.qdrant_point_id
FROM document_chunks dc
WHERE dc.document_id = '<doc_id>'
ORDER BY dc.chunk_index;

-- 5. Semantic cache hits
SELECT sc.id, sc.query_text, sc.hit_count, sc.created_at,
       sc.source_document_ids
FROM semantic_cache sc
ORDER BY sc.hit_count DESC;

-- 6. Audit logs summary
SELECT action_type, COUNT(*) AS count, MIN(timestamp) AS first, MAX(timestamp) AS last
FROM audit_logs
GROUP BY action_type
ORDER BY count DESC;

-- 7. Agent runs
SELECT ar.id, ar.session_id, ar.status, ar.cost_usd, ar.started_at, ar.finished_at
FROM agent_runs ar
ORDER BY ar.started_at DESC
LIMIT 20;

-- 8. Feedback summary
SELECT qf.rating, COUNT(*) AS count
FROM query_feedback qf
GROUP BY qf.rating;

-- 9. Human review queue
SELECT hrq.id, hrq.session_id, hrq.user_id, hrq.query,
       hrq.status, hrq.reviewed_by, hrq.reviewed_at
FROM human_review_queue hrq
ORDER BY hrq.id;

-- 10. Ingested document details (chunk count per doc)
SELECT d.id, d.filename, d.ingestion_status, COUNT(dc.id) AS chunk_count
FROM documents d
LEFT JOIN document_chunks dc ON dc.document_id = d.id
GROUP BY d.id, d.filename, d.ingestion_status
ORDER BY d.uploaded_at DESC;

-- 11. Cache invalidation check for a document
SELECT COUNT(*) AS affected_cache_entries
FROM semantic_cache
WHERE source_document_ids::jsonb @> '["<doc_id>"]'::jsonb;
```

---

### 5. Seed Data

#### Admin User
| Field | Value |
|---|---|
| **email** | `admin@safe4ai.local` |
| **password** | Printed by `scripts/seed.py` at runtime or supplied with `SEED_ADMIN_PASSWORD` |
| **role** | `admin` |
| **id** | (auto-generated UUID) |

#### Sample Documents (3 policy files)
| File | Content Type | Pages |
|---|---|---|
| `hr_policy.txt` | HR Policy — annual leave, sick leave, parental leave, public holidays | ~50 lines |
| `finance_policy.txt` | Finance & Procurement — CapEx approval matrix, OpEx, expense reimbursement, budget management | ~40 lines |
| `it_policy.txt` | IT Security — password requirements, device security, data handling, incident reporting | ~40 lines |

Each document is:
- Saved as `data/raw/{stem}-{uuid}.txt`
- Inserted into `documents` with `ingestion_status = queued`, `uploaded_by = admin_id`
- Has a corresponding `ingestion_jobs` row with `status = pending`
- Automatically ingested (embedded + indexed to Qdrant) during seed execution

**Running seed:** `cd safe4ai-pilot && python scripts/seed.py` (requires Ollama + Qdrant for the ingestion step to succeed).

---

### 6. Key Observations / Gaps

1. **Audit log writes are missing.** The `audit_logs` table is fully defined with all fields needed for per-query auditing (`action_type`, `query_text`, `latency_ms`, `model_used`, `trace_id`), and the frontend expects entries with types `"login"`, `"query"`, `"upload"`, `"feedback"`, `"fallback"`. However, **no backend code currently inserts these rows** during normal operations — only the cleanup task writes to it.

2. **Agent run recording is defined but not wired.** `CostTracker.record_run()` creates `agent_runs` rows, but is not called from any current code path.

3. **Schema is auto-created, not migrated.** Alembic is configured but the `versions/` directory is empty. Schema is created fresh via `Base.metadata.create_all()` in the lifespan. This means schema changes must be managed manually or via migration generation.

4. **Soft-delete for users.** Users are deactivated (`is_active = False`) rather than deleted, preserving referential integrity for existing FK references.

5. **Cascade deletes.** `sessions`, `document_chunks`, `ingestion_jobs`, `query_feedback`, and `human_review_queue` all use `ON DELETE CASCADE` from their parent FK, ensuring clean deletions.

6. **Vector extension required.** The `semantic_cache.query_embedding` column uses `Vector(768)`, which requires the `pgvector` PostgreSQL extension — created at application startup.
