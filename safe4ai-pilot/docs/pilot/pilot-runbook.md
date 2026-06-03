# Pilot Runbook

The operating playbook for running a Safe4AI pilot from provisioning to close-out. Follow top to bottom; record outcomes in the engagement folder.

- **Customer:** `<customer>`
- **Workflow:** `<selected workflow>`
- **Pilot window:** `<start>` → `<end>`
- **Operator:** `<name>`

## 1. Provision

- [ ] Choose tier (Evaluation / Team / Enterprise) and set seat cap + monthly query quota. (Evaluation defaults: 5 seats, 5,000 queries/month.)
- [ ] Set tier expiry (`tierExpiresAt`) to the pilot end date if the pilot is time-boxed.
- [ ] Create the admin account.
- [ ] Create `pilot_user` accounts (or configure OIDC SSO if used).
- [ ] Confirm the deployment form chosen in the security review (Compose / Helm / air-gap) is running and healthy (`/health`).

## 2. Configure the assistant

- [ ] Select provider mode: local (Ollama) or OpenAI-compatible endpoint.
- [ ] Confirm chat, embedding, and (if scanned docs) vision/OCR models are available.
- [ ] Set blocked terms appropriate to the customer.
- [ ] Confirm security settings (rate limits, lockout) match the security review.

## 3. Ingest the corpus

- [ ] Upload documents per `data-inventory-template.md` (`.pdf`, `.docx`, `.xlsx`, `.txt`, scanned PDF).
- [ ] Confirm each document reaches complete status in the admin document list.
- [ ] Run verification queries; confirm grounded answers cite filename + page + excerpt.
- [ ] Re-ingest / reindex any document that failed or returned poor retrieval.

## 4. Operate during the pilot

- [ ] Hold a kickoff so users know the target workflow and how to give feedback.
- [ ] Encourage thumbs-up/down feedback on answers (captured for the admin feedback view).
- [ ] Monitor daily via admin Overview/Activity, audit, feedback, and cost/stats pages.
- [ ] Watch quota and tier-expiry; top up seats/quota or extend expiry as agreed.
- [ ] Observe traces in Jaeger (OTLP) for latency or fallback anomalies.
- [ ] Triage anything routed to the human-review queue.

## 5. Evaluate

- [ ] Curate or extend `evaluation/golden_dataset.json` with representative pilot questions + expected sources.
- [ ] Run offline evaluation: `python evaluation/offline_eval.py` and record scores.
- [ ] Run the online monitor (`evaluation/online_monitor.py`) to track live quality trends.
- [ ] Attach evaluation output to the final readiness report.

## 6. Deployment / IP-boundary operating notes

Record how the pilot is actually deployed; this informs the rollout scope.

| Item | Value |
|---|---|
| Packaged form in operation | Compose / Helm / air-gap |
| Safe4AI-delivered runtime (images/version) | `<image:tag>` |
| Customer-owned data layer location | documents, Postgres, Qdrant, users, audit, model runtime, backups |
| Who applies updates | customer / Safe4AI |

> **Note:** The customer owns the data layer; Safe4AI delivers a runnable runtime (versioned images), not source by default.

## 7. Close-out

- [ ] Snapshot metrics: query volume, latency, fallback rate, feedback, cost, evaluation scores.
- [ ] Complete `final-readiness-report-template.md`.
- [ ] Complete `production-readiness-scorecard.md`.
- [ ] If not continuing: per agreement, delete pilot data and verify deletion across documents, Postgres, Qdrant vectors, semantic cache, raw files, jobs, and BM25 state.
- [ ] Export the audit CSV / JSONL archive for the customer's records if required.
- [ ] Schedule the readout: present recommendation (stop / repeat / expand) and rollout scope.
