# Controls Mapping

Date: 2026-06-12
Audience: Enterprise security and compliance reviewers

This is a service artifact, not a certification claim. Safe4AI maps product
evidence to common control themes so a customer can evaluate fit against its
own SOC 2, ISO 27001, NIST, or internal control framework.

| Control theme | Safe4AI evidence | Boundary |
|---|---|---|
| Access control | JWT auth, role-based admin APIs, CSRF on unsafe methods | Customer owns identity lifecycle and user approvals |
| Change management | Versioned release images, release notes, test gates, SBOMs, vulnerability scans, signed images | Customer owns deployment approval and rollout window |
| Vulnerability management | `pip-audit`, Trivy CRITICAL/HIGH image gates, SBOMs attached to releases | Customer owns infrastructure and registry scanning policies |
| Logging and monitoring | `audit_logs`, `agent_runs`, feedback rows, OTLP/Jaeger, admin stats | Customer owns SIEM export and retention policy |
| Data retention | Configurable audit retention, tamper-evident archive before cleanup | Customer owns WORM/immutable storage enforcement |
| Backup and recovery | Backup/restore runbook and restore drill expectations | Customer owns backup platform, schedule, encryption, and restore execution |
| Data deletion | Document deletion verification endpoint | Customer owns legal approval and evidence retention |
| Privacy and minimization | Query text truncated to 500 chars in audit logs, no secrets in audit rows | Customer owns uploaded content classification |
| AI governance | Grounded citations, output filter, human review flag, provider-mode audit | Customer owns policy for acceptable AI use and provider approvals |
| Vendor/runtime boundary | Closed-runtime release process and customer-owned data layer | Customer owns data stores, local models, cloud accounts, and network controls |

## Required customer decisions

Before a production rollout, record:

- Approved deployment mode: Compose, air-gap, or Kubernetes/Helm.
- Approved provider mode: local, hybrid, or cloud/OpenAI-compatible.
- Audit retention period.
- Backup retention period.
- WORM/immutable storage requirement.
- SIEM/export requirement.
- Security-pack evidence required per release.

## Non-claims

This document does not claim SOC 2, ISO 27001, HIPAA, GDPR, or FINRA
certification. It gives the customer's control owner the evidence map needed
to assess Safe4AI inside the customer's own control environment.
