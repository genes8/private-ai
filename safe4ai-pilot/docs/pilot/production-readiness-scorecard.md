# Production Readiness Scorecard

A structured go/no-go assessment after the pilot. Score each dimension, note gaps, and reach an overall recommendation. Use a 0–3 scale:

- **0** — not ready / not present
- **1** — partial, significant work required
- **2** — adequate for the next stage with minor work
- **3** — production-ready

- **Customer:** `<customer>`
- **Date:** `<date>`
- **Assessor:** `<name>`

## Scorecard

| # | Dimension | What "ready" means | Score (0–3) | Gap / action |
|---|---|---|---|---|
| 1 | Retrieval quality | Relevant passages retrieved for representative queries | | |
| 2 | Answer grounding / citations | Answers cite filename + page + excerpt; ungrounded answers refused | | |
| 3 | Guardrails | Input/content/output filters + blocked terms behave as intended | | |
| 4 | Security & auth | Cookie JWT, RBAC, lockout, headers, rate limits, SSRF-pinned egress verified | | |
| 5 | Observability | OTLP traces, admin stats, audit, feedback, cost all usable for ops | | |
| 6 | Data lifecycle | Ingest, reindex, and delete work; deletion verified across stores | | |
| 7 | Deployment readiness | Chosen target (Compose/Helm/air-gap) reproducible and documented | | |
| 8 | Ops / runbook coverage | Admin can run the system from docs without DB access | | |

**Total:** `<sum>` / 24

## Interpretation

| Total | Reading |
|---|---|
| 20–24 | Strong — proceed to production scope |
| 14–19 | Conditional — close named gaps, then proceed |
| < 14 | Not ready — repeat or stop |

## Known non-features (do not score as gaps to "fix" in the pilot)

These are deferred enterprise candidates, not pilot defects: SAML SSO, signed CSV, app-owned WORM storage, multi-tenant workspaces, vLLM preset. App-owned immutability is a deployment/storage-layer responsibility.

## Overall recommendation

- ☐ Go to production scope (`rollout-scope-cost-template.md`)
- ☐ Conditional go — resolve: `<gaps>`
- ☐ No go — `<reason>`

Top three gaps to close:

1. `<gap>`
2. `<gap>`
3. `<gap>`
