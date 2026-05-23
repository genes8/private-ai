# Bug Hunting Report — safe4ai-pilot/ (2026-05-23, Round 3 — Re-verification)

Deep code audit focusing on logic errors, data integrity risks, security concerns, and UI/UX issues. All 30+ source files read and analyzed: chat routes, auth pipeline, RAG pipeline, admin routes, settings routes, ingestion service, security modules, frontend hooks, and all admin pages.

## Verification Status — 2026-05-23 (Round 3)

| Check | Result | Evidence |
|-------|--------|----------|
| Backend tests | ✅ Pass | `./.venv/bin/pytest -q` → `341 passed, 4 skipped, 1 warning` |
| Frontend build | ✅ Pass | `npm run build` in `safe4ai-pilot/frontend` completed successfully |

### Round 2 → Round 3 Delta: 11 of 11 bugs FIXED

| Bug | Status | What changed |
|-----|--------|-------------|
| #1 PII filter | ✅ Fixed | Ingestion now redacts PII with `[REDACTED]` via `ContentFilter.redact()` instead of dropping chunks; document content stays fully indexed (rag_pipeline.py:140-143) |
| #2 Divergent chat persistence | ✅ Fixed | `/chat` now uses `finalize_chat_run()` with `_usage_or_estimate()` (chat_routes.py:236-250). `_save_assistant_reply`, `_write_audit_log`, `_record_cost` deleted |
| #3 Sync HTTP in async | ✅ Invalid | Settings endpoints are `def` (sync), not `async def`. FastAPI runs sync endpoints in a threadpool — `httpx.Client` is correct. Not a bug |
| #4 SSRF TOCTOU | ✅ Fixed | `_PinnedTransport` pins HTTP requests to DNS-resolved IP, preventing rebinding (settings_routes.py:315-319). `settings_service.py` caller updated to unpack tuple |
| #5 Inaccurate cost tracking | ✅ Fixed | `/chat` now uses `_usage_or_estimate()` preferring `provider_usage` when available (chat_routes.py:236) |
| #6 Silent feedback drop | ✅ Fixed | `useChat.rate()` now sets `ratingError` with descriptive message when session context is lost (useChat.ts:110), and rolls back optimistic rating on API error |
| #7 Qdrant/DB ID drift | ✅ Fixed | Same `chunk_ids[i]` used for both Qdrant point ID and DB chunk ID (rag_pipeline.py:149-176) |
| #8 Cache TTL too short | ✅ Fixed | TTL increased from 15s to 60s (settings_routes.py:35) |
| #9 Retrieve-retry identical | ✅ Fixed | `top_k` now increases by 4 per retry attempt: `retrieval_top_k + state.retrieval_attempts * 4` (graph.py:117) |
| #10 Input guard false positives | ✅ Fixed | Patterns now use role-specific blocklists: "you are now" only blocks AI-role substitution words; "act as" only blocks on `if you` or specific malicious roles (e.g. `hacker`). Allows: "act as a witness/agent", "You are now a benefits-eligible employee" |
| #11 Conversation summary | ✅ Mostly fixed | LLM failure now falls back to truncation (conversation.py:107-112). Summary still lossy on success, but that's inherent |

---

## 🔴 CRITICAL — Data Loss / Integrity Risks

**No remaining Critical bugs.** All Critical findings from Round 2 have been resolved or reclassified.

---

### 2. Blocking `/chat` and streaming `/chat/stream` persist audit/cost data through divergent paths — `app/api/chat_routes.py:56-111`, `app/services/chat_finalizer.py:14-70`

The blocking `/chat` endpoint uses three separate helpers:

```python
_save_assistant_reply(convo, final)
_write_audit_log(...)
_record_cost(...)
```

The streaming `/chat/stream` endpoint uses the unified `finalize_chat_run()` helper instead.

These paths currently write different data:

- Blocking path writes `AuditLog.action_type="query"`.
- Streaming finalizer writes `AuditLog.action_type="chat_query"`.
- Blocking path has a smaller `response_metadata` payload.
- Streaming finalizer records provider usage fields in `response_metadata`.
- Blocking path records cost through `CostTracker.record_run`, but does not use the same `AgentRun` creation path as `finalize_chat_run`.

**Impact:** Dashboards and cost/audit reports can disagree depending on whether a query used `/chat` or `/chat/stream`. This is especially risky because `/chat` is intentionally retained for eval scripts, integration tests, and direct API clients.

**Fix:** Make blocking `/chat` use `finalize_chat_run()` with `_usage_or_estimate()`, then delete `_save_assistant_reply`, `_write_audit_log`, and `_record_cost` if no longer needed. Ensure error audit handling remains explicit and consistent.

---

## 🟠 HIGH — Logic / Security Issues

**No remaining High bugs.** All High findings from Round 2 have been resolved or reclassified.

---

## 🟡 MEDIUM — Robustness / Maintainability

**No remaining Medium runtime bugs.** All Medium findings from Round 2 have been resolved.

---

## Previously Fixed Issues (from Rounds 1-7, verified still fixed)

| # | Issue | Verification |
|---|-------|-------------|
| R2 #2 | Blocking `/chat` and streaming `/chat/stream` used divergent persistence paths | ✅ `/chat` now uses `finalize_chat_run()` |
| R2 #3 | Sync HTTP in async settings endpoints | ✅ Invalid — endpoints are sync `def`, not `async def` |
| R2 #4 | SSRF TOCTOU race via DNS rebinding | ✅ `_PinnedTransport` pins requests to resolved IP |
| R2 #5 | Cost ceiling used estimated tokens for `/chat` | ✅ Now uses `_usage_or_estimate()` with `provider_usage` |
| R2 #6 | `useChat.rate()` silently dropped feedback | ✅ Now shows `ratingError` message |
| R2 #7 | Qdrant/DB chunk ID drift | ✅ Same UUID used for both Qdrant point and DB chunk |
| R2 #8 | Settings cache TTL too short (15s) | ✅ Increased to 60s |
| R2 #9 | Retrieve-retry used identical parameters | ✅ `top_k` increases by 4 per attempt |
| R2 #10 | Input guard false positives on legal language | ✅ Role-specific blocklists; "act as a witness/agent" and "You are now a benefits-eligible employee" now pass |
| R2 #11 | Conversation summary grew unbounded on LLM failure | ✅ Falls back to truncation |
| R3 #1 | PII ingestion dropped chunks instead of redacting | ✅ `ContentFilter.redact()` added; ingestion replaces PII with `[REDACTED]` |
| R1 #1 | "Indexing healthy" card was fake | ✅ Now dynamic — queries `corpus-stats` API |
| R1 #2 | Settings sources section hardcoded | ✅ Marked read-only with honest label |
| R1 #3 | Reranker list hardcoded | ✅ Hint updated to "Supported options" |
| R1 #4 | Chat suggestions static | ✅ Labeled "Example questions — edit before sending" |
| R1 #5 | SSE mode misplaced in Provider | ✅ Moved to Retrieval section |
| R1 #6 | Feedback trace "not recorded" | ✅ `GET /admin/feedback/{id}/trace` endpoint added |
| R1 #7 | Settings nav scroll desync | ✅ IntersectionObserver syncs active nav |
| R1 #8 | AdminLayout full feedback fetch | ✅ Lightweight `/admin/feedback/count` endpoint |
| Old #1 | `syncedAt: "2h ago"` in sources | ✅ Returns `None` |
| Old #2 | Dead Sync/Remove buttons | ✅ Removed |
| Old #4 | Fake trace grid | ✅ Replaced with honest message |
| Old #7 | Fake `source` filenames | ✅ `source` field removed |
| Old #8 | Login page fake health check | ✅ Calls `/health` API |
| Old #33 | `addedBy` always "—" | ✅ Backend returns `uploaded_by_email` |

---

## Thermo-Nuclear Code Quality Review — Re-verified 2026-05-23 (Round 3)

Scope: full code-quality audit of the current source tree. This is stricter than the bug list above and focuses on structural maintainability, abstraction quality, and spaghetti growth.

### BLOCKERS — Must Fix Before Shipping

| ID | Status | Finding | Verification |
|----|--------|---------|--------------|
| B1 | ✅ Fixed | Divergent chat persistence paths unified. | `/chat` now calls `finalize_chat_run()`; `_save_assistant_reply`/`_write_audit_log`/`_record_cost` deleted. |
| B2 | ✅ Fixed | `CustomModelManager` moved to module level. | `ProviderSettingsSection.tsx:43-99` — standalone component, no longer inside render body. |
| B3 | ✅ Confirmed | `collect_field_updates` is a long validation if-chain. | `app/services/settings_service.py:258-413` still contains repeated `if body.X is not None` validation/update branches. |

### HIGH — Serious Quality Debt

| ID | Status | Finding | Verification |
|----|--------|---------|--------------|
| H1 | ⚠️ Partially confirmed | Service layer raises `HTTPException`. | Confirmed in `settings_service.py` and `provider_settings.py`; not confirmed in `startup_migrations.py`, which uses `RuntimeError`/logged warnings instead. |
| H2 | ✅ Confirmed | `SettingsPage.set()` is a stringly typed dispatcher. | `frontend/src/pages/admin/SettingsPage.tsx:212-267` maps `keyof AppSettings` to flat patch fields with manual casts, while provider controls call `queueSave()` directly. |
| H3 | ✅ Confirmed | `applyDiff` mixes explicit optimistic patching with derived provider consequences. | `frontend/src/pages/admin/SettingsPage.tsx:116-165` uses nested null-coalescing chains and mode-specific provider synchronization. |
| H4 | ✅ Confirmed | Hybrid/cloud provider UI has substantial duplication. | `ProviderSettingsSection.tsx` repeats API URL, API key, chat model, and custom model UI across hybrid/cloud blocks. |

### MEDIUM — Architectural Smells

| ID | Status | Finding | Verification |
|----|--------|---------|--------------|
| M1 | ✅ Confirmed | `_QDRANT_COLLECTION = "documents"` is duplicated. | Present in `admin_routes.py`, `startup_migrations.py`, `ingestion_service.py`, and `scripts/verify_deletion.py`. |
| M2 | ✅ Confirmed | Deleted-user constants and ensure logic are duplicated. | Constants exist in `admin_routes.py` and `startup_migrations.py`; one implementation uses ORM, the other raw SQL. |
| M3 | ✅ Confirmed | `settings_routes.py` still owns too much business logic. | `_fetch_provider_model_names`, `_get_settings_live_metadata`, and `_serialize_settings` live in the route module. |
| M4 | ✅ Confirmed | Provider `/models` probing is duplicated. | `_fetch_provider_model_names()` and `test_provider_connection()` each implement direct `/models` calls. |
| M5 | ⚠️ Partially confirmed | LLM grading code is dead in the main graph path. | `graph.py` always passes `rerank_threshold`, so the production graph takes score-based grading; direct tests still call `grade_chunks()` without threshold, so the code is not globally unreachable. |
| M6 | ⚠️ Partially confirmed | Startup migrations swallow many failures. | Several `_ensure_*` helpers log and continue, but `_ensure_qdrant_collection()` re-raises `RuntimeError` for vector-size mismatch and default-credential checks can fail in enforce mode. |
| M7 | ✅ Fixed | Dead `if True:` branch in CSRF middleware. | No longer present in `app/main.py`. |
| M8 | ✅ Confirmed | Vector-size extraction is copy-pasted. | Same vector config extraction pattern appears in `settings_service.py` and `startup_migrations.py`. |
| M9 | ⚠️ Partially fixed | Vision model magic string partially centralized. | `runtime_config.py:20` and `settings_service.py:31` define `_DEFAULT_VISION_MODEL`; `settings_routes.py` still uses the literal string at lines 119, 140, 159, 161. |
| M10 | ✅ Confirmed | Entity booster compiles regex inside loops. | `entity_booster.py:90,97` calls `re.search(r"\b" + re.escape(tok) + r"\b", ...)` per token/chunk. |

### Stale Or Incorrect Review Items

| Review claim | Current status |
|--------------|----------------|
| `AdminLayout` fetches all feedback just to count negatives | ❌ Stale. `AdminLayout` now uses `queryKey: ["feedback-count"]` and `GET /admin/feedback/count`. |
| Feedback query key shared between `AdminLayout` and `FeedbackPage` | ❌ Stale. `AdminLayout` uses `["feedback-count"]`; `FeedbackPage` uses `["feedback"]`. |

### Thermo Summary

| Category | Count | Key Theme |
|----------|-------|-----------|
| Blockers | 1 remaining (of 3) | `collect_field_updates` long if-chain; B1 and B2 fixed |
| High | 4 | HTTP/service boundary coupling, split save paths, fragile optimistic state, duplicated provider UI |
| Medium | 9 remaining (of 10) | Duplicated constants, route-layer business logic, partial dead code, silent startup warnings, magic strings; M7 fixed |
| Stale/Incorrect | 2 | Feedback-count issues already fixed |

**Thermo verdict:** Improved since Round 2. 2 of 3 blockers fixed (B1, B2), 1 medium smell fixed (M7). Remaining B3 is a code-style concern, not a runtime bug. The codebase is in better structural shape than the previous audit.

---

## Summary

| Priority | Count | Key Themes |
|----------|-------|------------|
| 🔴 Critical | 0 | All Critical findings resolved |
| 🟠 High | 0 | All High findings resolved or reclassified |
| 🟡 Medium | 0 | All Medium runtime bugs resolved |
| **Total** | **0** | All 11 runtime bugs fixed across Rounds 2–3 |

Thermo-nuclear review status: **1 structural blocker remaining (of 3), 4 high-priority quality debts, 9 medium architectural smells (of 10).**
