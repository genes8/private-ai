# Bug Hunting Report — safe4ai-pilot/ (2026-05-23, Round 2)

Deep code audit focusing on logic errors, data integrity risks, security concerns, and UI/UX issues. All 30+ source files read and analyzed: chat routes, auth pipeline, RAG pipeline, admin routes, settings routes, ingestion service, security modules, frontend hooks, and all admin pages.

## Verification Status — 2026-05-23

| Check | Result | Evidence |
|-------|--------|----------|
| Backend tests | ✅ Pass | `./.venv/bin/pytest -q` → `339 passed, 6 skipped, 1 warning` |
| Frontend build | ✅ Pass | `npm run build` in `safe4ai-pilot/frontend` completed successfully |

The remaining issues below are code-quality, architecture, data-integrity, and maintainability findings. They are not currently failing the automated test/build checks.

---

## 🔴 CRITICAL — Data Loss / Integrity Risks

### 1. `content_filter` silently drops chunks containing legitimate PII — `app/security/content_filter.py:28-40`

```python
def filter_chunks(self, chunks: list[RankedChunk]) -> list[RankedChunk]:
    clean: list[RankedChunk] = []
    for chunk in chunks:
        if _contains_pii(chunk.content):
            logger.warning("pii_chunk_excluded", chunk_id=chunk.chunk_id, doc_id=chunk.doc_id)
        else:
            clean.append(chunk)
    return clean
```

Called from `graph.py:122` in the `retrieve_node`, **AFTER** reranking but BEFORE grading and generation. This means if a document about employee benefits contains an SSN (e.g., "Your SSN 123-45-6789 is used for..."), that entire chunk is **silently removed from the retrieval results**. The LLM then cannot answer questions about that content — and the user gets "I don't have enough information" even though the relevant document IS indexed.

The same filter is also applied during **ingestion** (`rag_pipeline.py:140`), meaning PII-containing chunks are never even embedded into Qdrant. This double-filtering (ingestion + retrieval) means ANY document containing SSN/credit-card/passport patterns is completely invisible to the chat.

**Impact:** If a company uploads an HR policy document that happens to contain an SSN example ("Enter your SSN: XXX-XX-XXXX" or a real SSN in a form), that content is permanently invisible to queries.

**Fix:** At minimum, remove the retrieval-time filter (keep ingestion-time only) since chunks are already filtered before indexing. Better: make PII filtering configurable per deployment, with a `redact_pii` mode that redacts rather than drops.

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

### 3. `settings_routes.py` makes **blocking synchronous HTTP calls** inside `async` FastAPI endpoints — `app/api/settings_routes.py:46-58`

```python
def _fetch_provider_model_names(base_url: str, api_key: str) -> list[str]:
    try:
        with httpx.Client(timeout=5.0) as client:   # ← synchronous!
            resp = client.get(f"{base_url.rstrip('/')}/models", ...)
```

And `_get_settings_live_metadata` calls `_svc.fetch_ollama_model_names()` which also uses a synchronous httpx.Client.

These synchronous HTTP calls block the **entire asyncio event loop** while waiting for the external provider/Ollama response. Under load, this means ALL concurrent requests (including SSE chat streams) are frozen for up to 5 seconds while the Ollama `/api/tags` endpoint responds.

`GET /settings` and `PATCH /settings` are async endpoints (`async def`), so FastAPI runs them on the event loop — but the synchronous httpx calls inside them block it.

**Fix:** Replace `httpx.Client` with `httpx.AsyncClient` and `await` the calls. Or run the sync calls in `asyncio.to_thread()`.

---

### 4. SSRF validation has a TOCTOU race — `app/security/url_validator.py:41-53`

```python
resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
for _family, _type, _proto, _canonname, sockaddr in resolved:
    ip = ipaddress.ip_address(sockaddr[0])
    for network in _BLOCKED_NETWORKS:
        if ip in network:
            raise HTTPException(...)
```

The DNS resolution happens at validation time, but the actual HTTP request to the provider URL happens later (in `_fetch_provider_model_names` or `test_provider_connection`). Between resolution and request, DNS could return a different IP (DNS rebinding attack). The validator resolves `evil.com` → public IP (passes check), then the actual request goes to `evil.com` → `127.0.0.1` (internal IP).

**Impact:** An admin configuring a malicious provider URL could use DNS rebinding to reach internal services. This is a realistic attack vector when the admin role is compromised.

**Fix:** After DNS validation, use `httpx` with a custom transport that resolves the hostname to the validated IP address, preventing re-resolution. Or use a connection-level IP allowlist.

---

### 5. Cost ceiling check uses **estimated** tokens, not actual — `app/api/chat_routes.py:331-333`

```python
prompt_tokens = estimate_tokens(body.question)
completion_tokens = estimate_tokens(final.draft_answer or "")
_record_cost(db, session_id, prompt_tokens, completion_tokens, model_name=_chat_model_name)
```

The blocking `/chat` endpoint uses `estimate_tokens()` (chars/4 heuristic) for cost tracking, even when `final.provider_usage` contains **actual token counts** from the provider. The `/chat/stream` endpoint correctly uses `_usage_or_estimate()` which prefers actual usage when available. But `/chat` always estimates.

**Impact:** Cost tracking for the blocking endpoint is inaccurate. With `cost_per_1k_tokens > 0`, this means the daily/monthly ceiling enforcement is based on incorrect numbers. The ceiling check itself (lines 113-157) also uses `estimate_tokens` for the projected cost.

**Fix:** Use `provider_usage` from the final state when available, falling back to estimates:
```python
usage = _usage_or_estimate(body.question, final.draft_answer or "", final.provider_usage)
_record_cost(db, session_id, usage.prompt_tokens, usage.completion_tokens, model_name=_chat_model_name)
```

---

### 6. `useChat` hook silently drops feedback when session ref is null — `frontend/src/hooks/useChat.ts:106-108`

```typescript
const rate = useCallback(async (msgId: string, rating: "up" | "down") => {
    const msg = messagesRef.current.find((m) => m.id === msgId);
    if (!msg?.traceId || !sessionRef.current) return;  // ← silent return
```

If `sessionRef.current` is null (e.g., if the user refreshes the page mid-conversation and then tries to rate a previous message), the feedback is **silently dropped**. The UI shows the thumb as selected (optimistic update on line 110-112), but the feedback is never sent to the server. The user sees "rated" but the server has no record.

**Fix:** Show an error state or toast when feedback cannot be submitted due to missing session/trace context, rather than silently dropping it.

---

## 🟡 MEDIUM — Robustness / Maintainability

### 7. Qdrant point IDs are generated independently from DB chunk IDs — `app/services/rag_pipeline.py:149-176`

```python
points = [
    qmodels.PointStruct(
        id=str(uuid.uuid4()),        # ← Qdrant point ID
        vector=embeddings[i],
        payload={...},
    )
    for i in range(len(clean_chunks))
]

for i, point in enumerate(points):
    chunk = DocumentChunk(
        id=str(uuid.uuid4()),          # ← DB chunk ID (different!)
        qdrant_point_id=str(point.id), # ← stored as reference
    )
```

The Qdrant point ID and the DB chunk ID are different UUIDs. The `qdrant_point_id` column stores the cross-reference, but there's no enforcement that they stay in sync. If the DB transaction fails after `qdrant.upsert()` succeeds (line 165), the Qdrant collection contains orphaned points that no DB row references. These points are never cleaned up.

The `delete_document` endpoint (admin_routes.py:357) deletes DB chunks by `document_id` and then calls `_delete_qdrant_points(doc_id)` which filters by the `doc_id` payload field — so orphans from failed transactions WOULD be cleaned up on document deletion. But if the document is never deleted, the orphaned points persist forever.

**Fix:** Use the DB chunk ID as the Qdrant point ID (or vice versa) to eliminate the cross-reference. Or wrap the Qdrant upsert + DB insert in a compensating-transaction pattern.

---

### 8. `settings_live_cache` TTL is only 15 seconds but Ollama model fetch can take 5+ seconds — `app/api/settings_routes.py:35-43`

```python
_SETTINGS_LIVE_TTL_SECONDS = 15.0
```

With a 15-second cache TTL and Ollama model fetching taking up to 5 seconds (the `httpx.Client(timeout=5.0)` on line 48), the cache hit rate is low under frequent settings page loads. Every 15 seconds, the next `GET /settings` call blocks for up to 5 seconds waiting for Ollama. Combined with issue #3 (sync HTTP in async context), this creates periodic request stalls.

**Fix:** Increase TTL to 60 seconds. Or better: fetch Ollama models asynchronously and cache the result, rather than blocking each settings request.

---

### 9. `graph.py` quality gate can send the same query to retrieve twice with identical parameters — `app/agents/graph.py:280-294`

```python
if state.retrieval_attempts < _MAX_RETRIEVAL_ATTEMPTS:
    allowed = ["respond", "retrieve", "fallback"]
else:
    allowed = ["respond", "fallback"]
```

When the quality gate decides to re-retrieve, the `retrieve_node` runs again with the same `rewritten_query` and same `top_k`. The only change is `retrieval_attempts` is incremented. There's no query modification, no expansion of `top_k`, no different retrieval strategy. The second retrieval will likely return the **same chunks** as the first, leading to the same grading result, the same quality gate decision — a wasted API call cycle.

The `decompose_node` exists to handle this (splitting the query into sub-queries), but the quality gate routes directly to `retrieve`, not to `decompose`. The only way decompose is triggered is via `grade_node` → `route_after_grade` when there are < 2 relevant chunks.

**Fix:** When re-retrieving after quality gate failure, either: (a) route to `decompose` instead of `retrieve`, or (b) increase `top_k` on subsequent attempts, or (c) rewrite the query before re-retrieval.

---

### 10. `InputGuard` injection patterns have many false positives — `app/security/input_guard.py:11-21`

```python
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(?:previous|all|prior)\s+instructions",
        r"you\s+are\s+now",
        r"act\s+as\s+(?:if\s+you\s+are|a|an)",
        ...
    ]
]
```

A user asking "What are our instructions for annual leave?" would match `instructions` in the first pattern if preceded by "ignore all" in a different context. More importantly, `"you are now"` matches legitimate business queries like "Can you tell me if you are now requiring..." or "Are you now accepting applications?". The `"act as a"` pattern matches "act as a witness" or "act as an agent" — common legal language.

**Impact:** Legitimate user queries about company policies can be blocked by the input guard, returning "Potential prompt injection detected" with no way to bypass.

**Fix:** Tighten the patterns to require sentence-start or imperative context. Add a confidence scoring system rather than binary match. Or move injection detection to a weaker "warning" tier that still processes the query.

---

### 11. Conversation summary loses all history older than the threshold — `app/services/conversation.py:110-117`

```python
summary_message = Message(
    role="assistant",
    content=f"[Conversation summary] {summary}",
    created_at=datetime.now(UTC),
)
recent_tail = state.messages[-(_SUMMARIZE_THRESHOLD - 1):] if _SUMMARIZE_THRESHOLD > 1 else []
updated_state = state.model_copy(update={"messages": [summary_message, *recent_tail]})
```

When a conversation exceeds 10 messages, the entire history is replaced with a single summary + the last 9 messages. The summary is generated by the LLM and is lossy. If the LLM fails to generate a summary (caught on line 107-108), the function returns silently — the conversation is NOT summarized and continues to grow unbounded, potentially hitting the 1MB `state_json` limit (line 63).

**Impact:** Long conversations either lose critical context (via lossy summary) or grow unbounded until they hit the 1MB limit and fail to save.

**Fix:** If the LLM summarization fails, implement a fallback strategy (e.g., keep only the last N messages without summarization). Also consider summarizing incrementally rather than replacing the entire history at once.

---

## Previously Fixed Issues (from Round 7 and Round 1, verified still fixed)

| # | Issue | Verification |
|---|-------|-------------|
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

## Thermo-Nuclear Code Quality Review — Verified 2026-05-23

Scope: full code-quality audit of the current source tree on `main @ 80310e3`. This is stricter than the bug list above and focuses on structural maintainability, abstraction quality, and spaghetti growth.

### BLOCKERS — Must Fix Before Shipping

| ID | Status | Finding | Verification |
|----|--------|---------|--------------|
| B1 | ✅ Confirmed | Blocking `/chat` and streaming `/chat/stream` use divergent audit/cost persistence paths. | `chat_routes.py` still uses `_write_audit_log`, `_record_cost`, and `_save_assistant_reply`; `chat_finalizer.py` writes different `action_type`/metadata and creates `AgentRun` through a different path. |
| B2 | ✅ Confirmed | `CustomModelManager` is defined inside `ProviderSettingsSection` render body. | `frontend/src/components/admin/ProviderSettingsSection.tsx:65-119` defines a component inside the parent function, creating a new component identity on every render. |
| B3 | ✅ Confirmed | `collect_field_updates` is a long validation if-chain. | `app/services/settings_service.py:258-413` contains repeated `if body.X is not None` validation/update branches and repeated numeric range checks. |

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
| M7 | ✅ Confirmed | Dead `if True:` branch in CSRF middleware. | `app/main.py:99` contains a leftover `if True:` wrapper. |
| M8 | ✅ Confirmed | Vector-size extraction is copy-pasted. | Same vector config extraction pattern appears in `settings_service.py` and `startup_migrations.py`. |
| M9 | ✅ Confirmed | Vision model magic string is duplicated. | `"qwen2.5vl:7b"` appears in `settings_routes.py`, `settings_service.py`, and `runtime_config.py`. |
| M10 | ✅ Confirmed | Entity booster compiles regex inside loops. | `entity_booster.py` calls `re.search(r"\b" + re.escape(tok) + r"\b", ...)` per token/chunk. |

### Stale Or Incorrect Review Items

| Review claim | Current status |
|--------------|----------------|
| `AdminLayout` fetches all feedback just to count negatives | ❌ Stale. `AdminLayout` now uses `queryKey: ["feedback-count"]` and `GET /admin/feedback/count`. |
| Feedback query key shared between `AdminLayout` and `FeedbackPage` | ❌ Stale. `AdminLayout` uses `["feedback-count"]`; `FeedbackPage` uses `["feedback"]`. |

### Thermo Summary

| Category | Count | Key Theme |
|----------|-------|-----------|
| Blockers | 3 | Divergent chat persistence, render-local component identity, large settings validation if-chain |
| High | 4 | HTTP/service boundary coupling, split save paths, fragile optimistic state, duplicated provider UI |
| Medium | 10 | Duplicated constants, route-layer business logic, partial dead code, silent startup warnings, magic strings |
| Stale/Incorrect | 2 | Feedback-count issues already fixed |

**Thermo verdict:** Not approved for shipping on structure. Tests and build pass, but B1/B2/B3 should be treated as presumptive blockers before calling the branch clean.

---

## Summary

| Priority | Count | Key Themes |
|----------|-------|------------|
| 🔴 Critical | 2 | PII filter silently removes legitimate chunks; fragile dual code paths for chat persistence |
| 🟠 High | 4 | Blocking sync HTTP in async endpoints; SSRF TOCTOU race; inaccurate cost tracking; silent feedback drop |
| 🟡 Medium | 5 | Qdrant/DB ID drift; cache TTL too short; retrieve-retry is identical; false-positive injection guard; conversation summary lossy/unbounded |
| **Total** | **11** | Down from 12 in Round 1 — all Round 1 issues resolved; new deeper issues found |

Additional thermo-nuclear review status: **3 structural blockers, 4 high-priority quality debts, 10 medium architectural smells.**
