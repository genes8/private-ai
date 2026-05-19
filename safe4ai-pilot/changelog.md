# Changelog

## 2025-05-19 — Security Audit Fixes

Full middleware security audit performed. 10 findings identified and fixed across 7 files.

### CRITICAL fixes
- **F-01** (CL/TE desync): `app/main.py` — Reject requests with both `Content-Length` and `Transfer-Encoding` headers (RFC 7230 §3.3.3 compliance)
- **F-02** (body size bypass): `app/main.py` — Remove `/chat` and `/chat/stream` exemption from chunked body size checks
- **F-03** (port exposure): `docker-compose.yml` — Bind port 8000 to `127.0.0.1` only, preventing direct Uvicorn access from outside

### HIGH fixes
- **F-04** (SSRF): `app/security/url_validator.py` (new), `app/api/admin_routes.py` — Validate provider URLs against private/reserved IP ranges before making outbound HTTP requests
- **F-05** (ASGI internals): `app/main.py` — Replace `_receive`/`_stream_consumed` monkey-patching with safe `_body` assignment; ensure `SpooledTemporaryFile` cleanup on all error paths
- **F-06** (health info leak): `app/main.py` — Health endpoint no longer exposes internal error messages, hostnames, or connection strings

### MEDIUM fixes
- **F-07** (SSE error leak): `app/api/chat_routes.py` — Stream error events return generic "Pipeline error" instead of raw exception strings
- **F-08** (nginx hardening): `frontend/nginx.conf` — Add `proxy_http_version 1.1`, scrub `Transfer-Encoding`/`Connection` hop-by-hop headers, set `client_max_body_size 50m`
- **F-09** (default creds): `app/main.py` — Block startup with default credentials when `enforce_https=True` (production mode)
- **F-10** (CSRF gap): `app/main.py` — Require CSRF double-submit token for all unsafe HTTP methods, regardless of authentication state

### Files changed
- `app/main.py` — F-01, F-02, F-05, F-06, F-09, F-10
- `app/api/admin_routes.py` — F-04
- `app/api/chat_routes.py` — F-07
- `app/security/url_validator.py` — F-04 (new file)
- `frontend/nginx.conf` — F-08
- `docker-compose.yml` — F-03
- `tests/test_chat.py` — Updated `test_chat_no_auth_returns_401` to accept 403 (CSRF before auth)

### New files
- `audit-code-report.md` — Full security audit report with detailed findings

### Test results
- 233 tests passing, 0 failures
