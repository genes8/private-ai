# Discovery Questionnaire

Use this template at the **start** of a pilot engagement to capture what the customer needs and whether Safe4AI is a fit. Fill one copy per customer. Keep answers factual; this document feeds workflow selection, data intake, and the final readiness report.

- **Customer:** `<customer>`
- **Date:** `<date>`
- **Completed by:** `<name / role>`
- **Safe4AI contact:** `<name>`

## 1. Business context

| Question | Answer |
|---|---|
| What problem are you trying to solve with private AI? | |
| Who feels this pain today (team/role)? | |
| What does success look like in 6–8 weeks? | |
| What happens if you do nothing? | |
| Is there a deadline or external driver (audit, contract, launch)? | |

## 2. Target workflow

| Question | Answer |
|---|---|
| Describe the single workflow you most want to pilot. | |
| What question(s) would users ask the assistant? | |
| Where do the answers live today (documents, people, systems)? | |
| How is this done manually now, and how long does it take? | |
| How will you know the assistant's answer is good enough? | |

> **Note:** A pilot tests **one** workflow well, not many shallowly. Capture additional candidate workflows here, but selection happens in `workflow-selection-template.md`.

## 3. Documents and data

| Question | Answer |
|---|---|
| What document types are involved? (`.pdf`, `.docx`, `.xlsx`, `.txt`, scanned PDFs) | |
| Approximate number of documents and total size? | |
| Are any documents scanned/image-only (need OCR)? | |
| How sensitive is this data? (public / internal / confidential / regulated) | |
| Any data that must **not** be ingested for the pilot? | |
| Who owns/approves use of this data? | |

## 4. Users and roles

| Question | Answer |
|---|---|
| How many pilot users? | |
| Who are the admins vs. day-to-day users? | |
| Do users need SSO? (Safe4AI supports **OIDC** today — SAML is not available.) | |
| Any access restrictions between users? | |

> **Note:** Roles are `admin` and `pilot_user`. There is no multi-tenant or per-project access model in the pilot platform.

## 5. Security and compliance context

| Question | Answer |
|---|---|
| What regulatory regimes apply? (e.g. GDPR, HIPAA, sector-specific) | |
| Must inference stay fully on-prem / air-gapped? | |
| Are there data residency requirements? | |
| Is a security/architecture review required before go-live? | |
| Do you need a threat model / SBOM / dependency report? | |

## 6. Deployment preferences

| Question | Answer |
|---|---|
| Preferred model provider: local (Ollama) or an OpenAI-compatible endpoint? | |
| If local, what hardware/GPU is available? | |
| Preferred deployment form: Docker Compose, Kubernetes/Helm, or air-gapped bundle? | |
| Who operates the infrastructure during the pilot (customer or Safe4AI)? | |

> **Note:** "Data never leaves your network" only holds in **local / on-prem mode**. If an external OpenAI-compatible provider is chosen, queries leave the customer network to that provider.

## 7. Decision and next step

| Item | Answer |
|---|---|
| Is there an executive sponsor? | |
| Budget owner / commercial contact? | |
| Tier of interest: Evaluation / Team / Enterprise | |
| Agreed next step + date | |
