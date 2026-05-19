# Security Audit Report — Safe4AI Pilot

**Date:** 2025-05-19
**Scope:** Middleware (`app/main.py`), auth (`app/auth/`), API routes (`app/api/`), security guards (`app/security/`), nginx reverse proxy (`frontend/nginx.conf`), Docker deployment (`docker-compose.yml`).

---

## CRITICAL

### F-01: CL/TE Desync primitive in `limit_body_size`

**File:** `app/main.py:130-139`

```python
content_length = request.headers.get("content-length")
max_body_bytes = settings.max_upload_size_mb * 1024 * 1024
if content_length:
    try:
        length = int(content_length)
    except ValueError:
        return Response(status_code=400, content="Invalid content-length header")
    if length > max_body_bytes:
        return Response(status_code=413, content="Request body too large")
elif request.headers.get("transfer-encoding", "").lower() == "chunked":
```

**Problem:** `if` / `elif` structure means when a request has **both** headers (`Content-Length` + `Transfer-Encoding: chunked`), only `Content-Length` is checked. Per RFC 7230 §3.3.3, when both are present, `Transfer-Encoding` takes precedence and `Content-Length` must be ignored. The nginx frontend proxy and Uvicorn backend **may interpret the same request differently** — classic CL/TE desync.

**Impact:** An attacker can send a request where:
- Nginx (frontend proxy) reads body per `Transfer-Encoding: chunked`
- Uvicorn / middleware reads per `Content-Length`
- Result: smuggled request bypasses body size check, or part of the body is interpreted as the next HTTP request

**Fix:** Always reject requests with **both** headers. `Transfer-Encoding` must take precedence.

---

### F-02: Body size bypass on `/chat` and `/chat/stream`

**File:** `app/main.py:139-142`

```python
elif request.headers.get("transfer-encoding", "").lower() == "chunked":
    # Skip chunked body replay for chat streaming — the body is always tiny JSON
    # and the replay mechanism uses private ASGI internals that may break across versions.
    if request.url.path not in {"/chat/stream", "/chat"}:
```

**Problem:** Chunked requests to `/chat` and `/chat/stream` **completely skip body size validation**. The comment says "body is always tiny JSON" — but an attacker can send arbitrarily large chunked body.

**Impact:** Denial of Service — unlimited payload is loaded into memory. Pydantic parses JSON, but before that FastAPI/Starlette reads the entire body into RAM.

---

### F-03: Direct Uvicorn access bypasses nginx

**File:** `docker-compose.yml:48-49`

```yaml
ports:
  - "8000:8000"
```

**Problem:** Port 8000 is directly exposed. An attacker can bypass nginx and target Uvicorn directly — all nginx security headers, proxy buffering, and rate limiting at that level are bypassed.

**Impact:** All vulnerabilities from F-01 and F-02 are exploitable directly, without proxy normalization.

**Fix:** Remove `ports: - "8000:8000"` or bind to `127.0.0.1:8000:8000`. Backend should only be accessible through nginx.

---

## HIGH

### F-04: SSRF via Provider URL

**File:** `app/api/admin_routes.py:1116-1117, 1178-1182`

```python
if body.providerBaseUrl is not None:
    updates["provider_base_url"] = body.providerBaseUrl.rstrip("/")
```

Used in:
```python
with httpx.Client(timeout=10.0) as client:
    resp = client.get(
        f"{base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
```

**Problem:** Admin user can set `providerBaseUrl` to any URL: `http://169.254.169.254/latest/meta-data`, `http://localhost:5432`, etc. The server makes an outbound HTTP request to that URL with an Authorization header.

**Impact:** SSRF — scanning internal services, reading cloud metadata (AWS/GCP/Azure credentials), port scanning.

**Fix:** URL allowlist/denylist: block private IP ranges (10.x, 172.16-31.x, 192.168.x, 169.254.x, localhost, 127.x), block non-http(s) schemes.

---

### F-05: ASGI internals monkey-patching

**File:** `app/main.py:171-172`

```python
request._stream_consumed = False
request._receive = replay_receive
```

**Problem:** Accessing private Starlette attributes (`_stream_consumed`, `_receive`). These attributes:
- Have no stability guarantee between versions
- Can create race conditions with async middleware chain
- `SpooledTemporaryFile` on line 145 is not closed on all error paths (file descriptor leak)

**Impact:** Breakage on Starlette upgrade, potential file descriptor leak under load.

---

### F-06: Health endpoint info leak

**File:** `app/main.py:378-422`

```python
@app.get("/health")
async def health() -> dict[str, object]:
```

**Problem:** Unauthenticated endpoint that returns detailed error messages with internal hostnames, ports, and connection strings for Postgres, Qdrant, and provider.

**Impact:** Information disclosure — attacker learns internal topology, service versions, port mappings.

**Fix:** Return only `{"status": "ok"|"degraded"}` for unauthenticated calls. Details only for admin.

---

## MEDIUM

### F-07: SSE error message leaks internals

**File:** `app/api/chat_routes.py:389`

```python
yield _sse("done", {"error": str(exc), "traceId": trace_id, "sessionId": session_id})
```

**Problem:** `str(exc)` is sent to client. May contain stack traces, DB connection info, file paths.

**Fix:** Return a generic message; log details server-side.

---

### F-08: nginx does not scrub dangerous headers

**File:** `frontend/nginx.conf:14-18`

```nginx
location ~ ^/(auth|chat|me|admin|feedback|settings) {
    proxy_pass http://app:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```

**Problem:** Missing:
- `proxy_set_header Transfer-Encoding "";` — does not scrub TE header
- `proxy_http_version 1.1;` — nginx defaults to HTTP/1.0 for upstream, where chunked is undefined
- `proxy_set_header Connection "";` — hop-by-hop header leak
- No `client_max_body_size` — nginx default is 1MB, but not explicitly set

---

### F-09: Default credentials in production

**File:** `docker-compose.yml:5-7`

```yaml
environment:
  POSTGRES_USER: safe4ai
  POSTGRES_PASSWORD: safe4ai
  POSTGRES_DB: safe4ai
```

**File:** `app/main.py:364`

```python
_DEFAULT_SECRET = "68d543ad135bb451bf0e0a26a7fa6cf5151cb1d0b0c6b1366d18f5543a93927e"
```

**Problem:** Hardcoded default password for Postgres and hardcoded default JWT secret. Only warning, no enforcement.

---

### F-10: CSRF protection not applied to unauthenticated POSTs

**File:** `app/main.py:111-115`

```python
needs_csrf = (
    request.cookies.get("access_token")
    or request.cookies.get("csrf_token")
    or request.url.path == "/auth/login"
)
```

**Problem:** If neither `access_token` nor `csrf_token` cookie is present, and path is not `/auth/login`, CSRF check is skipped. Any unauthenticated POST endpoint is without CSRF protection.

---

## Prioritized Fix Order

| # | Finding | Severity | Effort |
|---|---------|----------|--------|
| 1 | **F-01** CL/TE desync | CRITICAL | Low — ~10 lines of code |
| 2 | **F-03** Port 8000 exposure | CRITICAL | Low — 1 line yaml |
| 3 | **F-02** Chat body size bypass | CRITICAL | Low — remove exemption |
| 4 | **F-04** SSRF | HIGH | Medium — URL validation |
| 5 | **F-05** ASGI monkey-patch | HIGH | Medium — refactor |
| 6 | **F-06** Health info leak | HIGH | Low |
| 7 | **F-08** nginx header scrub | MEDIUM | Low |
| 8 | **F-07** SSE error leak | MEDIUM | Low |
| 9 | **F-09** Default creds | MEDIUM | Low |
| 10 | **F-10** CSRF gap | MEDIUM | Low |
