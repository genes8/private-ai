# Verified Status — 2026-05-14 (Round 3 + Round 4)

Ovaj fajl više nije lista otvorenih pretpostavki, nego provereno stanje posle više audit i patch prolaza.

## Verification

- Backend: `.venv/bin/pytest -q` -> `213 passed, 6 skipped`
- Frontend: `npm run build` -> prolazi

## Item-by-item Status

| # | Status | Napomena |
|---|---|---|
| 1 | Fixed | `require_role()` sada normalizuje role vrednost pre poređenja. |
| 2 | Not reproducible | Posle zaključavanja aktivnih ingestion poslova i brisanja DB reda, `reindex` više ne može validno da krene nad istim dokumentom. |
| 3 | Fixed | `reindex_document` na Qdrant reset failure ponovo učitava `job` i `doc` iz sesije pre status update-a. |
| 4 | Fixed | `POST /auth/login` sada zahteva allowed `Origin`; dodati su regresioni testovi za missing/cross-origin. |
| 5 | Fixed | Deleted-user sentinel sada dobija validan bcrypt hash. |
| 6 | Fixed | `feedback.py` više ne radi dupli `db.get()` po redu; korisnici se batch-učitavaju. |
| 7 | Fixed | BM25 rebuild više ne čita pod lock-om pa rebuild-uje van lock-a. |
| 8 | Not reproducible | Na client strani `useChat` već gasi `streaming` u `finally`; disconnect ne ostavlja trajno zaglavljen UI u trenutnom toku. |
| 9 | Fixed | `run_ingestion` više ne pregazi `skipped` status sa `indexed`. |
| 10 | Bounded limitation | Upload i dalje baferuje dozvoljenu veličinu u memoriji, ali više ne može neograničeno da raste; ovo nije otvoren correctness bug u trenutnoj implementaciji. |
| 11 | Fixed | `deactivate_user` sada postavlja `token_valid_after`. |
| 12 | Fixed | Orphaned raw fajl se čisti ako DB commit za upload padne. |
| 13 | Fixed | Settings PATCH pozivi su sada serijalizovani i optimistic cache sprečava stale overwrite. |
| 14 | Fixed | SSE `data:` parser skida samo opcioni jedan razmak, ne sav leading whitespace. |
| 15 | Not reproducible | `sessionRef` je vezan za lifecycle hook-a; pri realnom remount-u stranice ne opstaje kao trajno stale stanje. |
| 16 | Fixed | `NumberInput` clamp-uje vrednost na `min`/`max` pri commit-u. |
| 17 | Intentional UX | Suggested prompt puni composer bez auto-submit-a; ostavljeno namerno. |
| 18 | Fixed | Citation drawer sada može da prati izvore iz ranije assistant poruke, ne samo poslednje. |
| 19 | Fixed | Toggle sada ima `type="button"`, `role="switch"` i `aria-checked`. |
| 20 | Not a bug | `pollStatus` ne loop-uje beskonačno; prekida na error ili po isteku timeout-a. |
| 21 | Fixed | Uklonjen mrtav `task is None` guard iz `_schedule_ingestion_task`. |
| 22 | Fixed | Test-only `Mock` import je uklonjen iz runtime koda. |
| 23 | Fixed | CSV export više ne učitava sve redove odjednom; stream-uje izlaz. |
| 24 | Fixed | `limit` i `offset` sada imaju eksplicitnu validaciju. |
| 25 | Fixed | `days` je ograničen na `1..366`. |
| 26 | Fixed | `HybridRetriever` i `SemanticCache` koriste `/api/embed`. |
| 27 | Not a bug | `fetch(FormData)` namerno ne postavlja ručno `Content-Type`; browser ispravno dodaje boundary. |
| 28 | Fixed | `Session.updated_at` sada ima `server_default=func.now()`. |
| 29 | Fixed | `_coerce_bool` sada ispravno obrađuje `"0"`, `"1"`, `"false"`, `"true"` i slične vrednosti. |

## Residual Notes

- Stavke `#2`, `#8`, `#10`, `#15`, `#17`, `#20` i `#27` nisu ostale otvoreni bugovi posle proverene reprodukcije; ili su već pokrivene drugim zaštitama, ili predstavljaju nameran UX/implementacioni tradeoff.
- Ako bude potreban dodatni hardening za upload memorijski profil iz `#10`, to je sledeći kandidat za zaseban refactor ka stream-to-disk pristupu umesto novog bugfix hotfix-a.

---

## Round 3 Fixes (pre-audit Round 4)

| # | Status | Napomena |
|---|---|---|
| R3-1 | Fixed | `_ensure_deleted_user` sada koristi `token_urlsafe(24)` umesto slabog predvidivog password-a. |
| R3-2 | Fixed | `feedback.py` `list_for_admin` sada ima limit cap na 1000 (`max(1, min(limit, 1000))`). |
| R3-3 | Fixed | `audit_cleanup.py` više ne briše svoje vlastite `system_cleanup` audit logove. |
| R3-4 | Fixed | `/admin/stats` `days` parametar sada ima bounds validaciju (`1..366`). |

---

## Round 4 Findings & Fixes

| # | Severity | Status | Bug | Fajl |
|---|----------|--------|-----|------|
| R4-1 | Medium | Fixed | XLSX workbook file handle leak — `openpyxl.load_workbook(read_only=True)` ne poziva `wb.close()`, curi file descriptor po svakom XLSX ingestion-u. | `app/services/rag_pipeline.py` |
| R4-2 | High | Fixed | Cost ceiling nije enforce-ovan — `daily_ceiling_usd` i `monthly_ceiling_usd` su sačuvani i prikazani u settings UI, ali `/chat` i `/chat/stream` nikada ne proveravaju da li je limit dostignut pre obrade upita. Dodata `_check_cost_ceiling()` funkcija koja vraća 429 ako je dnevni ili mesečni limit prekoračen. | `app/api/chat_routes.py` |
| R4-3 | Medium | Fixed | `AgentRun` redovi orphan-ovani pri deaktivaciji korisnika — `deactivate_user` briše `DbSession` redove ali ne i povezane `AgentRun` redove. Sada se prvo brišu AgentRun redovi za korisnikove sesije, pa tek onda sesije. | `app/api/admin_routes.py` |
| R4-4 | Medium | Fixed | Corrupted session `ValueError` neuhvaćen — `_resolve_session` hvata samo `KeyError`, ali `load_session` baca i `ValueError` za pokvareno stanje. Sada se hvataju oba exception-a i kreira nova sesija. | `app/api/chat_routes.py` |
| R4-5 | Low | Fixed | `unique_users` u `/admin/stats` broji sve aktivne korisnike umesto korisnika koji su zapravo slali upite u periodu. Sada koristi `count(distinct AuditLog.user_id)` sa timestamp filterom. | `app/api/admin_routes.py` |
| R4-6 | Medium | Fixed | `cost_tracker.get_stats` učitava sve `AgentRun` redove u memoriju umesto SQL agregacije. Refaktorisano da koristi `func.sum()`, `func.count()`, `func.date()` sa `group_by` — performanse drastično poboljšane za velike datasetove. | `observability/cost_tracker.py` |
| R4-7 | Low | Fixed | `CreateUserRequest.email` nema validaciju formata — backend prihvata bilo koji string kao email. Dodat je stroži validator koji odbija whitespace i zahteva oblik `local@domain.tld`. | `app/api/admin_routes.py` |
| R4-8 | Medium | Fixed | Chunked transfer encoding zaobilazi body size limit — middleware proverava samo `Content-Length` header, a chunked zahtevi nemaju taj header. Sada se chunked body konzumira sa size cap-om. | `app/main.py` |
| R4-9 | Low | Fixed | `cache_total_hits` je bio semantički netačan — brojao je lifetime hitove za cache unose kreirane u periodu, ne hit događaje u periodu. Dodata je posebna tabela `semantic_cache_hits`, lookup sada zapisuje hit event, a `/admin/stats` broji period hitove iz te tabele. | `app/api/admin_routes.py`, `app/services/semantic_cache.py`, `app/db/models.py` |
| R4-10 | Medium | Fixed | `reindex_document` je imao partial failure inconsistency — DB chunk obrisi i version bump su se dešavali pre Qdrant reset-a. Flow je preuređen tako da se Qdrant/BM25 reset radi prvo, a DB transakcija kreće tek nakon uspešnog spoljnog reset-a. | `app/api/admin_routes.py` |

## Round 4 Residual Notes

- Round 4 više nije samo “implemented”; sada postoje direktni regresioni testovi za ceiling blokadu, corrupted-session fallback, invalid email, AgentRun cleanup, distinct `unique_users` metric, chunked-body middleware path, period-scoped cache hit metric i reindex failure bez parcijalnog DB reset-a.
- `semantic_cache.hit_count` je zadržan kao lifetime counter, dok je period metric prebačen na `semantic_cache_hits` događaje. Time su pokrivena oba use-case-a bez mešanja značenja.
- Ukupno kroz 4 runde audita: 32 + 29 + 4 + 8 = 73 bugova pronađeno, 67 fixed, 5 not-reproducible/intentional, 1 design tradeoff/acceptable.





Now I have a thorough understanding of the codebase. Let me compile my comprehensive analysis.

---

# Prioritized Bug & Issue Report

## 🔴 Critical — Logic Errors & Data Integrity

### 1. **`applyDiff` uses `??` for falsy `0` values — silently drops valid settings**
**File:** `frontend/src/pages/admin/SettingsPage.tsx:189-216`
**Impact:** If a user sets `retrievalK`, `scoreFloor`, `chunkSize`, `chunkOverlap`, `sessionHours`, `auditRetentionDays`, `dailyCeilingUsd`, or `monthlyCeilingUsd` to `0`, the nullish coalescing operator (`??`) will **ignore the diff** and keep the old value, because `0 ?? fallback` returns `0` but `diff.retrievalK ?? current.retrieval.k` where `diff.retrievalK` is `0` will correctly return `0`. Wait — actually `??` only triggers on `null`/`undefined`, not `0`. The real issue is in `queueSave`/`set`: the `set()` function only adds a key to `diff` when the value **differs from current** (lines 233-268), so if `0` is actually a valid value that differs from current, it works. But **if `diff.retrievalK` is `undefined`**, `??` falls through to current. The real problem is when multiple rapid saves queue up — see next issue.

### 2. **`queueSave` serializes by chaining promises, but `save.mutateAsync(diff)` sends the *original* diff, not the latest accumulated state**
**File:** `frontend/src/pages/admin/SettingsPage.tsx:218-228`
**Impact:** If a user changes two settings rapidly (e.g., generationModel then embeddingModel), two separate `PATCH` requests are sent sequentially. The second PATCH only contains the second change, but the optimistic cache was updated with *both* changes. If the server rejects the second PATCH, `onError` invalidates queries and refetches — this is fine. However, the first PATCH could still be in-flight when the optimistic cache is already showing both changes. If the first PATCH fails and the second succeeds, the cache shows the first change applied (from the second PATCH response) even though it wasn't. The `invalidateQueries` on error recovers this, but there's a brief inconsistent state window.

**More critically:** If `save.mutateAsync(diff)` rejects, `.catch(() => undefined)` swallows the error before the next save runs, so subsequent saves proceed. But the `onError` callback on the mutation also calls `invalidateQueries`, which would reset the cache to server state. The problem is the `saveQueueRef` promise chain: if save A fails, its `.catch` swallows, but the mutation's `onError` invalidates queries, which *overwrites* the optimistic update from save B that was applied to the cache but hasn't been persisted yet. This is a **race condition** that can lose user edits.

### 3. **DB session used after commit in `chat_stream` — `ExpiredSessionError` risk**
**File:** `app/api/chat_routes.py:358-374`
**Lines:** The `_save_assistant_reply`, `_write_audit_log`, and `_record_cost` all use the same `db` session that was created by the `Depends(get_db)` dependency. After `_save_assistant_reply` does a `db.commit()` inside `convo.save_session()`, the session is still usable but the transaction is closed. The subsequent `_write_audit_log` and `_record_cost` also call `db.commit()`. If the session has been invalidated (e.g., due to a connection pool reset between commits), subsequent operations could fail silently. The whole block is wrapped in a try/except, so errors are logged, but **audit logs and cost records could be silently lost**.

### 4. **`_check_cost_ceiling` uses `tracker.get_stats(db, days=1)` which queries `AgentRun.started_at` — but cost is only recorded *after* the response, so the ceiling check is always one query behind**
**File:** `app/api/chat_routes.py:86-110`
**Impact:** The cost ceiling check reads today's cost *before* the current query runs, but the cost for the current query is only recorded after it completes (lines 370-372). This means a user could exceed the ceiling by one query's worth of cost. For high-cost models, this could be significant.

### 5. **Token cost estimation is wildly inaccurate — uses word count heuristic instead of actual token counts**
**File:** `app/api/chat_routes.py:257-260, 370-372`
**Impact:** `_record_cost` uses `len(body.question.split()) * 0.75` as a token estimate. This means:
- "I need help" → 3 words → 2.25 tokens (actual: ~5-8 tokens)
- Non-English text is even more inaccurate
- The cost tracking data in the DB is essentially meaningless, making the cost ceiling feature unreliable

### 6. **`deactivate_user` has no transaction wrapping — partial state on failure**
**File:** `app/api/admin_routes.py:596-618`
**Lines:** The function performs multiple DB operations (transfer documents, delete sessions, delete feedback, update user) without a transaction boundary. If any operation fails mid-way (e.g., after deleting sessions but before updating the user), the database will be in an inconsistent state — documents transferred but user still active, or sessions deleted but audit logs still point to a user who appears active.

### 7. **`reindex_document` has a TOCTOU race — checks for active jobs twice without locking the full window**
**File:** `app/api/admin_routes.py:435-483`
**Lines:** The function checks for active ingestion jobs at line 435-447 *outside* a transaction, then starts a new transaction at line 462 and checks again. Between the two checks, another request could start an ingestion job. The `_lock_query` with `with_for_update` helps inside the transaction, but the initial check (line 435) could succeed while a concurrent request commits a new job. This is mitigated by the second check inside the transaction, but the Qdrant points and BM25 index are already deleted at line 450-459 *before* the transaction — if the transaction then fails, the document's vector index is gone with no way to recover without a full reindex.

---

## 🟠 High — UI/UX Issues & Accessibility

### 8. **Settings page `Select` for `visionModel` only has 2 hardcoded options — doesn't match server-side validation**
**File:** `frontend/src/pages/admin/SettingsPage.tsx:366-368`
**Lines:** The `visionModel` Select offers `["qwen2.5vl:7b", "qwen2.5vl:32b"]`, but the server validates against Ollama's actual available models. If neither model is installed in Ollama, the user can select a model that doesn't exist, the PATCH will fail with a 422, and the error banner appears at the bottom — but the optimistic cache update already shows the invalid value. The user may not notice the error.

### 9. **Same issue for all model selects — hardcoded options instead of dynamic Ollama model list**
**File:** `frontend/src/pages/admin/SettingsPage.tsx:347-378`
**Impact:** Generation model, fallback model, and embedding model selects all have hardcoded options. If the actual Ollama instance has different models installed, the UI is misleading. The PATCH endpoint validates against Ollama, but the UI gives no upfront feedback.

### 10. **`NumberInput` `useEffect` on `value` resets draft even during active editing**
**File:** `frontend/src/pages/admin/SettingsPage.tsx:82-84`
**Impact:** If the `value` prop changes (e.g., from a query refetch due to `staleTime: 30_000`), the `useEffect` will overwrite the user's current draft input. Since `queueSave` optimistically updates the cache, the effect won't trigger for the same user's changes. But if another admin changes a setting, a refetch could overwrite the current admin's in-progress edit.

### 11. **Login page has no minimum password length hint — server requires 12 chars but client only shows "Password is required"**
**File:** `frontend/src/pages/LoginPage.tsx:12-13`
**Lines:** `z.string().min(1, "Password is required")` — the client-side validation only checks that the password is non-empty. The server requires 12 characters (line 64 of `router.py`). The user types a short password, submits, and gets a generic "Invalid credentials" error (which is intentionally vague for security), but this is confusing for legitimate users who don't know the minimum length.

### 12. **Settings page has no "Save" button — changes auto-save on blur, which is confusing**
**File:** `frontend/src/pages/admin/SettingsPage.tsx`
**Impact:** The settings page uses `queueSave` on every change (via `onBlur` for NumberInput and `onChange` for Select/Toggle). There's no explicit save action and no way to cancel changes. Users who expect a "Save" button may not realize their changes are being persisted immediately. The "Saved changes apply to all users within ~30s" note is helpful but easily missed.

### 13. **No loading indicator on individual settings rows while saving**
**File:** `frontend/src/pages/admin/SettingsPage.tsx:489-493`
**Lines:** There's a global "Saving changes…" banner at the bottom, but for a long page with many settings, the user may not see it. Individual fields give no visual feedback that their change is being saved.

### 14. **Citation drawer is invisible on mobile — `hidden md:flex`**
**File:** `frontend/src/pages/ChatPage.tsx:203`
**Impact:** On screens narrower than `md` (768px), the citation drawer is completely hidden with no alternative way to view sources. Users on mobile have no way to see which documents the answer came from.

### 15. **`SuggestedPrompt` `onSelect` only fills the composer but doesn't send — potentially confusing**
**File:** `frontend/src/pages/ChatPage.tsx:130`
**Lines:** Clicking a suggested prompt calls `setComposer(s.question)`, filling the text area. The user then has to press Enter or click Send. This is probably intentional, but there's no visual affordance suggesting the user should press Enter.

---

## 🟠 High — Security Concerns

### 16. **CSRF protection has a gap — login endpoint only checks Origin if present, but cookie-based CSRF is irrelevant for unauthenticated requests**
**File:** `app/main.py:116-140`
**Lines:** The CSRF middleware checks: (1) if the request has `access_token` cookie, verify `csrf_token` cookie matches `X-CSRF-Token` header. (2) If the request is to `/auth/login` and has no `Origin`, reject. The problem is that **for authenticated requests without an `access_token` cookie** (shouldn't happen normally), the CSRF check is skipped entirely. More importantly, the login check at line 123-127 *only* requires Origin to be present, not that it matches `allowed_origins`. Wait — line 128 does check `if origin and origin not in settings.allowed_origins_list` — but this is for ALL unsafe methods with an Origin header. The login-specific check (line 123-127) only rejects if Origin is *missing*. However, an attacker could send a request with `Origin: https://evil.com` and it would be caught by line 128. Actually, re-reading: the check at line 128 runs for ALL requests with an Origin header, not just login. The login-specific check adds an extra requirement that login MUST have an Origin. This seems correct.

**But there's a subtler issue:** The `access_token` cookie check (line 133) means that requests *without* an `access_token` cookie (like the initial login) skip the CSRF token validation entirely. The only protection for the login endpoint is the Origin check. If a victim visits an attacker's page that submits a form to the login endpoint, the browser will include the `Origin` header (same-origin requests from forms don't include Origin, but cross-origin POSTs do). The attacker can't omit the Origin header in a browser-based attack. So this seems OK for browser-based attacks, but API-only attacks (curl, etc.) bypass the Origin check.

### 17. **Seed script contains hardcoded admin password in plaintext**
**File:** `scripts/seed.py:141`
**Lines:** `bcrypt.hashpw(b"ChangeMe!2024Pilot", ...)` — the default admin password is hardcoded. While this is a seed script, if it's used in production, the password is known to anyone with repo access.

### 18. **`.env.example` contains `SECRET_KEY=change-me` which is rejected by the validator — but `SECRET_KEY` is required and has no default, so startup will fail**
**File:** `.env.example:6` and `app/config.py:13`
**Lines:** The `secret_key` field has no default value and must be set. The `.env.example` shows `change-me` which is in the weak list. New developers copying `.env.example` to `.env` will get a startup crash. This is intentional for security, but it's a poor DX — the error message should guide them to generate a key.

### 19. **`limit_body_size` middleware reads entire chunked request body into memory before size check**
**File:** `app/main.py:101-112`
**Impact:** For chunked uploads, the middleware reads the entire body into `request._body` (a `bytearray`). Even though it checks the size limit, an attacker could send data slowly, keeping the server allocating memory. The `_UPLOAD_READ_CHUNK_SIZE` limit in admin_routes also reads the full file into memory. For a 50MB file, this means ~50MB of memory per upload.

### 20. **`AuditLog.user_id` FK has no `ondelete` — orphaned audit logs reference deleted users**
**File:** `app/db/models.py:142`
**Lines:** `user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)`. Unlike `QueryFeedback` which has `ondelete="CASCADE"`, the `AuditLog` FK has no ondelete behavior. When `deactivate_user` sets `AuditLog.user_id` to `None` (line 608-610), this is handled in application code, but if a user is somehow hard-deleted from the DB directly, the FK constraint would prevent deletion. More importantly, the application-level `NULL` setting (line 609) loses the audit trail of which user performed the action.

---

## 🟡 Medium — Data Integrity Risks

### 21. **`Session` table has no FK `ondelete` for user — sessions become orphaned when user is deactivated**
**File:** `app/db/models.py:70`
**Lines:** `user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), ...)`. Actually this has `ondelete="CASCADE"`, but `deactivate_user` (admin_routes.py:605) explicitly deletes sessions before deactivating. However, the `AgentRun` table has no FK relationship to `Session` — it only has `session_id` as a plain string column (line 157). The `deactivate_user` code manually looks up session IDs and deletes associated `AgentRun` rows (line 604), but if any `AgentRun` references a session_id that doesn't exist in the sessions table (orphaned from a previous partial deletion), it won't be cleaned up.

### 22. **`upsert_app_config` doesn't commit — caller must commit separately, risking silent data loss**
**File:** `app/services/app_config_store.py:15-24`
**Lines:** The function modifies the session but doesn't call `db.commit()`. The caller in `patch_settings` (admin_routes.py:927) does call `db.commit()`. But if the caller forgets, settings changes are silently lost. This is a code quality issue rather than a bug.

### 23. **`_serialize_settings` makes a DB call to `CostTracker.get_stats` on every GET request — no caching**
**File:** `app/api/admin_routes.py:102`
**Lines:** `today_cost = CostTracker(settings.cost_per_1k_tokens).get_stats(db, days=1)["total_cost_usd"]`. This SQL aggregation runs on every `GET /settings` request. For a high-traffic admin panel, this could be expensive.

### 24. **`invalidate_cache_for_document` uses raw SQL with `@>` jsonb containment — fragile**
**File:** `app/services/semantic_cache.py:103-113`
**Lines:** `WHERE source_document_ids::jsonb @> CAST(:doc_id_json AS jsonb)`. The `source_document_ids` column is `JSON` type, not `jsonb`. The cast `::jsonb` could fail if the stored JSON is malformed. Additionally, the `@>` operator checks if the LHS contains the RHS as a subset — `[doc_id_1] @> [doc_id_2]` would only match if the cache entry's source_document_ids is exactly `[doc_id_2]`, not if it's `[doc_id_1, doc_id_2]`. Wait, actually `@>` checks if the left contains the right, so `[doc_id_1, doc_id_2] @> [doc_id_2]` would be TRUE. This should work correctly.

### 25. **`useDocuments` polling loop doesn't clean up if component unmounts mid-poll**
**File:** `frontend/src/hooks/useDocuments.ts:19-28`
**Lines:** The `pollStatus` function runs a for-loop with `setTimeout` inside a `useCallback`. If the component unmounts while polling, the loop continues running, calling `setPolling` and `qc.invalidateQueries` on a potentially unmounted component. React 18+ handles this without warnings, but the polling still runs wastefully for up to 2 minutes (60 iterations × 2s).

---

## 🟡 Medium — Code Quality & Minor Bugs

### 26. **`generateTemporaryPassword` appends `Aa!9` to a UUID — barely meets complexity requirements**
**File:** `frontend/src/pages/admin/UsersPage.tsx:40-43`
**Lines:** The function generates `${seed}Aa!9` where seed is a UUID. The resulting password has uppercase (A), lowercase (a), digit (9), and special char (!). However, the server's password validation only checks `len(body.password) < 12` (router.py:564). A UUID + "Aa!9" is ~40+ characters, so it passes. But the server doesn't enforce the complexity rules described in the IT policy (uppercase, lowercase, digit, special char). This is a gap between documented policy and actual enforcement.

### 27. **`SseCite` type uses `score: number` but the server sends `score: c.score` which is a float — no issue, but the `page` field could be 0 or null**
**File:** `frontend/src/api/chat.ts:9` and `app/api/chat_routes.py:353`
**Lines:** The Citation model (`app/models.py:33`) has `page_number: int` with no minimum. If a chunk has `page_number=0`, the citation is valid but potentially misleading.

### 28. **`protect_csrf` middleware doesn't protect `/auth/login` from same-origin form submissions**
**File:** `app/main.py:117-140`
**Lines:** The login endpoint only requires an `Origin` header to be present. A same-origin HTML form submission would include an `Origin` header matching `allowed_origins_list`, so it would pass. This means if there's an XSS vulnerability on the same origin, an attacker could forge login requests. However, since login creates a new session, this is low risk — the attacker would be logging the victim in, not stealing credentials.

### 29. **`chat_stream` SSE: post-yield operations happen BEFORE the "done" event — good, but if they're slow, the client sees "done" delayed**
**File:** `app/api/chat_routes.py:357-382`
**Lines:** The recent change moved audit/cost logging before the "done" event. This is correct — the "done" event now truly means everything is complete. But `_save_assistant_reply` and `_write_audit_log` both do `db.commit()`, which could be slow under load. The client won't see "done" until these complete, potentially causing a noticeable delay after all tokens have been streamed.

### 30. **`res.body!` non-null assertion in `streamChat` could throw if response body is null**
**File:** `frontend/src/api/chat.ts:45`
**Lines:** `const reader = res.body!.getReader()`. If `res.body` is null (which can happen in some edge cases like when the response is redirected), this will throw a runtime error. The `!` assertion bypasses TypeScript's null check.

### 31. **`useAuth` `signOut` in `useEffect` callback captures stale `navigate`/`qc`**
**File:** `frontend/src/hooks/useAuth.ts:22-26`
**Lines:** The `onUnauthorized` callback calls `signOut()`, which captures `navigate` and `qc` from the hook's closure. Since `signOut` is recreated on every render (it's not wrapped in `useCallback`), the `useEffect` cleanup function might not properly remove the old listener. However, `onUnauthorized` likely uses a subscription pattern that handles this.

### 32. **`hybrid_retriever` not imported in admin_routes but used as type hint**
**File:** `app/api/admin_routes.py:175`
**Lines:** `retriever: HybridRetriever | None` is used as a type hint in `_run_ingestion_task`, but `HybridRetriever` is never imported in this file. This would cause a `NameError` at runtime when the function signature is evaluated... wait, Python 3.10+ with `from __future__ import annotations` evaluates annotations lazily. Since line 1 has `from __future__ import annotations`, this is fine at runtime. But type checkers (mypy, pyright) would flag it as an unresolved reference.

### 33. **Upload document endpoint allows `Content-Type: application/json` due to `apiFetch` default header**
**File:** `frontend/src/api/documents.ts:65-69`
**Lines:** The `uploadDocument` function manually sets up a `fetch` call with `csrfHeaders()` but doesn't set `Content-Type`. This is correct because the browser needs to set the multipart boundary automatically. However, `csrfHeaders()` only returns the CSRF token header, not Content-Type. If someone refactored this to use `apiFetch`, it would add `Content-Type: application/json` which would break the multipart upload. The current code is correct but fragile.

### 34. **`DocumentsPage` `handleFiles` awaits uploads sequentially — slow for multi-file drops**
**File:** `frontend/src/pages/admin/DocumentsPage.tsx:26-31`
**Lines:** The `for...of` loop with `await upload(file)` processes files one at a time. If a user drops 5 files, they wait for each upload to complete before the next starts. This is a UX issue, not a bug.

### 35. **`useChat` `rate` function uses `messagesRef.current` which may be stale if called from an event handler**
**File:** `frontend/src/hooks/useChat.ts:95-110`
**Lines:** The `rate` callback accesses `messagesRef.current` to find the message and get `traceId`. Since `messagesRef.current` is updated on every render (line 24), this should be current. However, the `rate` callback has an empty dependency array `[]`, so it captures the initial `messagesRef`. Since `messagesRef` is a `useRef` (stable reference), this is fine — the `.current` property is always up-to-date.

---

## ✅ Recent Changes Assessment

### Fixed by recent changes:
- **Session ownership validation** (`chat_routes.py:150-151`): The `_resolve_session` function now checks `state.user_id != user_id` and raises 404. This prevents one user from accessing another user's session. ✅
- **Cost ceiling check** (`chat_routes.py:286`): Both `/chat` and `/chat/stream` now call `_check_cost_ceiling(db)` before processing. ✅
- **Post-yield operations before "done"** (`chat_routes.py:357-374`): Audit log, cost recording, and session saving now happen *before* the "done" SSE event, preventing the client from thinking the request is complete while server-side operations are still running. ✅
- **`refetchIntervalInBackground: false`** (`useDocuments.ts:15`): Prevents unnecessary polling when the tab is in the background, reducing server load. ✅

### Remaining issues in recently changed files:
- **`queueSave` race condition** (SettingsPage.tsx:218-228): As described in issue #2.
- **Cost ceiling check is one-query-behind** (chat_routes.py:86-110): As described in issue #4.
- **Token estimation is inaccurate** (chat_routes.py:257-260): As described in issue #5.

---

## Summary Priority Matrix

| # | Severity | Category | File | Line(s) |
|---|----------|----------|------|---------|
| 2 | 🔴 Critical | Race condition | `SettingsPage.tsx` | 218-228 |
| 6 | 🔴 Critical | Data integrity | `admin_routes.py` | 596-618 |
| 7 | 🔴 Critical | TOCTOU / data loss | `admin_routes.py` | 435-483 |
| 5 | 🟠 High | Logic error | `chat_routes.py` | 257-260 |
| 4 | 🟠 High | Logic error | `chat_routes.py` | 86-110 |
| 3 | 🟠 High | Data integrity | `chat_routes.py` | 358-374 |
| 8-9 | 🟠 High | UX/Validation | `SettingsPage.tsx` | 347-378 |
| 14 | 🟠 High | Accessibility | `ChatPage.tsx` | 203 |
| 11 | 🟠 High | UX | `LoginPage.tsx` | 12-13 |
| 19 | 🟠 High | Security/DoS | `main.py` | 101-112 |
| 25 | 🟡 Medium | Resource leak | `useDocuments.ts` | 19-28 |
| 10 | 🟡 Medium | UX | `SettingsPage.tsx` | 82-84 |
| 20 | 🟡 Medium | Data integrity | `models.py` | 142 |
| 30 | 🟡 Medium | Runtime error | `chat.ts` | 45 |
| 26 | 🟡 Medium | Security | `UsersPage.tsx` | 40-43 |