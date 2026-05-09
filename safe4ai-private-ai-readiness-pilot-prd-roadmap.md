# Safe4AI Private AI Readiness + Pilot

## 1. Product Summary

`Private AI Readiness + Pilot` is a fixed-scope, fixed-timeline paid package for regulated companies that want to test AI on sensitive internal data without sending that data to public cloud AI tools.

The package is not a generic AI consulting engagement. It is a productized fixed-scope delivery that ends with a working production-grade private AI system, a readiness assessment, security/compliance findings, measured usage results, and a clear recommendation for expansion.

## 2. Positioning

### One-Liner

Private AI for regulated companies: deploy one secure AI workflow on your own infrastructure, production-ready from day one, with audit logs, citations, and a readiness report.

### Primary Buyer

- CIO / Head of IT
- Compliance officer / Data protection officer
- Operations leader responsible for document-heavy workflows
- Founder/CEO in regulated mid-market companies

### Ideal Customer Profile

The best early customers are regulated mid-market companies with sensitive documents, slow manual workflows, and blocked or restricted use of public AI tools.

Priority verticals:

- Private healthcare groups
- Law firms and legal departments
- Insurance companies
- Banks and fintech companies
- Municipalities and public-sector agencies
- Manufacturing companies with internal procedures, contracts, and compliance documentation

## 3. Problem

Regulated companies want AI productivity, but they face three blockers:

1. Sensitive data cannot be sent to public AI tools.
2. Internal IT teams do not have time to build production-grade private AI.
3. Generic AI consultants do not deliver a concrete, measurable result fast enough.

Current behavior usually looks like:

- public AI tools are banned or informally used as shadow AI
- employees manually search folders, PDFs, SharePoint, DMS, email, and ERP exports
- internal IT creates demos that never reach production
- leadership talks about AI strategy but no team owns a real workflow

## 4. Goals

### Business Goals

- Convert vague AI interest into paid pilots.
- Learn which workflow has the strongest willingness to pay.
- Produce repeatable implementation patterns for the future Safe4AI product.
- Create case studies, reference customers, and production expansion opportunities.

### Customer Goals

- Test private AI without a long procurement or transformation program.
- Keep sensitive data inside approved infrastructure.
- Measure whether AI reduces manual work in one real workflow.
- Understand technical, security, and compliance requirements before scaling.

## 5. Non-Goals

This package should not include:

- full enterprise AI transformation
- company-wide rollout
- custom AI agents for multiple departments
- deep ERP/EHR/DMS integrations
- model fine-tuning unless absolutely necessary
- autonomous decision-making
- medical, legal, or financial advice generation without human review
- unlimited document volume
- unlimited users

## 6. Pilot Scope

Each pilot must include exactly one primary workflow.

Recommended first workflows:

1. Document Q&A over internal policies, procedures, contracts, or manuals.
2. Policy assistant for compliance, HR, legal, or operations teams.
3. Invoice or contract OCR with structured extraction and document lookup.
4. Medical intake summary for private clinics, where patient data stays private.

Default package limits:

- 1 department or team
- 5-10 users
- up to 500-2,000 documents, depending on document complexity
- 1 deployment environment
- 1 workflow
- 1 final readiness report

## 7. Deliverables

### Discovery Deliverables

- workflow map
- data inventory
- stakeholder map
- risk register
- current process baseline
- target success metric

### Technical Deliverables

- working private AI pilot
- document ingestion pipeline
- prompt and retrieval configuration
- access-control model for pilot users
- citation/source display
- basic audit logging
- admin access for Safe4AI and customer owner

### Business Deliverables

- pilot results summary
- measured before/after workflow comparison
- production-readiness score
- security/compliance gap list
- recommended next phase
- estimated production rollout scope and cost

## 8. Functional Requirements

### FR1: Workflow Selection

The pilot must start by selecting one workflow with a measurable business outcome.

Acceptance criteria:

- one workflow is documented
- workflow owner is named
- current process is mapped
- success metric is defined before implementation starts

### FR2: Data Intake

Safe4AI must collect or connect to a bounded set of customer documents.

Acceptance criteria:

- document types are listed
- document volume is capped
- sensitive data handling is approved by customer owner
- unsupported formats are identified early

### FR3: Private AI Prototype

The pilot must produce a usable private AI prototype for the chosen workflow.

Acceptance criteria:

- pilot users can ask questions or process documents
- responses reference customer-provided data
- outputs include citations or source links where applicable
- customer data is not sent to unauthorized public AI services

### FR4: Access Control

The pilot must include a simple access-control model.

Acceptance criteria:

- pilot users are named or grouped
- document access is limited by role where needed
- admin can remove user access

### FR5: Audit Logging

The pilot must log usage events.

Acceptance criteria:

- user, timestamp, query/action, and result metadata are recorded
- logs can be exported or reviewed by admin
- sensitive log retention rules are documented

### FR6: Results Report

The pilot must end with a decision-ready report.

Acceptance criteria:

- baseline and pilot results are compared
- technical risks are listed
- compliance gaps are listed
- recommendation is one of: stop, repeat pilot, expand to production

## 9. Security And Compliance Requirements

Minimum requirements:

- customer data stays in approved infrastructure
- no training on customer data without explicit written approval
- role-based access for pilot users
- audit log for user actions
- documented data retention policy
- documented backup and deletion process
- human review for high-risk outputs

Nice-to-have requirements:

- single sign-on integration
- encryption at rest
- encryption in transit
- customer-managed keys
- private model hosting
- vulnerability scan
- deployment hardening checklist

## 10. Technical Architecture

The pilot is built on a private AI stack designed for on-premise or private cloud deployment. All components run inside the customer's approved infrastructure. No customer data leaves the deployment boundary.

### Orchestration Framework

The pilot uses **LangGraph** (Python) as the agent and workflow orchestration framework.

Rationale for choosing LangGraph over alternatives:

- Native RAG pipeline support with LangChain document loaders
- Stateful, multi-step workflow graphs with explicit control over retrieval, reranking, and generation steps
- Compatible with any LLM that exposes an OpenAI-compatible API, which covers all major open-source models
- No dependency on external AI hosting — everything runs locally
- Built-in support for streaming, human-in-the-loop checkpoints, and audit-friendly state persistence

### Language Model

Default starting model: **Qwen 3.5 9B**, deployed locally via Ollama or vLLM.

The model choice is configurable per deployment and can be swapped without changing the application layer. Supported alternatives:

- Llama 3.x (Meta)
- Mistral / Mixtral
- Qwen 2.5
- Any model served via an OpenAI-compatible API endpoint

Final model selection depends on hardware available at the customer site, language requirements, and task performance during discovery.

### Embeddings

Local embedding model served via Ollama or a dedicated inference server. Default candidates: `nomic-embed-text`, `bge-m3`. No external embedding API calls.

### Vector Store

Default: **Qdrant** (self-hosted Docker container). Alternatives based on customer preference or existing infrastructure: pgvector (PostgreSQL extension), Chroma, Weaviate.

### Document Processing

LangChain document loaders handle PDF, DOCX, XLSX, and plain text. Scanned document support via vision OCR using a local multimodal model (Qwen2.5-VL 7B via Ollama) — no external OCR service. Pages where extraction confidence is low are flagged for manual admin review.

### Deployment

Pilot deployments use Docker Compose for simplicity. Production-scale deployments use Kubernetes. All services are containerised and can run on customer-managed infrastructure, including on-premise servers, private cloud, or air-gapped environments.

### Conceptual Architecture

```
[Pilot User]
     │
     ▼
[Web UI / Chat Interface]
     │
     ▼
[LangGraph Agent]──────────────────────[LLM: Qwen 3.5 9B / local model]
     │                                          (Ollama / vLLM)
     ├──► [Retriever] ──► [Vector Store: Qdrant]
     │                          │
     │                    [Embeddings: local]
     │
     ├──► [Document Store: local filesystem / S3-compatible]
     │
     └──► [Audit Log: structured JSON / PostgreSQL]
```

## 11. Packaging And Pricing

Suggested tiers:

### Starter

- 1 workflow
- up to 500 documents
- 5 users
- final report
- suggested price: EUR 3,000-5,000

### Standard

- 1 workflow
- up to 2,000 documents
- 10 users
- basic access control
- audit logs
- final report and rollout plan
- suggested price: EUR 7,500-15,000

### Enterprise

- 1-2 workflows
- private infrastructure deployment
- security review
- compliance workshop
- production architecture proposal
- suggested price: EUR 20,000+

Early sales should bias toward `Standard`, because it is paid enough to prove seriousness but small enough to avoid a long enterprise procurement cycle.

## 12. Success Metrics

### Product Metrics

- number of paid pilots sold
- pilot-to-production conversion rate
- average pilot implementation time
- number of repeatable workflow templates discovered
- number of referenceable customers

### Customer Metrics

Choose one primary metric per pilot:

- time to find an answer
- number of manual document searches avoided
- time saved per case/patient/contract/invoice
- reduction in incomplete intake or missing information
- reduction in manual data extraction
- user satisfaction after real usage

## 13. Roadmap

### Phase 0: Offer Definition

Duration: 1 week

Deliverables:

- one-page sales offer
- pilot scope checklist
- pricing tiers
- discovery questionnaire
- security FAQ
- sample final report template

### Phase 1: Founder-Led Sales

Duration: 2-4 weeks

Deliverables:

- list of 100 target companies
- 30 direct conversations
- 10 discovery calls
- 3 paid pilot proposals
- 1-2 signed pilots

### Phase 2: First Paid Pilots

Duration: 2-6 weeks

Deliverables:

- working pilot systems
- pilot result reports
- documented objections
- documented implementation bottlenecks
- customer quotes or case-study permission

### Phase 3: Repeatable Playbook

Duration: 4-8 weeks

Deliverables:

- standard implementation checklist
- reusable architecture pattern
- reusable security documents
- reusable workflow templates
- clearer ICP based on paid demand

### Phase 4: Convert To Product

Duration: after 3-5 successful pilots

Deliverables:

- product requirements for private RAG appliance
- production deployment model
- support model
- pricing model for annual contracts

## 14. Key Risks

### Risk: The customer only wants free AI education.

Mitigation:

- require paid pilot
- define a business metric before technical work
- avoid long unpaid workshops

### Risk: Procurement kills speed.

Mitigation:

- sell to mid-market first
- keep scope under procurement thresholds where legally appropriate
- use fixed price and fixed timeline

### Risk: The pilot becomes custom consulting.

Mitigation:

- one workflow only
- capped document volume
- no deep integrations in first pilot
- reuse the same report and architecture template

### Risk: Security requirements exceed pilot budget.

Mitigation:

- separate pilot from production hardening
- list security gaps transparently
- price enterprise-grade deployment separately

## 15. Open Questions

- Which vertical should Safe4AI attack first?
- What deployment environments can Safe4AI support reliably from day one?
- Which local/EU compliance claims can be safely made?
- What is the minimum security documentation needed to close paid pilots?
- Which workflow has the shortest sales cycle and clearest ROI?
- Which LLM performs best for the pilot workflow? Default starting point is Qwen 3.5 9B; final selection to be validated per customer hardware and language requirements.
- Which embedding model gives the best retrieval quality for the target document types?
- Should Qdrant or pgvector be the default vector store for customers with existing PostgreSQL infrastructure?

