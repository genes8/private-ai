# Security Review Checklist

Use this template before a pilot goes live to confirm the security posture and to record the deployment / IP-boundary decisions that shape any later production rollout. Mark each item and add notes.

- **Customer:** `<customer>`
- **Date:** `<date>`
- **Reviewer:** `<name>`

## 1. Platform security controls (already in the product)

| Control | Present | Notes |
|---|---|---|
| Cookie-based JWT auth (HTTP-Only cookie; token never in response body) | ☐ | |
| Role-based access control (`admin`, `pilot_user`) | ☐ | |
| Brute-force login lockout | ☐ | |
| Security headers on responses | ☐ | |
| Rate limiting | ☐ | |
| Upload validation (extension + declared MIME + magic-byte MIME) | ☐ | |
| Input guard / content filter / output filter | ☐ | |
| Configurable blocked terms | ☐ | |
| SSRF validation + pinned outbound transport for provider & OIDC calls | ☐ | |
| Audit logging for chat queries (`chat_query`) and provider changes (`settings_provider_change`) | ☐ | |
| Audit CSV export | ☐ | |
| Tamper-evident JSONL audit archive before retention cleanup | ☐ | |
| OIDC SSO | ☐ | |

## 2. Explicitly out of scope (do not represent as available)

| Item | Status | If the customer needs it |
|---|---|---|
| SAML SSO | Not available (OIDC only) | Enterprise candidate; not in pilot |
| Signed / tamper-evident **CSV** | Not available (CSV export is unsigned) | JSONL audit archive is the tamper-evident artifact |
| App-owned WORM / immutable storage | Not an app guarantee | Provided by the storage layer at deployment |
| Multi-tenant workspaces | Not available | One workspace / evaluation boundary |
| Hard vLLM support | Reachable only as OpenAI-compatible provider | No preset/runbook yet |

## 3. Data flow review

| Question | Answer |
|---|---|
| Model provider mode: local (Ollama) or OpenAI-compatible endpoint? | |
| If OpenAI-compatible: does query data leave the customer network? To where? | |
| Where do documents, Postgres, and Qdrant physically reside? | |
| Are backups encrypted and access-controlled? | |
| Is observability (OTLP/Jaeger) kept inside the customer environment? | |

> **Note:** "Data never leaves your network" holds only in local/on-prem mode. State the actual data flow for the chosen provider mode.

## 4. Deployment / IP-boundary decisions

These decisions drive any production rollout (Phase E). Capture them now — this is a decision record, not implementation.

| Decision | Choice | Notes |
|---|---|---|
| Deployment target | ☐ Docker Compose ☐ Kubernetes/Helm ☐ Air-gapped bundle | |
| Customer-owned data layer (documents, Postgres, Qdrant, users, audit logs, local model runtime, backups) | ☐ Confirmed customer-owned | |
| Safe4AI runtime delivery (versioned images, not source by default) | ☐ Acknowledged | |
| SBOM / security pack required? | ☐ Yes ☐ No | architecture + data-flow diagram, threat model, SBOM, vuln scan, dependency/license report |
| Source escrow required? | ☐ Yes ☐ No | enterprise-only, contract-triggered |

## 5. Sign-off

| Role | Name | Date | Approved |
|---|---|---|---|
| Customer security reviewer | | | ☐ |
| Safe4AI lead | | | ☐ |
