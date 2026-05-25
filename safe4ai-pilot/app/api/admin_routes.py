"""admin_routes.py — decomposed into focused modules.

Original 854-line god file split into:
  api/document_routes.py    — upload, list, status, delete, reindex, corpus-stats
  api/user_routes.py        — list, create, deactivate
  api/audit_routes.py       — audit-logs, export.csv, stats
  api/review_routes.py      — review-queue list, approve, reject
  api/account_routes.py     — /me (moved here from admin)

Services extracted:
  services/document_service.py  — Qdrant cleanup, BM25 prune
  services/user_service.py      — ghost user, deactivation cascade
  services/stats_service.py     — shared corpus-stats SQL (also used by account_routes)

This file is intentionally empty; it is kept for one release to avoid
hard-breaking any external callers that imported from it directly.
"""
from __future__ import annotations
