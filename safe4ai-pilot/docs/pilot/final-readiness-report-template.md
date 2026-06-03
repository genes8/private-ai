# Final Readiness Report

The primary pilot deliverable. Complete every section. Keep claims grounded in measured data from the pilot. The report ends with a clear recommendation: **stop, repeat, or expand**.

- **Customer:** `<customer>`
- **Pilot window:** `<start>` → `<end>`
- **Prepared by:** `<name>`
- **Date:** `<date>`

## 1. Executive summary

Two to four paragraphs: what was piloted, the headline result, and the recommendation. Written for an executive who will not read the rest.

## 2. Workflow tested

- Workflow: `<selected workflow>`
- Why it was chosen: `<rationale>`
- Example questions users asked: `<list>`
- What was explicitly out of scope: `<list>`

## 3. Data sources and document volume

| Source | File types | Documents | Size | Notes |
|---|---|---|---|---|
| | | | | |

Total documents ingested: `<n>`. OCR/scanned share: `<n>`.

## 4. Users and roles

| Role | Count | Notes |
|---|---|---|
| admin | | |
| pilot_user | | |

SSO used: `<OIDC / none>`.

## 5. Usage and operational metrics

| Metric | Result | Target | Met? |
|---|---|---|---|
| Total queries | | | |
| Typical latency | | | |
| Fallback / "don't know" rate | | | |
| Feedback (helpful %) | | | |
| Cost (tokens / $) | | | |

## 6. Evaluation scores

From `evaluation/offline_eval.py` against the pilot golden set, plus online-monitor trend.

| Evaluation metric | Score | Notes |
|---|---|---|
| Grounding / citation | | |
| Answer relevance | | |
| Retrieval quality | | |

## 7. What the assistant answered well

Concrete examples with the question, the answer, and the cited source.

## 8. What it missed

Concrete failure examples, with root cause where known (missing document, retrieval gap, out-of-scope reasoning, ambiguous question).

## 9. Security and compliance gaps

Summarize findings from `security-review-checklist.md`. Be explicit about items that are deployment-layer responsibilities (WORM/immutable storage) and features not available today (SAML, signed CSV, multi-tenant).

| Gap | Severity | Owner | Path to resolution |
|---|---|---|---|
| | | | |

## 10. Production requirements

What would be required to run this in production: deployment target, hardware/model sizing, user scale, integrations, security pack, support.

## 11. Recommendation

Choose one and justify it:

- ☐ **Stop** — the workflow is not a fit; reasons: `<...>`
- ☐ **Repeat** — promising but needs another iteration; changes: `<...>`
- ☐ **Expand** — proceed to production scope; see `rollout-scope-cost-template.md`.

Recommended next step and date: `<...>`
