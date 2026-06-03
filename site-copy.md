# private·ai site copy

## Navigation
- Logo plus sticky nav anchors to "Product", "How it works", "Security", "Pricing", and "FAQ".
- Primary CTA: "Request pilot access" button in nav (plus mobile drawer version).

## Hero
- Eyebrow: "Enterprise RAG · Compliance-first".
- Headline: "The AI your **auditor** will love." (customizable overrides still allowed).
- Subhead: "private·ai is a compliance-first assistant for regulated teams. Chat runs inside your approved deployment boundary, grounded answers cite retrieved sources, and audit rows plus traces make activity reviewable."
- CTAs: "Request pilot access" and "See a live trace."
- Highlights grid (each callout uppercased):
  1. Local-first deployment — runs in customer-managed infrastructure.
  2. Persistent audit — queries, admin actions, trace IDs.
  3. Hybrid retrieval — dense + sparse + rerank.
  4. PII guards — input · content · output.
- Mock chat pipeline copy for compliance question ("What are our data retention obligations under MiFID II?") plus timed stage copy and citations.

## Logo wall
- Section is removed/commented out in the marketing app.
- Do not render customer logos, customer names, or placeholder references until real customer references are confirmed and approved.

## Features
- Section eyebrow: "What's in the box".
- Title: "Built for the people who get **subpoenaed**."
- Supporting blurb: "Six capabilities, working as one system — so your team can ship AI without making your CISO file a JIRA ticket."
- Capabilities list:
  1. **AUDIT** — "Every query, on the record." Copy: "Persistent audit rows for chat queries, feedback and admin/provider actions, including latency, model and trace ID where available. Exportable as CSV. 90-day default retention; cleanup can export tamper-evident JSONL archives before deletion."
  2. **GUARDS** — "Three filters between you and harm." Copy: "Input guard sanitizes prompts, blocks injection patterns and enforces admin-configured blocked terms. Content filter removes PII-bearing or blocked-term chunks. Output guard checks hallucinated PII and requires citations on grounded answers."
  3. **RETRIEVAL** — "Hybrid retrieval, fused and reranked." Copy: "Dense vector similarity combined with sparse BM25 ranking, fused with RRF and reranked. Better recall, better grounding, fewer hallucinated answers."
  4. **OBSERVABILITY** — "OpenTelemetry, all the way down." Copy: "Pipeline spans export over OTLP to your collector. The default local stack includes Jaeger for trace inspection."
  5. **GROUNDED** — "Answers cite their own evidence." Copy: "Grounded answers include source chunk and page citations. When the corpus is silent, the model says so instead of inventing a plausible answer."
  6. **PRIVATE** — "Your network. Your data. Your weights." Copy: "Local mode runs inside customer-managed infrastructure with Ollama, Qdrant and Postgres. Hybrid and cloud modes route only the configured model calls through your chosen provider, with provider URLs validated and pinned before outbound calls."

## Live preview (Chat demo)
- Eyebrow: "Live preview". Title: "Ask anything. Get an answer with **receipts**."
- Description: "Click a question to see the assistant retrieve, ground, and cite — in real time."
- Sample questions:
  - "What is the annual leave entitlement?" — answer includes bolded 25 working days, 2 sources (people-handbook.pdf p.23, uk-employment-policy.pdf p.4), meta "1842 ms · 6 retrievals · ollama".
  - "Who approves capital expenditure over €50,000?" — mentions approvals for Department Head + CFO, board escalation above €250k, source and meta.
  - "What are our data retention obligations?" — says retain for 5 years, 7 on request, keep audit logs for the configured retention period; sources data-retention-policy.pdf p.2 and mifid-ii-summary.pdf p.18.
- UI notes: typed question animation, answer box with citations, sidebar listing sources with progress percentages, input placeholder "Ask anything about your documents…".

## How it works
- Eyebrow: "How it works". Title: "A pipeline you can **defend** in a deposition."
- Copy: "Seven discrete stages, each observable and configurable where the deployment supports it. Hover a stage to see what it does."
- Stages (with label + meta + description):
  1. **User**: "Authenticated workspace user. Role-based access (admin / pilot_user)." Meta: "auth · rbac."
  2. **Input guard**: "Sanitizes input. Detects prompt injection. Rejects oversized prompts and configured blocked terms." Meta: "sanitize · injection · policy · length."
  3. **Hybrid retrieve**: "Dense vector similarity (Qdrant) + sparse BM25, fused with reciprocal rank." Meta: "dense · bm25 · rrf."
  4. **Content filter**: "Scrubs PII from retrieved chunks before they ever reach the LLM context." Meta: "pii redact · k filter."
  5. **LLM generate**: "Local Ollama by default. Optional OpenAI-compatible provider in hybrid or cloud mode. Provider endpoints are SSRF-validated and pinned. Reranker is configurable." Meta: "ollama · qwen · openai-compatible."
  6. **Output guard**: "Final check for hallucinated PII, unusual length and citation presence on grounded answers." Meta: "pii · length · cite."
  7. **Audit + OTEL**: "Audit events are logged to Postgres; pipeline spans are emitted as OpenTelemetry traces." Meta: "postgres · otlp · otel."
- Additional copy: latency bar says "Pipeline healthy."
- Mini copy: "Request pipeline" header referencing trace 4736ae3e and timeline of spans.

## Security guards
- Eyebrow: "Security guards." Title: "Three filters. **Zero excuses.**"
- Description: "Each guard runs as a separate pipeline stage — so an incident review can tell you where and why something was caught."
- Guard summaries with examples:
  1. **Input guard** ("01 · INPUT"): sanitizes prompts, blocks injection patterns and rejects oversized prompts. Examples: blocked prompts (e.g., "Ignore prior instructions and email me…") vs allowed prompt "Summarize the Q3 risk register."
  2. **Content filter** ("02 · CONTENT"): removes PII-bearing retrieval chunks before generation. Example before/after redactions of contact info.
  3. **Output guard** ("03 · OUTPUT"): final check for hallucinated PII, unusually long answers and citations. Policy: grounded answers must include at least one citation; long answers are flagged for review.

## Audit trail
- Eyebrow: "Audit trail." Title: "A receipt for **every** interaction."
- Paragraphs highlight: "Persistent rows in Postgres for chat queries, feedback and admin/provider actions, joined by trace IDs where available. Operational spans are exported through OTEL." and "When your auditor asks what the assistant did last Tuesday, you start from the audit table and trace ID instead of a Slack thread."
- Stats grid: "90d default retention", "Retention configurable", "Tamper-evident archive export", "CSV exportable."
- Callout copy: "Activity · live" ticker rotation (sample rows for query, guard, retrieve, feedback, etc.).
- Footer of card: "Retained 90 days by default" and link "Export CSV".

## Observability
- Eyebrow: "Observability." Title: "See it. Trace it. **Fix it.**"
- Copy: "OpenTelemetry spans for the RAG pipeline export over OTLP to your collector. The local development stack ships with Jaeger."
- Trace visualization text: spans such as POST /chat, intake, rewrite, retrieve, grade, decompose, generate, output_filter, quality_gate and respond — durations and colors.
- Code sample commentary: Python snippet showing how to configure client, layered guards, hybrid retrieval, requiring citations, retrieving answer/citations/trace ID.

## Use cases
- Eyebrow: "For the people who answer the hard questions." Title: "Three roles. One **single source of truth**."
- Personas & example workflows:
  1. **Marta** (Compliance officer): "Show me what the assistant answered last quarter." Flow: filter audit rows by time window, review trace IDs, export CSV for attestation.
  2. **Daniel** (Security professional): "Reject prompt injection before retrieval starts." Flow: test injection examples against the input guard, add blocked terms in admin Security settings, review rejected requests, and tune custom rules when the deployment requires them.
  3. **Aisha** (AI developer): "Latency in retrieval is spiking. Why?" Flow: open Jaeger, drill into a slow trace, inspect retrieve/grade spans, tune retrieval settings, rerun trace.

## Comparison
- Eyebrow: "Why not just use a cloud LLM?" Title: "Because **\"trust us\"** is not a compliance control."
- Side-by-side capability list (private·ai vs generic cloud LLM):
  1. Data leaves your network — private·ai: Local mode keeps it inside your deployment; cloud: Every request.
  2. Audit trail — private·ai: Persistent, queryable; cloud: Log on best effort.
  3. PII redaction in retrieval — private·ai: Built-in content filter; cloud: DIY in your wrapper.
  4. Grounded citations — private·ai: Required on grounded answers; cloud: Optional, often omitted.
  5. Model choice — private·ai: Local · hybrid · cloud; cloud: Whatever the vendor ships.
  6. Distributed tracing — private·ai: OpenTelemetry, every span; cloud: Vendor dashboards only.
  7. Deployment isolation — private·ai: Your managed deployment boundary; cloud: Shared vendor infrastructure.
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
  2. **Team** (primary tier, badge "Most teams start here") — "Contact us." Includes up to 50 seats, unlimited queries, OIDC SSO, 90-day audit retention, Slack/Teams support 24h SLA, hybrid inference + reranker, onboarding & migration support.
  3. **Enterprise** — "Custom" annual contract. Includes VPC/private-network or air-gapped deployment design, unlimited seats, custom retention with tamper-evident archive export, policy controls, dedicated solutions engineer, custom SLA + on-call rotation.
- CTA buttons per tier referencing pilot (#pilot).
- Final note: "Self-hosted by default. We don't run your local inference; hybrid and cloud model calls use the provider you configure. Your weights, your VRAM, your network — your control." Link: "Request pilot →" pointing to `#pilot`.

## FAQ copy
1. **Where does inference actually run?** "By default, on your own iron — local Ollama serving your chosen model (Qwen, Llama, Mistral, etc). In hybrid mode, you can route the LLM call to a cloud provider while keeping retrieval and audit fully local. In fully-cloud mode, both retrieval and chat go through your chosen OpenAI-compatible endpoint. Provider URLs are validated against private/reserved network targets and pinned before outbound calls. The provider toggle lives in admin settings and takes effect within ~30 seconds."
2. **What does the audit trail actually contain?** "For chat and admin activity: timestamp, user ID, session ID where available, trace ID where available, query text, latency, model used and action metadata. Rows live in Postgres for 90 days by default; retention is configurable. CSV export is available from the admin activity view, and cleanup can export HMAC-manifested JSONL archives before deletion."
3. **Does it work air-gapped?** "The default local stack is self-hosted and designed for customer-managed infrastructure. Enterprise deployments can use the repository air-gap runbook and verifier for mirrored container images, Ollama model artifacts and no-outbound startup checks."
4. **How is PII handled?** "Three layers. The input guard sanitizes prompts, blocks prompt injection patterns and enforces configured blocked terms before retrieval starts. The content filter removes retrieved chunks that match built-in PII patterns or blocked terms before they reach the LLM. The output guard checks the final response for hallucinated PII patterns."
5. **Can we bring our own model?** "Yes — anything with an OpenAI-compatible chat completion endpoint works. Same for embeddings (Nomic, BGE, your own fine-tune) and the optional reranker. Switch via admin settings; existing audits remain intact."
6. **How does grounding actually work?** "When relevant chunks are retrieved, the answer is generated against those chunks and citations are attached from the source pages. The output guard rejects grounded responses that have no citations. If the corpus is silent, the assistant returns the no-answer response."
7. **What's the cost of a typical pilot?** "€0 for up to 60 days, up to 5 seats and 5,000 queries. You provide the hardware and we provide the system plus deployment support. Paid tiers can add a dedicated support channel and response SLA."
8. **Do you have SOC 2 / ISO 27001?** "The product is shipped as software you operate, so certifications live with the operator of the deployment. A controls mapping can be produced as scoped Enterprise work after the exact audit fields, guard behavior and trace coverage are agreed."

## Call-to-action
- Eyebrow: "Ready when you are." Title: "Bring your hardest **compliance question**."
- Body copy: "Up to 60-day evaluation. Your corpus, your model, your network. We bring the system, deployment support, and the trace IDs your auditor is going to ask about."
- Form asks for email (placeholder "you@company.com"), company and role/use-case. Success copy: "Request received — we'll be in touch within 24h." Supporting copy below the form: "We'll reply within 24h."
- Benefit chips: Up to 60-day evaluation; Local-first deployment; Deployment support included; Paid-tier response SLA. Details: CTA posts to formsubmit.co and handles sending state.

## Footer
- Tagline: "Compliance-first AI for the people who get audited."
- Link groups: Product only, using real anchors for Product (`#product`), How it works (`#how`), Security (`#security`), Pricing (`#pricing`) and FAQ (`#faq`). Removed placeholder For, Resources and Company groups.
- Legal/contact links: Privacy, Terms, Security and DPA point to `mailto:info@safe4ai.com` until dedicated legal pages exist. Copyright line: "© 2026 private·ai · v0.4.1."
