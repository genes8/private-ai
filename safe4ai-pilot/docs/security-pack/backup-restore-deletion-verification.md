# Backup, Restore, and Deletion Verification

Date: 2026-06-12
Audience: operators and security reviewers

Safe4AI stores customer data in PostgreSQL, Qdrant, filesystem volumes, and
the audit archive directory. Backup and restore are customer platform
responsibilities.

## Backup scope

Back up these stores together:

- PostgreSQL `safe4ai` database.
- Qdrant collection storage or snapshots.
- `data/raw`.
- `data/processed`.
- `data/index_config`.
- `data/audit-archive`.
- Ollama model volume, if local model mode is used and rebuild time matters.

## Backup cadence

Minimum pilot cadence:

- Daily PostgreSQL dump.
- Daily Qdrant snapshot.
- Daily file-volume backup.
- Audit archive sync after retention cleanup runs.

Enterprise cadence is set by contract and customer policy.

## Restore drill

Run this drill before go-live and after major version upgrades:

1. Restore PostgreSQL into an isolated environment.
2. Restore Qdrant snapshot into the same environment.
3. Restore file volumes.
4. Start the exact Safe4AI release image tags used in production.
5. Run `/health`.
6. Confirm an admin can list documents, run one document-backed query, export
   audit logs, and view ingestion status.

## Deletion verification

After deleting a document, run:

```bash
curl -fsS -b cookies.txt \
  https://<host>/admin/documents/<document-id>/verify-deletion
```

The response is suitable for a deletion evidence packet when `clean` is true.
It checks known remnants in PostgreSQL chunks, Qdrant vectors, ingestion jobs,
semantic cache, and in-memory BM25 state.

## Evidence to retain

- Timestamped restore drill notes.
- Qdrant snapshot identifiers.
- PostgreSQL backup identifiers.
- Audit archive manifest files.
- Deletion verification JSON responses.

Do not store customer document content in the evidence packet unless the
customer policy explicitly requires it.
