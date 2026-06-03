# Bug Hunting Report — safe4ai-pilot/ (2026-06-02, Round 5 + Review Follow-up Fixed)

Full-stack bugfix pass for the Round 4 report. The 30 Round 4 findings were
re-checked against current source, fixed where they were real defects, or marked
as already-fixed / invalid where current evidence contradicted the old report.

## Verification Status — 2026-06-02 Round 5

| Check | Result | Evidence |
|---|---:|---|
| Backend tests | ✅ Pass | `.venv/bin/pytest tests/ -q` → `407 passed, 6 skipped, 1 warning` |
| Review follow-up tests | ✅ Pass | `.venv/bin/pytest tests/test_runtime_config.py tests/test_health.py tests/test_oidc.py tests/test_admin.py::TestSettings::test_patch_settings_persists_oidc_config tests/test_admin.py::TestSettings::test_fetch_provider_model_names_validates_stored_url` → pass |
| Frontend build | ✅ Pass | `npm run build` in `safe4ai-pilot/frontend` completed successfully |
| Diff whitespace | ✅ Pass | `git diff --check` clean for touched files |

Review follow-up status: complete. The two remaining review blockers are closed:
legacy OpenAI-compatible provider configs are lazy-resolved into pinned runtime
clients, and the `/health` provider `/models` check now uses the same pinned
transport path when a resolved provider IP is available.

Known residual warning: Qdrant client compatibility warning when no local Qdrant
server version can be read during mocked settings tests.

## Round 4 Findings — Resolution

| # | Status | Resolution evidence |
|---:|---|---|
| 1 | ✅ Already fixed | `provider_api_key` is in `_SENSITIVE_KEYS`; `upsert_app_config` encrypts it and `load_app_config` decrypts it. Added regression test `test_upsert_app_config_encrypts_provider_api_key`. |
| 2 | ✅ Fixed | `/chat/stream` async postprocessing now runs sync DB finalization through `asyncio.to_thread(...)` before scheduling with `create_task`. Covered by `test_chat_stream_async_finalization_uses_thread`. |
| 3 | ✅ Fixed | `_fetch_provider_model_names()`, provider connection tests, cloud embedding probes, and OpenAI-compatible runtime clients now validate and pin provider outbound connections. Covered by `test_fetch_provider_model_names_validates_stored_url`, `test_runtime_config_loads_provider_resolved_ip`, and `test_build_provider_pins_openai_compatible_transport`. |
| 4 | ✅ Clarified | Foreign sessions still return `404` intentionally, matching missing-session behavior. Added code comment so this remains an explicit anti-enumeration choice. Existing `test_chat_rejects_session_owned_by_another_user` covers it. |
| 5 | ✅ Fixed | `readStreamChunks()` is iterative, not recursive, and stream read errors become frontend error events. |
| 6 | ✅ Fixed | `useSettings` no longer re-applies a rejected optimistic diff after server rejection; it invalidates and lets server state win. |
| 7 | ✅ Fixed | `useSettings.set()` now supports top-level `embeddingSource` and emits `diff.embeddingSource`. TypeScript build verifies the contract. |
| 8 | ✅ Fixed | Ingestion tasks are tracked by `doc_id`; document delete cancels a registered active task before deletion. Covered by `test_delete_document_cancels_registered_ingestion_task`. |
| 9 | ✅ Fixed | `formatBytes(0)` now returns `0.0 B`; only negative/null/undefined values render as `—`. |
| 10 | ✅ Fixed | Unknown audit action types no longer map to `query`; frontend has `admin` and `other` kinds and backend returns `user_email` for display. Covered by `test_list_audit_logs_returns_user_email_for_display`. |
| 11 | ✅ Fixed | `ErrorBoundary` now wraps the whole router, covering login, chat, admin and settings routes. |
| 12 | ✅ Fixed | `exportAuditCsv()` now includes CSRF headers, checks `res.ok`, verifies `text/csv`, and throws `ApiError` for failures. |
| 13 | ✅ Fixed | Streaming disconnect/read errors now surface as an error event; `useChat` annotates an interrupted assistant response when no `done` event arrives. |
| 14 | ✅ Fixed | `useChat` stores the last session ID under a user-scoped key and reloads it when the authenticated user changes; sign-out/unauthorized clears stored chat sessions. |
| 15 | ✅ Fixed | Users page now requests `limit=1000` explicitly and displays a "showing first 1,000" hint if the backend cap is reached. |
| 16 | ✅ Fixed | Generated temporary password is shown in a readonly input with a copy button instead of inline text. |
| 17 | ✅ Fixed | Multi-file upload failures accumulate failed filenames in one error message instead of overwriting with the last failure. |
| 18 | ✅ Fixed | Mobile sources toggle now has `aria-label="Toggle citation sources panel"`. |
| 19 | ✅ Already fixed | Cost percentage hint and bar both guard `dailyCeilingUsd > 0`; no division-by-zero remains in current source. |
| 20 | ✅ Fixed | Chat collection name now uses `VITE_DEFAULT_COLLECTION ?? "default"`. |
| 21 | ✅ Fixed | Frontend default Ollama URL now uses `VITE_OLLAMA_URL ?? "http://localhost:11434"`. |
| 22 | ✅ Fixed | `_validate_embedding_model_dimension()` logs skipped Qdrant checks at debug level instead of silently swallowing all exceptions. Covered by `test_embedding_dimension_check_logs_qdrant_errors`. |
| 23 | ✅ Fixed by documentation | Settings live metadata cache is documented as per-process with 60s TTL in code and deployment docs; persisted settings are still DB-read per request. |
| 24 | ✅ Fixed | `OllamaProvider.embed_documents()` only falls back to legacy `/api/embeddings` on 404; other 4xx/5xx errors raise. Covered by `test_ollama_embed_documents_does_not_fallback_on_model_error`. |
| 25 | ✅ Fixed | Audit list joins `User.email` and frontend displays email when available instead of raw UUID. Covered by `test_list_audit_logs_returns_user_email_for_display`. |
| 26 | ✅ Fixed | Admin Settings scroll observer now uses `useLayoutEffect` for layout-dependent section observation. |
| 27 | ✅ Fixed | SSE `done.model` now reports `runtime.chat_model`, with a safe string fallback. Covered by `test_chat_stream_done_event_reports_chat_model_name`. |
| 28 | ✅ Invalid/no impact | `LiveTimer` is only rendered while `isStreaming` is true and unmounts when streaming stops; no persistent interval remains. |
| 29 | ✅ Fixed | CSV export validates response status and content type before downloading. |
| 30 | ✅ Fixed | Password-change success message now explicitly says to sign in again with the new password before redirect. |

## Files Changed In This Pass

- Backend: `app/api/chat_routes.py`, `app/api/document_routes.py`,
  `app/api/audit_routes.py`, `app/services/settings_service.py`,
  `app/services/provider_clients.py`, `app/services/runtime_config.py`,
  `app/services/provider_settings.py`, `app/services/app_config_store.py`,
  `app/auth/router.py`, `app/auth/oidc.py`, `app/config.py`,
  `app/security/input_guard.py`, `app/security/pinned_http.py`,
  `scripts/audit_cleanup.py`, `scripts/verify_airgap_package.py`.
- Frontend: `frontend/src/api/chat.ts`, `frontend/src/api/audit.ts`,
  `frontend/src/api/auth.ts`, `frontend/src/api/documents.ts`,
  `frontend/src/api/settings.ts`, `frontend/src/hooks/useAuth.ts`,
  `frontend/src/hooks/useChat.ts`, `frontend/src/hooks/useDocuments.ts`,
  `frontend/src/hooks/useSettings.ts`, `frontend/src/utils/chatSessionStorage.ts`,
  `frontend/src/App.tsx`, `frontend/src/pages/ChatPage.tsx`,
  `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/SettingsPage.tsx`,
  `frontend/src/pages/admin/ActivityPage.tsx`,
  `frontend/src/pages/admin/AdminLayout.tsx`,
  `frontend/src/pages/admin/DocumentsPage.tsx`,
  `frontend/src/pages/admin/OverviewPage.tsx`,
  `frontend/src/pages/admin/SettingsPage.tsx`,
  `frontend/src/pages/admin/UsersPage.tsx`,
  `frontend/src/components/admin/ActivityEvent.tsx`,
  `frontend/src/components/admin/DocumentRow.tsx`,
  `frontend/src/components/admin/ProviderSettingsSection.tsx`,
  `frontend/src/components/admin/SettingsAtoms.tsx`.
- Tests: `tests/test_chat.py`, `tests/test_admin.py`,
  `tests/test_provider_clients.py`, `tests/test_models.py`,
  `tests/test_runtime_config.py`, `tests/test_health.py`, `tests/test_oidc.py`.
- Docs/config: `docs/deployment.md`, `docs/air-gap-runbook.md`,
  `docker-compose.yml`.

## Review Follow-up Findings — Resolution

| # | Status | Resolution evidence |
|---:|---|---|
| R1 | ✅ Fixed | Persisted `provider_resolved_ip` is now loaded into runtime config and passed into OpenAI-compatible chat/embedding clients, which create a pinned async transport. Legacy OpenAI-compatible configs without a stored IP are lazy-resolved at runtime load. Provider model-list, health `/models`, and embedding-probe paths use the same pinned helper. |
| R2 | ✅ Fixed | OIDC issuer settings now use SSRF validation. OIDC discovery, token, and userinfo calls validate each outbound URL and use pinned async transports. Covered by `tests/test_oidc.py`. |
| R3 | ✅ Fixed | Chat session persistence is keyed by authenticated user id and cleared on sign-out/unauthorized. The legacy global key is removed during cleanup. |
| R4 | ✅ Fixed in report | This report now lists the broader branch scope, including OIDC, auth, air-gap, audit cleanup, settings/tier, runtime, and frontend auth/session files. |
| R5 | ✅ Fixed | Legacy OpenAI-compatible configs without stored `provider_resolved_ip` are lazy-resolved during runtime config load. Covered by `test_runtime_config_resolves_legacy_provider_without_stored_ip`. |
| R6 | ✅ Fixed | `/health` provider `/models` checks use `create_pinned_async_transport()` when `runtime.provider_resolved_ip` is present. Covered by `test_health_provider_check_uses_pinned_transport_when_resolved_ip_exists`. |

## Remaining Open Bugs From Round 4

None known from the original Round 4 list after the fixes and targeted
verification above. This is not a claim that the entire expanded branch has no
remaining defects.

## Deferred Code Quality Notes

These are still architectural/code-style debts, not open Round 4 bugs:

- `collect_field_updates` remains a long validation dispatcher.
- Some service modules still raise HTTP-oriented exceptions.
- Settings provider UI still has duplication and stringly typed dispatch.
- Collection constants and deleted-user helpers could be centralized further.
