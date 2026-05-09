"""Verify that a document has been fully deleted from all storage layers.

Usage:
    python -m scripts.verify_deletion <doc_id>

Checks:
  - PostgreSQL `documents` table
  - PostgreSQL `document_chunks` table
  - Qdrant vector store (scroll API)
  - Filesystem (data/raw/ and data/processed/)

Prints PASS/FAIL per check; exits non-zero if any FAIL.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
from sqlalchemy import text

from app.config import settings
from app.db import engine

_QDRANT_COLLECTION = "documents"
_RAW_DIR = Path("data/raw")
_PROCESSED_DIR = Path("data/processed")


def check_documents_table(doc_id: str) -> bool:
    """PASS if no row with this doc_id exists in `documents`."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM documents WHERE id = :doc_id"),
            {"doc_id": doc_id},
        ).first()
    if row is None:
        print(f"  documents table: PASS (no row for {doc_id})")
        return True
    print(f"  documents table: FAIL (row still exists for {doc_id})")
    return False


def check_document_chunks_table(doc_id: str) -> bool:
    """PASS if no chunk rows exist for this doc_id in `document_chunks`."""
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM document_chunks WHERE document_id = :doc_id"),
            {"doc_id": doc_id},
        ).scalar()
    if count == 0:
        print(f"  document_chunks table: PASS (0 rows for {doc_id})")
        return True
    print(f"  document_chunks table: FAIL ({count} row(s) still exist for {doc_id})")
    return False


def check_qdrant(doc_id: str) -> bool:
    """PASS if Qdrant has no points with payload.doc_id == doc_id."""
    url = f"{settings.qdrant_url}/collections/{_QDRANT_COLLECTION}/points/scroll"
    payload = {
        "filter": {"must": [{"key": "doc_id", "match": {"value": doc_id}}]},
        "limit": 1,
        "with_payload": False,
        "with_vector": False,
    }
    try:
        response = httpx.post(url, json=payload, timeout=15)
        response.raise_for_status()
        points = response.json().get("result", {}).get("points", [])
        if not points:
            print(f"  qdrant: PASS (no points for doc_id={doc_id})")
            return True
        print(f"  qdrant: FAIL ({len(points)}+ point(s) still exist for doc_id={doc_id})")
        return False
    except Exception as exc:
        print(f"  qdrant: FAIL — {exc}")
        return False


def check_filesystem(doc_id: str) -> bool:
    """PASS if no file containing doc_id exists in data/raw/ or data/processed/."""
    found: list[Path] = []
    for directory in (_RAW_DIR, _PROCESSED_DIR):
        if directory.exists():
            found.extend(p for p in directory.iterdir() if doc_id in p.name)
    if not found:
        print(f"  filesystem: PASS (no files for {doc_id})")
        return True
    for f in found:
        print(f"  filesystem: FAIL — file still exists: {f}")
    return False


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.verify_deletion <doc_id>")
        sys.exit(2)

    doc_id = sys.argv[1]
    print(f"Verifying deletion of doc_id={doc_id}\n")

    results = [
        check_documents_table(doc_id),
        check_document_chunks_table(doc_id),
        check_qdrant(doc_id),
        check_filesystem(doc_id),
    ]

    failed = sum(1 for ok in results if not ok)
    if failed:
        print(f"\n{failed} check(s) FAILED.")
        sys.exit(1)
    print("\nAll checks PASSED — document fully deleted.")


if __name__ == "__main__":
    main()
