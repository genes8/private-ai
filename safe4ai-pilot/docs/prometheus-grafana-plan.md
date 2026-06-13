# Prometheus and Grafana Plan

Date: 2026-06-12
Audience: Enterprise customers that need metrics beyond OTLP/Jaeger/admin stats

Prometheus and Grafana are not part of the default Safe4AI package. Current
support is OpenTelemetry/OTLP export, local Jaeger in the Compose stack,
database audit tables, feedback tables, cost tables, and admin stats endpoints.

## Decision

Do not claim Prometheus/Grafana support by default. Add it only when a customer
deployment needs platform metrics that are not covered by the current OTLP and
admin surfaces.

## Scope if enabled

If enabled, the Enterprise add-on should provide:

- `/metrics` endpoint on the backend with request counts, latency buckets,
  provider call counts, retrieval counts, ingestion job counts, and queue
  status.
- Prometheus scrape annotations or ServiceMonitor values in the Helm package.
- Grafana dashboard JSON for API latency, chat success/failure, ingestion
  status, provider usage, and cost trend.
- Alert examples for backend down, high error rate, provider failure, Qdrant
  unavailable, PostgreSQL unavailable, and ingestion backlog.

## Out of scope

- Sending customer query text or document content to metrics.
- Storing prompts, answers, citations, uploaded filenames, API keys, or cookies
  in Prometheus labels.
- Replacing audit logs with metrics. Audit evidence remains in PostgreSQL and
  the tamper-evident audit archive.

## Acceptance checks

Before claiming support:

```bash
curl -fsS http://localhost:8000/metrics | grep safe4ai_
promtool check metrics < metrics-sample.txt
promtool check rules alert-rules.yaml
```

The dashboard must be reviewed with sample data that contains no customer
content.
