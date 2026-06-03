# Data Inventory

Use this template to inventory the documents that will be ingested for the pilot. It drives ingestion planning, OCR needs, and the "data sources and volume" section of the final report.

- **Customer:** `<customer>`
- **Workflow:** `<selected workflow>`
- **Date:** `<date>`
- **Owner:** `<name>`

## 1. Supported formats

The platform ingests `.pdf`, `.docx`, `.xlsx`, and `.txt`. Scanned/image-only PDFs are handled via the OCR path. Files outside these types must be converted before ingestion, or excluded.

## 2. Source inventory

| # | Source / set | File type(s) | Approx. count | Approx. size | Owner | Sensitivity | OCR needed? | Ingestion status |
|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | public/internal/confidential/regulated | yes/no | pending/ingested/failed |
| 2 | | | | | | | | |
| 3 | | | | | | | | |

## 3. Exclusions

List documents or data deliberately **not** ingested for the pilot, and why (sensitivity, ownership, out of scope).

| Item | Reason for exclusion |
|---|---|
| | |

## 4. Data handling notes

| Item | Answer |
|---|---|
| Where do source files physically live during the pilot? | |
| Who can upload documents (admins)? | |
| Is any PII present that needs special handling? | |
| Retention expectation for ingested data after the pilot? | |
| Deletion/verification required at pilot close? (see pilot-runbook close-out) | |

> **Note:** In local/on-prem mode, ingested documents, the PostgreSQL database, and the Qdrant vector index all stay in the customer's environment. Immutable/WORM retention, if required, is provided by the storage layer — it is not an app guarantee.

## 5. Ingestion verification

After ingestion, confirm for each source:

- [ ] Document appears in admin document list with status complete.
- [ ] A test query returns a grounded answer citing the expected file (filename + page + excerpt).
- [ ] Scanned documents produced searchable text (OCR succeeded).
