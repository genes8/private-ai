# Enterprise Security Pack

Date: 2026-06-12
Audience: customer security reviewers

This folder is the customer-ready security-pack index for Safe4AI Enterprise
reviews. Release-generated evidence files are attached to each GitHub release;
static reviewer references live here.

## Static artifacts

| Artifact | File |
|---|---|
| Data-flow diagram | `docs/security-pack/data-flow-diagram.md` |
| Threat model | `docs/security-pack/threat-model.md` |
| Audit-log and agent trail field reference | `docs/security-pack/audit-log-reference.md` |
| Backup, restore, and deletion verification | `docs/security-pack/backup-restore-deletion-verification.md` |
| Controls mapping | `docs/security-pack/controls-mapping.md` |
| WORM storage guide | `docs/security-pack/worm-storage-guide.md` |
| Image signing verification | `docs/security-pack/image-signing-verification.md` |

## Per-release evidence

The release workflow attaches these files to versioned GitHub releases:

- Backend and frontend SPDX SBOMs.
- Backend and frontend Trivy SARIF vulnerability reports.
- Backend and frontend dependency/license reports.
- Signed backend and frontend image references.

## Boundary statement

Safe4AI records evidence in the customer environment. Uploaded documents, raw
files, PostgreSQL, Qdrant, users, audit logs, feedback, local models, backups,
and immutable retention remain customer-owned controls.
