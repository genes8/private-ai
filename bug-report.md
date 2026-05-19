# Bug Hunting & Mockup Analysis — safe4ai-pilot/ (2026-05-18)

## 🔴 CRITICAL — Mockup Data / Fake Data Reaching Users

### 1. Hardcoded "sources" in Settings API response — `app/api/admin_routes.py:194-204`

The `/settings` GET endpoint returns a **hardcoded single source** instead of real data from the DB:

```python
"sources": [
    {
        "id": "src-1",
        "kind": "watch",
        "label": "data/raw",
        "detail": "Local filesystem watch",
        "docCount": db.query(Document).count(),
        "syncedAt": "2h ago",      # ← ALWAYS "2h ago", never a real timestamp
        "status": "ok",            # ← ALWAYS "ok"
    },
],
```

**Impact**: The Document Sources section on Settings always shows exactly one fake entry with a static "2h ago" timestamp. The `syncedAt` and `status` fields are never updated from real sync state. The `docCount` uses a raw `db.query(Document).count()` which is a full-table scan on every settings load — no caching, no pagination.

---

### 2. Settings Source card buttons are dead (no-ops) — `frontend/src/pages/admin/SettingsPage.tsx:641-642`

```tsx
onSync={() => {/* TODO: trigger sync */}}
onRemove={() => {/* TODO: confirm + remove */}}
```

Both Sync and Remove buttons on source cards are non-functional. No corresponding API endpoint exists on the backend either.

---

### 3. "Add source" buttons (S3, Google Drive, Watch folder) are dead — `frontend/src/pages/admin/SettingsPage.tsx:647-655`

Three "Connect another location" buttons do nothing when clicked. No onClick handlers, no API endpoints, no modals.

---

### 4. Feedback detail "trace" grid is entirely mockup data — `frontend/src/pages/admin/FeedbackPage.tsx:157-167`

```tsx
{[
  ["latency",     "—"],    // ← ALWAYS "—"
  ["cache",       "—"],    // ← ALWAYS "—"
  ["model",       "—"],    // ← ALWAYS "—"
  ["k retrieved", "—"],    // ← ALWAYS "—"
].map(([k, v]) => (
```

All four trace fields (latency, cache, model, k retrieved) are hardcoded as "—". The backend `QueryFeedback` model doesn't store any trace metadata at all — only `trace_id`, `session_id`, `rating`, `comment`. There's no backend endpoint to look up trace details by trace_id. The entire "trace" section is decorative.

---

### 5. "Suspected cause" on Feedback detail is static text — `frontend/src/pages/admin/FeedbackPage.tsx:172-185`

Always shows "Review the trace and retrieved chunks above for coverage gaps." — this is not derived from any analysis. It's a placeholder.

---

### 6. Activity page "Retention" sidebar text is hardcoded — `frontend/src/pages/admin/ActivityPage.tsx:121`

```
All audit events retained <b>365 days</b>, then archived to immutable storage.
```

The "365 days" is hardcoded, but the actual configurable retention is `auditRetentionDays` in Settings. Should read from settings like UsersPage does.

---

### 7. Chat suggested prompts are hardcoded — `frontend/src/pages/ChatPage.tsx:18-23`

```tsx
const SUGGESTED = [
  { tag: "Policy",    question: "What is the annual leave entitlement?",         source: "hr_policy.pdf" },
  { tag: "Finance",   question: "Who approves capital expenditure over €50,000?", source: "finance_policy.pdf" },
  { tag: "IT",        question: "What is the minimum password length?",            source: "it_policy.pdf" },
  { tag: "Compliance",question: "What are our data retention obligations?",        source: "compliance_policy.pdf" },
];
```

These are static suggestions that never change. The `source` field is cosmetic — not linked to actual document names.

---

### 8. Login page "All systems operational" is fake — `frontend/src/pages/LoginPage.tsx:73-75`

Hardcoded status indicator with a green dot and "All systems operational" — no health check API call.

---

## 🔴 CRITICAL — Settings API Integration Gaps

### 9. `providerApiKey` bypasses Ollama model validation — `app/api/admin_routes.py:988-1005`

When `providerApiKey` is sent alongside model fields (e.g., `generationModel`), the PATCH handler calls `_validate_ollama_model_exists()` which checks models against the Ollama `/api/tags` endpoint. But if the provider is `openai_compatible`, these models won't be in Ollama, causing a **422 error**. The validation is triggered by the presence of model fields, not by the provider type. **Fix:** skip Ollama model validation when `effective_provider == "openai_compatible"`.

---

### 10. Settings `ollamaModelOptions` includes `visionModel` for chat models — `frontend/src/pages/admin/SettingsPage.tsx:449-457`

```tsx
const ollamaModelOptions = s?.availableModels
    ? Array.from(new Set([
      ...s.availableModels.ollama,
      s.generationModel,
      s.generationFallback,
      s.embeddingModel,
      s.visionModel,    // ← Vision model listed as option for chat model select
    ]))
    : [];
```

This single merged list is used for Generation, Fallback, Embedding, AND OCR model selects. Vision-specific models (like `qwen2.5vl:7b`) appear as options for the generation model, and chat models appear as options for embedding. These should be separate lists.

---

### 11. Backend `/settings` doesn't return `availableModels` for OpenAI-compatible providers — `app/api/admin_routes.py:178`

`availableModels.ollama` always fetches from the Ollama `/api/tags` endpoint. When the provider is `openai_compatible`, the Ollama models list may be empty/irrelevant, and there's no `availableModels.openai_compatible` field. The frontend just uses `ollamaModelOptions` for all model selects regardless of provider type.

---

### 12. Provider test endpoint not called from frontend — `app/api/admin_routes.py:1106-1148`

The backend has `POST /settings/provider/test` for validating provider credentials, but the frontend SettingsPage never calls it. There's no "Test connection" button.

---

### 13. `docCount` in settings sources does full table scan — `app/api/admin_routes.py:200`

`db.query(Document).count()` executes on every GET `/settings` call with no caching. This is a `SELECT COUNT(*) FROM documents` that can be slow with large corpora.

---

## 🟠 HIGH — Logic Errors

### 14. Race condition in Settings save queue — `frontend/src/pages/admin/SettingsPage.tsx:359-392`

The `queueSave` function uses a `saveQueueRef` promise chain but reads `unsavedDiffRef.current` inside the `.then()` callback. If two saves are queued rapidly:

1. First save starts with diff A
2. Second save merges diff B into `unsavedDiffRef` → now contains A+B
3. First save completes, reads `unsavedDiffRef.current` (A+B), sends both A and B
4. Second `.then()` reads `unsavedDiffRef.current` again, which has already been subtracted by step 3

This means the second save may send an empty diff, or the `subtractConfirmedDiff` logic may incorrectly remove pending changes that weren't part of the first request.

---

### 15. `subtractConfirmedDiff` uses shallow equality — `frontend/src/pages/admin/SettingsPage.tsx:285-296`

```tsx
if (remaining[key] === confirmed[key]) {
    delete remaining[key];
}
```

For object values (nested objects like `provider`), `===` comparison always fails for different references, so nested diffs may never be subtracted from the pending queue.

---

### 16. `dailyCeilingUsd` min allows 0 in NumberInput but backend requires ≥ 1 — `frontend/src/pages/admin/SettingsPage.tsx:706`

Frontend: `<NumberInput value={s.cost.dailyCeilingUsd} unit="USD" min={1} max={10000}>`

But the `NumberInput` component's `commit()` function clamps with `Math.min(max ?? next, Math.max(min ?? next, next))` — if `min` is `undefined`, it defaults to `next`, allowing any value. The `min={1}` is correctly passed here, but the `monthlyCeilingUsd` has `min={30}` while the backend also validates `≥ 30`. These are aligned, but the `NumberInput` component doesn't show validation errors — it silently clamps, which could confuse users.

---

### 17. Reindex race condition — double check without lock — `app/api/admin_routes.py:543-572`

The `reindex_document` endpoint checks for active ingestion jobs at line 543-555, then again inside `db.begin()` at line 560-572. Between these two checks, another reindex request could slip through. The outer check is redundant and should be removed, or a proper lock should be used.

---

### 18. Audit log `action_type` mismatch — `app/api/chat_routes.py:73` vs `frontend/src/api/audit.ts:25-31`

The chat route writes `action_type="chat_query"` to the audit log, but the frontend `mapKind()` function only recognizes `"query"`, `"upload"`, `"feedback"`, `"login"`, `"fallback"`. `"chat_query"` falls through to the default `"query"`. This is functionally OK but semantically lossy — the distinction between a chat query and other query types is lost in the UI.

---

## 🟠 HIGH — Data Integrity Risks

### 19. Deactivate user orphans AgentRun records — `app/api/admin_routes.py:721-726`

```python
user_session_ids = [s.id for s in db.query(DbSession).filter(DbSession.user_id == user_id).all()]
if user_session_ids:
    db.query(AgentRun).filter(AgentRun.session_id.in_(user_session_ids)).delete(synchronize_session=False)
```

AgentRun has no FK to sessions, so the delete-by-session-IDs is a manual cascade. But `AgentRun.session_id` is not an indexed column and has no FK constraint, meaning:
- If a session is deleted by other code paths, AgentRuns become orphans
- The `IN` clause could be very large for active users

---

### 20. SemanticCache vector dimension hardcoded to 768 — `app/db/models.py:115`

```python
query_embedding = Column(Vector(768), nullable=False)
```

If the embedding model changes (e.g., to `text-embedding-3-small` with 1536 dimensions), existing cache entries become incompatible and will cause runtime errors. The dimension should be configurable or at least validated against the current model on startup.

---

### 21. No cascade delete from Document to Qdrant points on reindex — `app/api/admin_routes.py:576-582`

If `_delete_qdrant_points` fails, the old points remain in Qdrant while the document is re-ingested, potentially creating duplicate points.

---

### 22. AppConfig `value` column is JSON but no type validation — `app/db/models.py:208`

```python
value = Column(JSON, nullable=False)
```

Any JSON value can be stored. The `upsert_app_config` function writes raw Python values (int, bool, str) which get serialized as JSON. But there's no schema validation on read — `load_app_config` returns raw values that could be of unexpected types if the DB is modified directly.

---

## 🟡 MEDIUM — Security Concerns

### 23. `.env` file committed with real SECRET_KEY — `safe4ai-pilot/.env:6`

```
SECRET_KEY=68d543ad135bb451bf0e0a26a7fa6cf5151cb1d0b0c6b1366d18f5543a93927e
```

The `.env` file contains a real secret key and is in the workspace. While `.gitignore` may exclude it, the file is present and contains production-viable credentials.

---

### 24. Default Postgres credentials in config — `app/config.py:8`

```python
postgres_url: str = "postgresql+psycopg2://safe4ai:safe4ai@localhost:5432/safe4ai"
```

Hardcoded default credentials `safe4ai:safe4ai` — if the environment variable is not set, the app runs with these weak credentials.

---

### 25. `_serialize_settings` leaks `provider_api_key` existence but not value — `app/api/admin_routes.py:158,167`

```python
provider_api_key_raw = _val("provider_api_key", "")
...
"apiKeyConfigured": bool(provider_api_key_raw),
```

The boolean `apiKeyConfigured` leaks whether an API key is configured. While this is intentional for the UI, it's an information disclosure vector.

---

### 26. Test provider endpoint logs API key in error — `app/api/admin_routes.py:1126-1128`

The `test_provider_connection` endpoint sends the API key in an Authorization header via `httpx.Client`. If the request fails and the error message includes the URL or headers, the key could appear in logs. The `except Exception as exc` at line 1135 passes `str(exc)` directly to the HTTPException detail, which could include the key in error responses.

---

### 27. CSRF token only checked on non-GET methods, but SSE stream uses POST — `frontend/src/api/chat.ts:31`

The chat stream POST includes CSRF headers, which is good. However, the `exportAuditCsv` function in `audit.ts:52-53` uses raw `fetch()` without CSRF headers for the CSV download (GET request), which is fine for GET, but the pattern is inconsistent.

---

### 28. `generateTemporaryPassword` has non-uniform distribution — `frontend/src/pages/admin/UsersPage.tsx:46-59`

```tsx
const chars = Array.from(array).map((b) => all[b % all.length]);
```

`b % all.length` introduces modulo bias because `256 % all.length != 0`. For `all.length = 62`, the bias is small but present. The fixed-position overwrites at positions 0-3 help, but the remaining 16 characters are biased.

---

## 🟡 MEDIUM — UI/UX Issues

### 29. Settings left nav doesn't scroll to sections — `frontend/src/pages/admin/SettingsPage.tsx:500-501`

```tsx
href={`#${item.id}`}
onClick={() => setActive(item.id)}
```

Clicking nav items sets `active` state but the `href="#provider"` doesn't actually scroll because React intercepts the click. There's no `scrollIntoView` call. The `scroll-mt-4` class on sections (line 57) suggests scrolling was intended but never implemented.

---

### 30. Settings grid layout breaks on mobile — `frontend/src/pages/admin/SettingsPage.tsx:487`

```tsx
<div className="h-full grid grid-cols-[200px_1fr] bg-paper">
```

The 200px fixed left sidebar doesn't collapse on mobile, making the Settings page unusable on narrow screens.

---

### 31. Feedback page detail has no loading state — `frontend/src/pages/admin/FeedbackPage.tsx:85-196`

When a feedback item is selected, the detail panel shows immediately with all "—" values. There's no loading indicator for fetching trace data (which doesn't exist anyway — see issue #4).

---

### 32. No "Retry" button on settings save failure — `frontend/src/pages/admin/SettingsPage.tsx:715-720`

If the settings API fails after initial load, the user sees the error state. But if they change a setting and the save fails, the optimistic update remains visible. The error banner is good, but there's no "Retry" button.

---

### 33. DocumentsPage `addedBy` always shows "—" — `frontend/src/api/documents.ts:53`

```tsx
addedBy: "—",
```

The backend `/admin/documents` endpoint doesn't return `uploaded_by` user info (only the ID is in the DB), and the frontend mapping just hardcodes "—". The `added by` column header in the table is misleading.

---

## 🟢 LOW — Minor Issues

### 34. Settings version string hardcoded — `frontend/src/pages/admin/SettingsPage.tsx:729`

```tsx
<span>Settings v0.4.18 · loaded from server</span>
```

Hardcoded version string "v0.4.18" that will become stale.

---

### 35. `DEFAULT_PROVIDER` vision model hardcoded — `frontend/src/pages/admin/SettingsPage.tsx:49`

```tsx
visionModel: "qwen2.5vl:7b",
```

This default should come from the backend, not be hardcoded in the frontend.

---

### 36. Chat page loads all documents just to count them — `frontend/src/pages/ChatPage.tsx:33`

```tsx
const { docs } = useDocuments();
```

`useDocuments()` fetches the full document list (with 10-second polling) just to display `totalChunks` and `totalDocs` in the empty state. A lightweight stats endpoint would be more efficient.

---

### 37. Audit export CSV doesn't include CSRF headers — `frontend/src/api/audit.ts:52-53`

```tsx
export const exportAuditCsv = () =>
    fetch(apiUrl("/admin/audit-logs/export.csv"), { credentials: "include" }).then((r) => r.blob());
```

No CSRF token header is sent. While the backend CSRF middleware may only check mutation requests, this is inconsistent with the pattern used elsewhere.

---

### 38. `ollamaModelOptions` used for embedding model select is wrong — `frontend/src/pages/admin/SettingsPage.tsx:587-592`

Chat models and embedding models are fundamentally different, but the same dropdown is used for both. An admin could accidentally set the embedding model to a chat model, which would cause runtime failures during document ingestion.

---

### 39. Double Ollama model validation in PATCH — `app/api/admin_routes.py:989-1005`

When the provider is `openai_compatible`, the backend still validates model names against Ollama's `/api/tags` if `generationModel` etc. are sent. But in openai_compatible mode, models should be validated against the OpenAI-compatible provider's model list, not Ollama's. This causes a **422 error** when trying to set models in openai_compatible mode.

---

## Summary

| Priority | Count | Key Themes |
|----------|-------|------------|
| 🔴 Critical | 13 | Mockup data in Settings sources, Feedback traces; dead buttons; Ollama validation blocks openai_compatible |
| 🟠 High | 9 | Settings save race condition; shallow diff comparison; orphaned AgentRuns; hardcoded vector dims |
| 🟡 Medium | 11 | Security: key leakage, modulo bias; UX: no scroll, broken mobile, no retry, misleading columns |
| 🟢 Low | 6 | Hardcoded strings; inefficient queries; same model dropdown for all selects |
| **Total** | **39** | |

## Round 7 — Fixed (2026-05-18, review follow-up 2026-05-19)

| # | Status | Notes |
|---|--------|-------|
| 1 | ✅ Fixed | `syncedAt: "2h ago"` → `null`; `docCount` moved to TTL cache |
| 2 | ✅ Fixed | Dead Sync/Remove buttons removed from SourceCard |
| 3 | ✅ Fixed | Dead "Add source" footer section removed |
| 4 | ✅ Fixed | Fake trace grid replaced with "Trace detail not recorded" message |
| 5 | ✅ Fixed | Fake "Suspected cause" section removed |
| 6 | ✅ Fixed | Activity page now reads `auditRetentionDays` from settings API |
| 7 | ✅ Fixed | Fake `source` filenames removed from SUGGESTED prompts |
| 8 | ✅ Fixed | Login page "All systems operational" now calls `/health` API |
| 9 | ✅ Fixed | Ollama model validation skipped when `openai_compatible` is active |
| 10 | ✅ Fixed | Separate `chatModelOptions`, `embeddingModelOptions`, `visionModelOptions` |
| 11 | ✅ Fixed | Backend fetches & caches `/models` from openai_compatible provider; returned as `availableModels.provider` |
| 12 | ✅ Fixed | "Test connection" button added to Provider section; calls `POST /settings/provider/test` |
| 13 | ✅ Fixed | `docCount` moved to TTL cache — no longer a per-request full scan |
| 14 | ✅ Fixed | Save queue snapshots and clears `unsavedDiffRef` before mutation; failed diffs restored for retry |
| 15 | ✅ Fixed | `subtractConfirmedDiff` now uses `JSON.stringify` deep equality |
| 16 | ✅ Fixed | `NumberInput.commit()` now always syncs draft to clamped value so displayed value matches applied value |
| 17 | ✅ Fixed | Redundant outer reindex check removed; inner locked check is authoritative |
| 18 | ✅ Fixed | `action_type="chat_query"` → `"query"` in audit log |
| 19 | ✅ Fixed | `_ensure_agentrun_fk()` at startup: prunes orphans + adds `agent_runs_session_fkey` FK with ON DELETE CASCADE |
| 20 | ✅ Fixed | `_ensure_semantic_cache_dimension()` warns at startup if embedding model dimension ≠ 768 |
| 21 | ✅ Fixed | Qdrant delete failure now aborts reindex with 502 before DB chunk deletion or ingestion scheduling; this prevents stale vectors from remaining searchable beside newly indexed chunks |
| 22 | ✅ Fixed | `load_app_config` coerces known keys to declared types, with explicit boolean string parsing for `"false"`, `"0"`, `"off"`, `"true"`, `"1"`, `"on"` |
| 23 | ✅ Fixed | `_warn_default_credentials()` at startup logs warning if default SECRET_KEY is in use |
| 24 | ✅ Fixed | `_warn_default_credentials()` at startup logs warning if default Postgres credentials are in use |
| 25 | ✅ Not a Bug | `apiKeyConfigured` boolean is intentional — it's the safest way to tell the UI a key is set |
| 26 | ✅ Fixed | `test_provider_connection` catches `httpx.HTTPError` and generic exceptions; returns sanitized message |
| 27 | ✅ Not a Bug | Audit CSV uses GET — CSRF not required for GETs per HTTP spec |
| 28 | ✅ Fixed | `generateTemporaryPassword` rewritten with rejection-sampling + Fisher-Yates |
| 29 | ✅ Fixed | Settings nav onClick now calls `scrollIntoView` |
| 30 | ✅ Fixed | Settings grid is now responsive (`flex-col` on mobile, `grid` on md+) |
| 31 | ✅ Fixed | Trace section now shows honest "not recorded" message — no loading state needed |
| 32 | ✅ Fixed | Retry button added to save error banner |
| 33 | ✅ Fixed | `addedBy` now populated from `uploaded_by_email` join |
| 34 | ✅ Fixed | Hardcoded "v0.4.18" version string removed |
| 35 | ✅ Fixed | `DEFAULT_PROVIDER.visionModel` changed to `""` — actual value always comes from server |
| 36 | ✅ Fixed | `GET /admin/corpus-stats` endpoint added; ChatPage uses it instead of loading all documents |
| 37 | ✅ Not a Bug | Audit CSV GET without CSRF is correct per HTTP spec |
| 38 | ✅ Fixed | Same as #10 — model dropdowns are now split by type |
| 39 | ✅ Fixed | Same as #9 — Ollama validation skipped for openai_compatible |

**All 39 issues resolved** (37 Fixed + 2 Not a Bug)

## Review Follow-up Verification (2026-05-19)

| Review item | Status | Evidence |
|-------------|--------|----------|
| P1 — reindex must not continue after Qdrant delete failure | ✅ Fixed | `tests/test_admin.py::TestDocumentReindex::test_reindex_qdrant_failure_does_not_delete_db_chunks_or_schedule` verifies 502 response, no DB chunk delete, no ingestion scheduling, and failed document status |
| P2 — boolean config strings must not use Python truthiness | ✅ Fixed | `tests/test_models.py::test_load_app_config_coerces_boolean_strings_explicitly` verifies `"false"`, `"0"`, and `"off"` load as `False` |

Fresh local verification:

- Backend: `.venv/bin/pytest -q` → `231 passed, 6 skipped`
- Changed-area backend: `.venv/bin/pytest tests/test_admin.py tests/test_models.py -q` → `58 passed`
- Frontend: `npm run build` → successful production build
