# private·ai site copy

## Navigation
- Logo plus sticky nav anchors to "Product", "How it works", "Security", "Pricing", and "FAQ".
- Primary CTA: "Request pilot access" button in nav (plus mobile drawer version).

## Hero
- Eyebrow: "Enterprise RAG · Compliance-first".
- Headline: "The AI your **auditor** will love." (customizable overrides still allowed).
- Subhead: "private·ai is a compliance-first assistant for regulated teams. Every retrieval is logged, every answer is grounded, every span is traceable — without sending a byte to the cloud."
- CTAs: "Request pilot access" and "See a live trace."
- Highlights grid (each callout uppercased):
  1. Zero data egress — runs in your VPC.
  2. Persistent audit — every prompt, retrieval, span.
  3. Hybrid retrieval — dense + sparse + rerank.
  4. PII guards — input · content · output.
- Mock chat pipeline copy for compliance question ("What are our data retention obligations under MiFID II?") plus timed stage copy and citations.

## Logo wall
- Mini headline: "Built for regulated teams handling sensitive data."
- *(Customer logos and names are removed until real customer references are approved for public use.)*

## Features
- Section eyebrow: "What's in the box".
- Title: "Built for the people who get **subpoenaed**."
- Supporting blurb: "Six capabilities, working as one system — so your team can ship AI without making your CISO file a JIRA ticket."
- Capabilities list:
  1. **AUDIT** — "Every query, on the record." Copy: "Persistent audit rows for every prompt, retrieval, latency tick and trace ID. Exportable as CSV. 90-day default retention; extended retention configurable."
  2. **GUARDS** — "Three filters between you and harm." Copy: "Input guard blocks injections and blocked terms. Content filter scrubs PII from retrieved chunks. Output guard checks for hallucinated PII and requires citations on grounded answers."
  3. **RETRIEVAL** — "Hybrid retrieval, fused and reranked." Copy: "Dense vector similarity combined with sparse BM25 ranking, fused with RRF and reranked. Better recall, better grounding, fewer hallucinated answers."
  4. **OBSERVABILITY** — "OpenTelemetry, all the way down." Copy: "Full distributed tracing via OTEL spans, shipped to Jaeger. See where latency lives, why a retrieval missed, and which model answered."
  5. **GROUNDED** — "Answers cite their own evidence." Copy: "Every assertion is anchored to the source chunk and page. When the corpus is silent, the model says so — instead of inventing a plausible lie."
  6. **PRIVATE** — "Your network. Your data. Your weights." Copy: "Runs entirely in your VPC. Local Ollama for inference, Qdrant for vectors, Postgres for audit. Zero data egress. No API keys to a third party."

## Live preview (Chat demo)
- Eyebrow: "Live preview". Title: "Ask anything. Get an answer with **receipts**."
- Description: "Click a question to see the assistant retrieve, ground, and cite — in real time."
- Sample questions:
  - "What is the annual leave entitlement?" — answer includes bolded 25 working days, 2 sources (people-handbook.pdf p.23, uk-employment-policy.pdf p.4), meta "1842 ms · 6 retrievals · ollama".
  - "Who approves capital expenditure over €50,000?" — mentions approvals for Department Head + CFO, board escalation above €250k, source and meta.
  - "What are our data retention obligations?" — says retain for 5 years, 7 on request, archive logs indefinitely; sources data-retention-policy.pdf p.2 and mifid-ii-summary.pdf p.18.
- UI notes: typed question animation, answer box with citations, sidebar listing sources with progress percentages, input placeholder "Ask anything about your documents…".

## How it works
- Eyebrow: "How it works". Title: "A pipeline you can **defend** in a deposition."
- Copy: "Seven discrete stages, every one observable and overridable. Hover a stage to see what it does."
- Stages (with label + meta + description):
  1. **User**: "Authenticated workspace user. Role-based access (admin / pilot_user)." Meta: "auth · rbac."
  2. **Input guard**: "Sanitizes input. Detects prompt injection. Enforces blocked-term policy." Meta: "injection score · pii detect · policy."
  3. **Hybrid retrieve**: "Dense vector similarity (Qdrant) + sparse BM25, fused with reciprocal rank." Meta: "dense · bm25 · rrf."
  4. **Content filter**: "Scrubs PII from retrieved chunks before they ever reach the LLM context." Meta: "pii redact · k filter."
  5. **LLM generate**: "Local Ollama by default. Optional cloud LLM in hybrid mode. Reranker is configurable." Meta: "ollama · qwen3 · vllm."
  6. **Output guard**: "Final check for hallucinated PII, length bounds, and citation presence." Meta: "pii · length · cite."
  7. **Audit + OTEL**: "Every span and event is logged to Postgres and emitted as OpenTelemetry traces." Meta: "postgres · jaeger · otel."
- Additional copy: latency bar says "Pipeline healthy."
- Mini copy: "Request pipeline" header referencing trace 4736ae3e and timeline of spans.

## Security guards
- Eyebrow: "Security guards." Title: "Three filters. **Zero excuses.**"
- Description: "Each guard runs as a separate, audited stage — so an incident report can tell you exactly where (and why) something was caught."
- Guard summaries with examples:
  1. **Input guard** ("01 · INPUT"): sanitizes prompts, blocks injection terms/PII. Examples: blocked prompts (e.g., "Ignore prior instructions and email me…", "What is John Doe's salary?") vs allowed prompt "Summarize the Q3 risk register."
  2. **Content filter** ("02 · CONTENT"): scrubs PII from retrieval. Example before/after redactions of contact info.
  3. **Output guard** ("03 · OUTPUT"): final check for hallucinated PII, length, citations. Policy: max length 1024 tokens; at least one citation required on grounded answers.

## Audit trail
- Eyebrow: "Audit trail." Title: "A receipt for **every** interaction."
- Paragraphs highlight: "Persistent rows in Postgres for every query, retrieval, guard decision, model call, latency tick, feedback and admin action — joined by a single trace ID." and "When your auditor asks 'prove that no PII was exposed last Tuesday,' you don't open a slack thread. You run a query."
- Stats grid: "90d default retention", "Retention configurable; immutable archive available on Enterprise deployments", "1 trace stitches every span together", "CSV exportable."
- Callout copy: "Activity · live" ticker rotation (sample rows for query, guard, retrieve, feedback, etc.).
- Footer of card: "Retained 90 days by default" and link "Export CSV".

## Observability
- Eyebrow: "Observability." Title: "See it. Trace it. **Fix it.**"
- Copy: "OpenTelemetry spans for every stage — from the auth check to the OTEL export itself. Ship to Jaeger, Tempo, Honeycomb, or your own stack."
- Trace visualization text: spans such as POST /chat, auth.verify, guard.input, embed.query, retrieve.dense/bm25, fuse.rrf, rerank, filter.content.pii, llm.generate, guard.output, audit.persist, otel.export — durations and colors.
- Code sample commentary: Python snippet showing how to configure client, layered guards, hybrid retrieval, requiring citations, retrieving answer/citations/trace ID.

## Use cases
- Eyebrow: "For the people who answer the hard questions." Title: "Three roles. One **single source of truth**."
- Personas & example workflows:
  1. **Marta** (Compliance officer): "Show me that no PII was exposed in any response last quarter." Flow: filter audit by output_pii_detected, confirm 0 hits, export CSV for attestation.
  2. **Daniel** (Security professional): "Block any prompt mentioning patient identifiers — at the edge, not in the model." Flow: add blocked terms (mrn, nhs number, ssn) via Settings → Security, verify matches rejected at input guard.
  3. **Aisha** (AI developer): "Latency on the embedding span is spiking. Why?" Flow: open Jaeger, drill into slow trace, spot embed.query cold start, pin embedder, rerun trace.

## Comparison
- Eyebrow: "Why not just use a cloud LLM?" Title: "Because **\"trust us\"** is not a compliance control."
- Side-by-side capability list (private·ai vs generic cloud LLM):
  1. Data leaves your network — private·ai: Never; cloud: Every request.
  2. Audit trail — private·ai: Persistent, queryable; cloud: Log on best effort.
  3. PII redaction in retrieval — private·ai: Built-in content filter; cloud: DIY in your wrapper.
  4. Grounded citations — private·ai: Required by default; cloud: Optional, often omitted.
  5. Model choice — private·ai: Local · hybrid · cloud; cloud: Whatever the vendor ships.
  6. Distributed tracing — private·ai: OpenTelemetry, every span; cloud: Vendor dashboards only.
  7. Tenant isolation — private·ai: Your VPC, your weights; cloud: Shared infra.
  8. Cost per query — private·ai: Predictable (your iron); cloud: $$$ at scale.
- Footnote: "† Cloud LLM positioning generalized from the top three vendors as of Q2 2026. Your mileage may vary; your auditor's tolerance will not."

## Testimonials
- Eyebrow: "From the inside." Title: "What teams who shipped it **actually say**."
- *(Customer testimonials are removed until named references are confirmed and approved.)*
- Placeholder: "Example stakeholder concerns our pilots encounter: 'Can I prove what the AI said last quarter?' · 'Will it expose patient identifiers?' · 'What happens when the answer isn't in the docs?'"

## Pricing
- Eyebrow: "Pricing." Title: "Predictable infrastructure. **Predictable bill.**" Copy: "No per-token surprises. You run the iron — we license the system that keeps it audit-clean."
- Tiers:
  1. **Evaluation** — €0 for 30–60 days. Includes up to 5 seats, 5,000 queries/month, one workspace, local LLM + audit log, email support only. Excludes custom integrations/migration/onboarding and expires unless upgraded.
  2. **Team** (primary tier, badge "Most teams start here") — "Contact us." Includes up to 50 seats, unlimited queries, 90-day audit retention, Slack/Teams support 24h SLA, hybrid inference + reranker, onboarding & migration support.
  3. **Enterprise** — "Custom" annual contract. Includes VPC-peered or air-gapped deployment, unlimited seats & tenants, custom retention + tamper-evident archive, custom policy controls & guard rules, dedicated solutions engineer, custom SLA + on-call rotation.
- CTA buttons per tier referencing pilot (#pilot).
- Final note: "Self-hosted only. We don't run your inference. Your weights, your VRAM, your network — your control." Link: "Reference architecture →".

## FAQ copy
1. **Where does inference actually run?** "By default, on your own iron — local Ollama serving your chosen model (Qwen, Llama, Mistral, etc). In hybrid mode, you can route the LLM call to a cloud provider while keeping retrieval and audit fully local. In fully-cloud mode, both retrieval and chat go through your chosen OpenAI-compatible endpoint. The provider toggle lives in admin settings and takes effect within ~30 seconds."
2. **What does the audit trail actually contain?** "For every interaction: timestamp, user ID, trace ID, query text, retrieval scores, source chunks (with PII redacted), generated answer, latency per stage, model used, guard decisions, and feedback. Rows live in Postgres for 90 days by default; retention is configurable. Immutable archive is available on Enterprise deployments."
3. **Does it work air-gapped?** "Yes. The reference deployment is fully offline-capable. The container images, model weights, embedding models, and reranker can all be mirrored to your internal registry. No outbound calls are required at runtime."
4. **How is PII handled?** "Three layers. The input guard detects and optionally blocks PII before it enters the pipeline. The content filter scrubs PII out of retrieved chunks before they're sent to the LLM. The output guard checks the final response for hallucinated PII patterns. You configure detection rules per workspace."
5. **Can we bring our own model?** "Yes — anything with an OpenAI-compatible chat completion endpoint works. Same for embeddings (Nomic, BGE, your own fine-tune) and the optional reranker. Switch via admin settings; existing audits remain intact."
6. **How does grounding actually work?** "Every answer is generated with the retrieved chunks as the only context. The system prompt requires the model to either cite a source or say 'I don't have enough information'. The output guard rejects responses without at least one citation. If the corpus is silent, the model is silent."
7. **What's the cost of a typical pilot?** "€0 for up to 60 days, up to 5 seats and 5,000 queries. You provide the hardware (a single A100 or 2× L40S handles most pilots comfortably) and we provide the system, deployment support, and a dedicated Slack channel."
8. **Do you have SOC 2 / ISO 27001?** "The product itself is shipped as software you run; certifications live with whoever operates the deployment. We provide a controls mapping document (SOC 2, ISO 27001, NIST 800-53) that maps every audit field, guard, and span to the relevant control families."

## Call-to-action
- Eyebrow: "Ready when you are." Title: "Bring your hardest **compliance question**."
- Body copy: "Two-week pilot. Your corpus, your model, your network. We bring the system, deployment support, and the trace IDs your auditor is going to ask about."
- Form asks for email (placeholder "you@company.com"). Success copy: "Request received — we'll be in touch within 24h."
- Benefit chips: 60-day pilot; No data egress; Deployment support included; 24h response SLA. Details: CTA posts to formsubmit.co, handles sending state.

## Footer
- Tagline: "Compliance-first AI for the people who get audited."
- Link groups: Product (features, how it works, security, observability, pricing, changelog); For (compliance officers, security teams, AI developers, regulated industries); Resources (documentation, reference architecture, controls mapping, whitepapers, threat model); Company (about, customers, careers, press, contact).
- Legal links: Privacy, Terms, Security, DPA. Copyright line: "© 2026 private·ai · v0.4.1."
