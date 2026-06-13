# Enterprise WORM Storage Guide

Date: 2026-06-12
Audience: Enterprise storage and compliance owners

Safe4AI writes tamper-evident audit archive files, but it does not itself
provide WORM or immutable storage. Immutable retention is a storage-layer
control owned by the customer.

## What Safe4AI provides

During audit retention cleanup, Safe4AI writes:

- JSONL archive files containing expired audit rows.
- Manifest files with HMAC-chain evidence.
- No plaintext secrets, passwords, JWTs, session cookies, or API keys.

The default archive path is:

```text
data/audit-archive
```

## Customer storage patterns

Approved options include:

- Object storage with retention lock, such as S3 Object Lock or equivalent.
- Immutable backup target controlled by the customer backup platform.
- Filesystem snapshot technology with retention lock and restricted admin
  access.

## Recommended flow

1. Mount `data/audit-archive` to a durable customer-owned volume.
2. Sync archive files and manifests to the immutable target.
3. Apply retention lock according to customer policy.
4. Restrict delete/write permissions to the minimum operator group.
5. Test retrieval of an archived JSONL file and manifest before go-live.

## Verification evidence

Retain:

- Storage policy name and retention period.
- Example locked object or snapshot identifier.
- Hash of one archive JSONL file and its manifest.
- Operator approval for retention and legal hold behavior.

## Non-claim

Safe4AI can produce tamper-evident archives. It cannot guarantee immutability
unless the customer storage layer enforces WORM retention.
