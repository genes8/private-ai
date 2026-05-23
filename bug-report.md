# Bug Hunting & E2E API Verification — safe4ai-pilot/ (2026-05-23)

Full static analysis of every frontend API call mapped against every backend endpoint. Focus: identify mock/disconnected data, verify all admin panel tabs, and find calls that display data not actually connected to the backend.

## Verification Status — 2026-05-23

**Overall status: not clean.** Frontend build passes, but the backend test suite currently fails.

| Check | Result | Evidence |
|-------|--------|----------|
| Frontend production build | ✅ Pass | `npm run build` in `safe4ai-pilot/frontend` completed successfully |
| Backend tests | ❌ Fail | `./.venv/bin/pytest -q` in `safe4ai-pilot` → `326 passed, 6 skipped, 5 failed` |

Backend failures are all in `tests/test_startup_schema.py`. The tests patch `app.startup_migrations.load_runtime_config`, but `app/startup_migrations.py` currently imports `load_runtime_config` inside `_ensure_qdrant_collection()` instead of exposing it at module scope. Result: every Qdrant collection dimension test fails before it can exercise behavior.

This is a separate regression from the API/mock-data findings below and must be fixed before claiming the codebase is fully verified.

## Frontend-to-Backend API Map — Complete Verification

| Frontend Call | Backend Endpoint | Connected? | Notes |
|---------------|-----------------|------------|-------|
| `GET /auth/csrf` | `auth/router.py:55` | ✅ Live | |
| `POST /auth/login` | `auth/router.py:70` | ✅ Live | |
| `POST /auth/logout` | `auth/router.py:151` | ✅ Live | |
| `GET /me` | `admin_routes.py:841` | ✅ Live | |
| `GET /health` | `main.py:385` | ✅ Live | Used by LoginPage health check |
| `GET /admin/stats` | `admin_routes.py:719` | ✅ Live | |
| `GET /admin/documents` | `admin_routes.py:250` | ✅ Live | Includes `uploaded_by_email` join |
| `GET /admin/documents/{id}/status` | `admin_routes.py:287` | ✅ Live | |
| `POST /admin/documents/upload` | `admin_routes.py:172` | ✅ Live | |
| `DELETE /admin/documents/{id}` | `admin_routes.py:314` | ✅ Live | |
| `POST /admin/documents/{id}/reindex` | `admin_routes.py:368` | ✅ Live | |
| `GET /admin/corpus-stats` | `admin_routes.py:237` | ✅ Live | Used by ChatPage empty state |
| `GET /admin/audit-logs` | `admin_routes.py:613` | ✅ Live | |
| `GET /admin/audit-logs/export.csv` | `admin_routes.py:653` | ✅ Live | |
| `GET /admin/feedback` | `observability_routes.py:41` | ✅ Live | Returns `user_email` via join |
| `POST /feedback` | `observability_routes.py:27` | ✅ Live | |
| `GET /admin/users` | `admin_routes.py:491` | ✅ Live | |
| `POST /admin/users` | `admin_routes.py:517` | ✅ Live | |
| `DELETE /admin/users/{id}` | `admin_routes.py:542` | ✅ Live | |
| `GET /settings` | `settings_routes.py:311` | ✅ Live | |
| `PATCH /settings` | `settings_routes.py:322` | ✅ Live | |
| `POST /settings/provider/test` | `settings_routes.py:606` | ✅ Live | |
| `POST /chat/stream` | `chat_routes.py:346` | ✅ Live | SSE streaming |
| `GET /admin/stats/cost` | `observability_routes.py:53` | ⚠️ No frontend | |

**Result: All 23 frontend API calls found in `frontend/src` are connected to real backend endpoints.** `GET /admin/stats/cost` is a backend endpoint with no frontend consumer, so it is not counted as a frontend API call. Zero frontend API calls found in the API adapters use mock/fake data as their data source.

---

## Backend Endpoints With No Frontend Consumer

| Endpoint | File | Notes |
|----------|------|-------|
| `POST /chat` (non-streaming) | `chat_routes.py:269` | No frontend code calls this — all chat uses SSE streaming |
| `GET /admin/stats/cost` | `observability_routes.py:53` | Detailed cost breakdown not shown in UI |
| `GET /admin/review-queue` | `admin_routes.py:770` | Human review queue has no admin UI |
| `POST /admin/review-queue/{id}/approve` | `admin_routes.py:800` | No admin UI for review actions |
| `POST /admin/review-queue/{id}/reject` | `admin_routes.py:818` | No admin UI for review actions |

---

## 🔴 CRITICAL — Static/Hardcoded Data Still Reaching Users

### 1. "Indexing healthy" card in admin sidebar is completely fake — `frontend/src/pages/admin/AdminLayout.tsx:76-82`

```tsx
<div className="mx-2 mb-3 rounded-lg bg-paper-2 border border-line px-3 py-2.5">
  <div className="flex items-center gap-2 mb-1">
    <span className="w-1.5 h-1.5 rounded-full bg-success shrink-0" />
    <span className="text-[11.5px] font-medium text-text-2">Indexing healthy</span>
  </div>
  <p className="text-[10.5px] text-text-mute">All documents indexed</p>
</div>
```

**No API call. No query.** Always shows green dot + "Indexing healthy" + "All documents indexed". Should query for documents with `failed` or `embedding` status and show actual indexing health. If a document ingestion is failing, the admin sees a green "healthy" indicator — misleading.

**Fix:** Add a query to check for documents with `ingestion_status IN ('failed', 'embedding', 'queued')` and render the card dynamically.

---

### 2. Settings "Document sources" section renders hardcoded single source — `app/api/settings_routes.py:186-196`

```python
"sources": [
    {
        "id": "src-1",
        "kind": "watch",
        "label": "data/raw",
        "detail": "Local filesystem watch",
        "docCount": doc_count,
        "syncedAt": None,
        "status": "ok",
    },
],
```

This is **always a single hardcoded source**. There's no database table for sources, no CRUD operations, no way to add/remove sources from the UI. The `docCount` is live (from TTL cache), but the source itself is static. The frontend `SourceCard` component (`SettingsPage.tsx:182-208`) renders it as if it's a dynamic data source with real status indicators.

The `SourceCard` component also has icons for `s3`, `gdrive`, and `watch` kinds — but only `watch` is ever returned, making the S3/Google Drive icon logic dead code.

**Fix options:**
- A) Remove the Sources section entirely from Settings (it's decorative)
- B) Create a proper `data_sources` DB table with CRUD endpoints and wire the frontend to it
- C) Mark it clearly as "Local filesystem" info (not a configurable source) with a different UI treatment

---

### 3. Reranker model list is hardcoded — `app/api/settings_routes.py:170-173`

```python
"reranker": [
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "bge-reranker-v2",
],
```

Unlike Ollama models (fetched dynamically via `/api/tags`) and provider models (fetched dynamically via `/models`), the reranker model dropdown is two hardcoded strings. There's no check whether these models are actually available/installed on the server.

**Fix:** Either fetch available reranker models dynamically from the server, or mark the list as "available options" rather than "installed models".

---

### 4. Chat suggested prompts are static — `frontend/src/pages/ChatPage.tsx:19-24`

```tsx
const SUGGESTED = [
  { tag: "Policy",    question: "What is the annual leave entitlement?" },
  { tag: "Finance",   question: "Who approves capital expenditure over €50,000?" },
  { tag: "IT",        question: "What is the minimum password length?" },
  { tag: "Compliance",question: "What are our data retention obligations?" },
];
```

These are hardcoded static suggestions that never change regardless of what documents are indexed. The previous `source` fake filenames were removed (good), but the questions themselves are still static and may be irrelevant if no HR/finance/IT/compliance documents exist.

**Note:** Severity downgraded from Critical — this is a UX concern, not a data integrity issue.

---

## 🟠 HIGH — Logic/UX Issues

### 5. `SSE completion mode` field is misplaced in Provider section — `frontend/src/components/admin/ProviderSettingsSection.tsx:329-334`

The `sseDoneMode` selector (`strict` / `async`) is rendered inside the Provider section, but this is a backend streaming behavior setting, not an inference provider setting. It appears under every provider mode (local, hybrid, cloud). It does save correctly to the backend, but it's conceptually confusing — users looking at "Inference provider" settings don't expect to find SSE streaming configuration there.

**Fix:** Move `sseDoneMode` to a more appropriate section (e.g., "Retrieval" or a new "Advanced" section).

---

### 6. Feedback detail "Trace" section shows "not recorded" — `frontend/src/pages/admin/FeedbackPage.tsx:153-158`

```tsx
<p className="text-[12px] text-text-3 font-mono">
  Trace detail is not recorded. Use the trace ID below to correlate with server logs.
</p>
```

The old fake trace grid was correctly replaced with an honest message. However, the backend `QueryFeedback` model stores `trace_id` and `session_id` — both could be used to look up the `AuditLog` entry which does have `latency_ms`, `model_used`, etc. The trace detail is not technically "not recorded" — it's in the audit_logs table, just not fetched/displayed.

**Fix:** Add a backend endpoint `GET /admin/feedback/{id}/trace` that looks up the audit log by trace_id and returns latency, model, cache status. Wire the FeedbackPage to display this data.

---

### 7. Settings nav `scrollIntoView` works but `setActive` can desync — `frontend/src/pages/admin/SettingsPage.tsx:456-459`

```tsx
onClick={(e) => {
  e.preventDefault();
  setActive(item.id);
  document.getElementById(item.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}}
```

Clicking a nav item sets `active` state AND scrolls. But if the user manually scrolls, `active` doesn't update to reflect which section is visible. The left nav highlight stays on the last-clicked section regardless of scroll position.

**Fix:** Add an `IntersectionObserver` to track which section is visible and update `active` accordingly.

---

### 8. AdminLayout fetches feedback on every page load — `frontend/src/pages/admin/AdminLayout.tsx:28-33`

```tsx
const { data: feedbackItems = [] } = useQuery({
  queryKey: ["feedback"],
  queryFn: listFeedback,
  refetchInterval: 60_000,
  staleTime: 30_000,
});
```

Every admin page wrapped in `AdminLayout` fetches the full feedback list just to show a negative feedback count badge on the sidebar. This is redundant when the user is on the Feedback page itself (which has its own query). Should share cache or use a lightweight count endpoint.

**Severity:** Low — React Query deduplicates by queryKey, so it's not a real duplicate request, just unnecessary refetching.

---

## 🟡 MEDIUM — Minor Issues

### 9. Backend Qdrant startup schema tests are failing — `tests/test_startup_schema.py:49`

`./.venv/bin/pytest -q` currently fails 5 tests:

- `test_text_embedding_3_small_creates_1536_dim_collection`
- `test_text_embedding_3_large_creates_3072_dim_collection`
- `test_nomic_embed_text_creates_768_dim_collection`
- `test_unknown_model_falls_back_to_768`
- `test_dimension_mismatch_raises_on_existing_collection`

All fail with:

```text
AttributeError: <module 'app.startup_migrations' ...> does not have the attribute 'load_runtime_config'
```

The implementation imports `load_runtime_config` locally inside `_ensure_qdrant_collection()`, while tests patch it at module scope. Either expose `load_runtime_config` at module scope and reuse it, or update tests to patch the canonical import path used by the function. From a maintainability perspective, module-scope dependency imports are cleaner here because they make the startup migration dependency graph explicit and easier to test.

---

### 10. Backend `POST /chat` (non-streaming) has no frontend consumer — `app/api/chat_routes.py:269`

The non-streaming chat endpoint exists but is never called from the frontend. Could be removed or kept for API-only consumers.

---

### 11. Review Queue has no admin UI — `app/api/admin_routes.py:770-833`

Three endpoints exist for the human review queue (`list`, `approve`, `reject`) but there's no admin page or component that uses them. This is a complete backend feature with no frontend surface.

---

### 12. `GET /admin/stats/cost` not used by frontend — `app/api/observability_routes.py:53`

A dedicated cost stats endpoint exists but the frontend gets cost data from the general `/admin/stats` endpoint and the Settings API (`cost.todayUsd`). This endpoint is unused.

---

## Previously Fixed Issues (from Round 7, verified still fixed)

| # | Issue | Verification |
|---|-------|-------------|
| Old #1 | `syncedAt: "2h ago"` in sources | ✅ Now returns `None` |
| Old #2 | Dead Sync/Remove buttons on SourceCard | ✅ Buttons removed |
| Old #3 | Dead "Add source" buttons | ✅ Section removed |
| Old #4 | Fake trace grid in Feedback | ✅ Replaced with honest message |
| Old #5 | Fake "Suspected cause" in Feedback | ✅ Section removed |
| Old #6 | Activity page hardcoded retention | ✅ Reads from settings API |
| Old #7 | Fake `source` filenames in SUGGESTED | ✅ `source` field removed |
| Old #8 | Login page fake health check | ✅ Calls `/health` API |
| Old #9 | Ollama validation blocks openai_compatible | ✅ Validation skipped correctly |
| Old #10 | Single model dropdown for all types | ✅ Separate dropdowns per model type |
| Old #11 | No provider model list | ✅ Fetches from `/models` endpoint |
| Old #12 | No "Test connection" button | ✅ Button added, calls API |
| Old #33 | `addedBy` always "—" | ✅ Backend returns `uploaded_by_email` |

---

## Summary

| Priority | Count | Key Themes |
|----------|-------|------------|
| 🔴 Critical | 3 | Admin sidebar "Indexing healthy" is fake; Settings sources still hardcoded; Reranker list hardcoded |
| 🟠 High | 5 | SSE mode misplaced; Feedback trace could be fetched; Settings nav scroll desync; Feedback query on every admin page; Chat suggestions static |
| 🟡 Medium | 4 | Failing startup schema tests; unused backend endpoints (non-streaming chat, review queue, cost stats) |
| **Total** | **12** | Down from 39 in Round 7, but backend verification is not clean |

### What's Actually Working

All 23 frontend API calls found in `frontend/src` are connected to real backend endpoints. Every admin panel tab (Overview, Documents, Activity, Feedback, Users, Settings) fetches live data from the backend. The main remaining issues are:

1. **Static decorative elements** that look dynamic (indexing health card, sources section)
2. **Hardcoded model lists** (reranker)
3. **Unused backend features** (review queue, cost stats, non-streaming chat)
4. **Backend regression test failure** in startup Qdrant collection dimension tests
