# Workflow Selection

Use this template after discovery to choose the **one** workflow the pilot will test. A focused pilot produces a clear go/no-go signal; a broad one produces noise.

- **Customer:** `<customer>`
- **Date:** `<date>`
- **Decided by:** `<names>`

## 1. Candidate workflows

List the workflows surfaced during discovery and score each. Use a simple 1–5 scale (5 = best).

| # | Candidate workflow | Business value | Document availability | RAG answerability | Risk if wrong | Measurability | Total |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |

Scoring guidance:

- **Business value** — how much time/cost/risk it removes.
- **Document availability** — are the source documents accessible, complete, and in supported formats (`.pdf`, `.docx`, `.xlsx`, `.txt`, scanned PDF via OCR)?
- **RAG answerability** — can answers be grounded in retrieved passages, or do they need reasoning/computation the platform does not do?
- **Risk if wrong** — lower score for workflows where a wrong answer is costly and hard to catch (favour workflows where users can verify).
- **Measurability** — can we define success criteria and measure them in 6–8 weeks?

## 2. Selected workflow

| Item | Value |
|---|---|
| Chosen workflow | `<workflow>` |
| Why this one | |
| Primary users | |
| Example questions the assistant must answer | |
| Out of scope for this pilot | |

## 3. Success criteria

Define measurable criteria up front; these become report metrics.

| Criterion | Target | How measured |
|---|---|---|
| Answer grounding / citation rate | e.g. ≥ `<n>`% of answers cite a source | SSE citation events + spot review |
| Answer usefulness | e.g. ≥ `<n>`% rated helpful | feedback capture |
| Fallback / "I don't know" rate | within `<range>` | admin stats |
| Latency (typical query) | ≤ `<n>` s | OTLP traces / admin stats |
| Evaluation score on golden set | ≥ `<n>` | `evaluation/offline_eval.py` |

> **Note:** A high fallback rate is not automatically a failure — refusing to answer ungrounded questions is a safety feature. Interpret it against the workflow.

## 4. Risks and assumptions

| Risk / assumption | Mitigation |
|---|---|
| | |
