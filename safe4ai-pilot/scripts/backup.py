"""Backup script: pg_dump, Qdrant snapshot, and raw-file archive.

Run with: python -m scripts.backup

All steps are attempted even if earlier ones fail.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.config import settings

_COLLECTION = "documents"
_BACKUP_ROOT = Path("data/backups")
_RAW_ROOT = Path("data/raw")


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def backup_postgres(ts: str) -> bool:
    """Dump PostgreSQL to a timestamped SQL file."""
    dest = _BACKUP_ROOT / f"pg_dump_{ts}.sql"
    _BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(  # noqa: S603, S607
            ["pg_dump", settings.postgres_url, "-f", str(dest)],
            capture_output=True,
            check=True,
        )
        print(f"pg_dump: SUCCESS → {dest}")
        return True
    except Exception as exc:
        print(f"pg_dump: FAIL — {exc}")
        return False


def backup_qdrant(ts: str) -> bool:
    """Trigger a Qdrant snapshot via the REST API."""
    url = f"{settings.qdrant_url}/collections/{_COLLECTION}/snapshots"
    try:
        response = httpx.post(url, timeout=30)
        if response.status_code in (200, 201):
            print(f"qdrant_snapshot: SUCCESS — {response.json()}")
            return True
        print(f"qdrant_snapshot: FAIL — status {response.status_code} {response.text}")
        return False
    except Exception as exc:
        print(f"qdrant_snapshot: FAIL — {exc}")
        return False


def backup_raw_files(ts: str) -> bool:
    """Copy data/raw/ to a timestamped backup directory."""
    dest = _BACKUP_ROOT / f"raw_{ts}"
    try:
        if _RAW_ROOT.exists():
            shutil.copytree(str(_RAW_ROOT), str(dest))
            print(f"raw_backup: SUCCESS → {dest}")
        else:
            print(f"raw_backup: SKIP — {_RAW_ROOT} does not exist")
        return True
    except Exception as exc:
        print(f"raw_backup: FAIL — {exc}")
        return False


def main() -> None:
    ts = _timestamp()
    results = [
        backup_postgres(ts),
        backup_qdrant(ts),
        backup_raw_files(ts),
    ]
    failed = sum(1 for ok in results if not ok)
    if failed:
        print(f"\n{failed} step(s) failed.")
        sys.exit(1)
    print("\nAll backup steps completed successfully.")


if __name__ == "__main__":
    main()
