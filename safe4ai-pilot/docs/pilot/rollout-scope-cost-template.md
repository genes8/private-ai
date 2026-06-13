# Rollout Scope and Cost

Use this template when the pilot recommendation is **expand**. It defines the production scope and the cost drivers, and records the deployment / IP-boundary decisions. It is a scoping document — use placeholders rather than invented prices.

- **Customer:** `<customer>`
- **Date:** `<date>`
- **Prepared by:** `<name>`

## 1. Production scale

| Dimension | Pilot | Production target |
|---|---|---|
| Users / seats | | |
| Tier (Evaluation / Team / Enterprise) | | |
| Monthly query volume | | |
| Document count | | |
| Document growth rate | | |
| Workflows in scope | 1 (pilot) | |

## 2. Deployment / IP-boundary decisions

| Decision | Choice | Notes |
|---|---|---|
| Deployment target | ☐ Docker Compose ☐ Kubernetes/Helm ☐ Air-gapped bundle | |
| Safe4AI runtime delivery | Versioned backend + frontend images via private registry or offline bundle | not source by default |
| Customer-owned data layer | documents, Postgres, Qdrant, users, audit logs, local model runtime, backups | confirm customer owns and operates |
| Update channel | private registry pull / offline image bundle | |
| SBOM / security pack | ☐ Yes ☐ No | architecture + data-flow diagrams, threat model, SBOM, vuln scan, dependency/license report |
| Source escrow | ☐ Yes ☐ No | enterprise-only, contract-triggered |

## 3. Model / runtime sizing

| Item | Value |
|---|---|
| Provider mode | local (Ollama) / OpenAI-compatible |
| Chat model | |
| Embedding model | |
| Vision/OCR model (if scanned docs) | |
| Hardware / GPU requirement | |
| Expected concurrency | |

## 4. Cost drivers

Capture the drivers; fill amounts during commercial scoping. Do not quote a price the deal has not agreed.

| Driver | Notes |
|---|---|
| Runtime license / subscription (by tier) | |
| Deployment + onboarding effort | |
| Infrastructure (compute, GPU, storage) — customer-owned | |
| Model/runtime hosting (local vs external provider) | |
| Updates, support, and security patches | |
| Optional enterprise security pack / escrow | |
| Optional readiness-service add-ons | |

## 5. Open work items before production

| Item | Owner | Notes |
|---|---|---|
| | | |

> **Note:** Keep this scope aligned with the commercial deployment model in the canonical roadmap (closed Safe4AI runtime + customer-owned data layer). Do not commit to SAML, signed CSV, multi-tenant workspaces, bundled vLLM operations, or app-owned WORM storage unless they are explicitly added as funded scope.
