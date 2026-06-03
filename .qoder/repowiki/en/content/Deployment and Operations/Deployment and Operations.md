# Deployment and Operations

<cite>
**Referenced Files in This Document**
- [docker-compose.yml](file://safe4ai-pilot/docker-compose.yml)
- [docker-compose.override.yml](file://safe4ai-pilot/docker-compose.override.yml)
- [docker-compose.ollama.yml](file://safe4ai-pilot/docker-compose.ollama.yml)
- [app/Dockerfile](file://safe4ai-pilot/app/Dockerfile)
- [frontend/Dockerfile](file://safe4ai-pilot/frontend/Dockerfile)
- [frontend/nginx.conf](file://safe4ai-pilot/frontend/nginx.conf)
- [pyproject.toml](file://safe4ai-pilot/pyproject.toml)
- [alembic.ini](file://safe4ai-pilot/alembic.ini)
- [scripts/backup.py](file://safe4ai-pilot/scripts/backup.py)
- [scripts/healthcheck.py](file://safe4ai-pilot/scripts/healthcheck.py)
- [scripts/migrate.py](file://safe4ai-pilot/scripts/migrate.py)
- [scripts/verify_airgap_package.py](file://safe4ai-pilot/scripts/verify_airgap_package.py)
- [.github/workflows/ci.yml](file://safe4ai-pilot/.github/workflows/ci.yml)
- [app/config.py](file://safe4ai-pilot/app/config.py)
- [docs/air-gap-runbook.md](file://safe4ai-pilot/docs/air-gap-runbook.md)
- [docs/deployment.md](file://safe4ai-pilot/docs/deployment.md)
</cite>

## Update Summary
**Changes Made**
- Added comprehensive air-gap deployment section with step-by-step offline deployment instructions
- Integrated air-gap verification procedures and artifact export processes
- Updated deployment strategies to include air-gapped environment support
- Enhanced operational procedures with offline validation and security considerations

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Air-Gap Deployment Strategy](#air-gap-deployment-strategy)
7. [Dependency Analysis](#dependency-analysis)
8. [Performance Considerations](#performance-considerations)
9. [Troubleshooting Guide](#troubleshooting-guide)
10. [Conclusion](#conclusion)
11. [Appendices](#appendices)

## Introduction
This document provides comprehensive deployment and operations guidance for the Private AI system. It covers containerized deployment with Docker Compose, orchestration of backend, frontend, database, vector store, and observability tools, production configuration, scaling considerations, backup and restore procedures, CI/CD automation, monitoring and alerting, security hardening, and operational best practices. The content is grounded in the repository's actual deployment artifacts and operational scripts, including comprehensive air-gap deployment capabilities for fully isolated environments.

## Project Structure
The deployment stack is orchestrated by Docker Compose with two primary service groups:
- Data and model services: PostgreSQL with pgvector, Qdrant vector database, and Ollama local LLM service.
- Application services: FastAPI backend application and Nginx-based frontend.

Development overrides enable hot reload and live volume mounts for rapid iteration. The system now supports both standard online deployments and fully air-gapped offline deployments through comprehensive artifact packaging and verification procedures.

```mermaid
graph TB
subgraph "Compose Services"
PG["PostgreSQL<br/>pgvector:0.8.0-pg16"]
QD["Qdrant<br/>v1.13.3"]
OL["Ollama<br/>latest"]
APP["FastAPI App<br/>Uvicorn"]
FE["Nginx Frontend"]
end
subgraph "Volumes"
PGDATA["postgres_data"]
QDDATA["qdrant_data"]
OLDATA["ollama_data"]
end
PG --- PGDATA
QD --- QDDATA
OL --- OLLDATA
APP --> |"HTTP"| FE
APP --> |"PostgreSQL"| PG
APP --> |"Qdrant"| QD
APP --> |"Ollama"| OL
```

**Diagram sources**
- [docker-compose.yml:1-87](file://safe4ai-pilot/docker-compose.yml#L1-L87)

**Section sources**
- [docker-compose.yml:1-87](file://safe4ai-pilot/docker-compose.yml#L1-L87)
- [docker-compose.override.yml:1-11](file://safe4ai-pilot/docker-compose.override.yml#L1-L11)

## Core Components
- Backend application
  - Built from the backend Dockerfile, installs Python dependencies, pre-bakes a cross-encoder model, and runs Uvicorn on port 8000.
  - Environment variables are loaded from .env and include database, vector store, and model gateway URLs.
  - Health checks probe the /health endpoint.
- Frontend
  - Multi-stage build: Node base for building assets, Nginx base for serving.
  - Nginx proxies API routes to the backend and serves a SPA fallback.
- Data and Vector Stores
  - PostgreSQL with pgvector extension for embeddings and metadata.
  - Qdrant for vector similarity search.
  - Ollama for local LLM inference with pre-warmed models.
- Observability
  - Jaeger for tracing (OTLP enabled).
- Operational Scripts
  - Backup: Postgres dump, Qdrant snapshot, and raw data archive.
  - Health check: Connectivity and readiness probes for Postgres, Qdrant, and Ollama.
  - Migration: Alembic upgrade to latest schema.
  - Air-gap verification: Static package verifier for offline deployment validation.

**Section sources**
- [app/Dockerfile:1-23](file://safe4ai-pilot/app/Dockerfile#L1-L23)
- [frontend/Dockerfile:1-14](file://safe4ai-pilot/frontend/Dockerfile#L1-L14)
- [frontend/nginx.conf:1-29](file://safe4ai-pilot/frontend/nginx.conf#L1-L29)
- [docker-compose.yml:46-83](file://safe4ai-pilot/docker-compose.yml#L46-L83)
- [scripts/backup.py:1-92](file://safe4ai-pilot/scripts/backup.py#L1-L92)
- [scripts/healthcheck.py:1-58](file://safe4ai-pilot/scripts/healthcheck.py#L1-L58)
- [scripts/migrate.py:1-17](file://safe4ai-pilot/scripts/migrate.py#L1-L17)
- [scripts/verify_airgap_package.py:1-59](file://safe4ai-pilot/scripts/verify_airgap_package.py#L1-L59)

## Architecture Overview
The system is a microservice-style composition:
- Backend exposes REST endpoints and streaming responses for chat.
- Frontend serves a SPA and proxies authenticated routes to the backend.
- Data plane: PostgreSQL stores relational data and embeddings metadata; Qdrant stores vectors; Ollama provides embeddings and generation.
- Observability: Jaeger collects traces via OTLP.
- Air-gap support: Complete offline deployment capability with artifact packaging and verification.

```mermaid
graph TB
Client["Browser"]
FE["Nginx Frontend<br/>SPA + API proxy"]
APP["FastAPI App<br/>Uvicorn"]
DB["PostgreSQL<br/>pgvector"]
VS["Qdrant"]
LLM["Ollama"]
TRC["Jaeger"]
AIRGAP["Air-Gap Verification<br/>Static Package Checker"]
Client --> FE
FE --> |"Proxy /auth /chat /me /admin /feedback"| APP
APP --> DB
APP --> VS
APP --> LLM
APP --> TRC
APP --> AIRGAP
```

**Diagram sources**
- [docker-compose.yml:1-87](file://safe4ai-pilot/docker-compose.yml#L1-L87)
- [frontend/nginx.conf:13-24](file://safe4ai-pilot/frontend/nginx.conf#L13-L24)
- [scripts/verify_airgap_package.py:26-48](file://safe4ai-pilot/scripts/verify_airgap_package.py#L26-L48)

## Detailed Component Analysis

### Backend Application Containerization
- Build process: Python slim image, system deps, pip install editable package, pre-bake cross-encoder.
- Runtime: Uvicorn with host 0.0.0.0 and port 8000.
- Development override: Hot reload via Uvicorn with mounted source directories.

```mermaid
flowchart TD
Start(["Build"]) --> Base["Base Python Slim Image"]
Base --> SysDeps["Install System Deps"]
SysDeps --> CopySrc["Copy Python Package Sources"]
CopySrc --> PipInstall["pip install -e ."]
PipInstall --> Preheat["Pre-bake CrossEncoder Model"]
Preheat --> CMD["CMD: Uvicorn app.main:app"]
CMD --> End(["Runtime"])
```

**Diagram sources**
- [app/Dockerfile:1-23](file://safe4ai-pilot/app/Dockerfile#L1-L23)

**Section sources**
- [app/Dockerfile:1-23](file://safe4ai-pilot/app/Dockerfile#L1-L23)
- [docker-compose.override.yml:2-11](file://safe4ai-pilot/docker-compose.override.yml#L2-L11)

### Frontend Containerization and Proxying
- Multi-stage build: Node build stage, Nginx runtime.
- Nginx configuration:
  - SPA fallback using try_files.
  - Proxies API routes to backend on port 8000.
  - Disables proxy buffering for SSE and sets long read timeout.
  - Enables gzip for common asset types.

```mermaid
flowchart TD
Dev["Source Code"] --> BuildStage["Node Build Stage"]
BuildStage --> Dist["Dist Artifacts"]
Dist --> Runtime["Nginx Runtime"]
Runtime --> SPA["SPA Fallback"]
Runtime --> Proxy["Proxy API Routes to app:8000"]
Proxy --> Backend["Backend App"]
```

**Diagram sources**
- [frontend/Dockerfile:1-14](file://safe4ai-pilot/frontend/Dockerfile#L1-L14)
- [frontend/nginx.conf:1-29](file://safe4ai-pilot/frontend/nginx.conf#L1-L29)

**Section sources**
- [frontend/Dockerfile:1-14](file://safe4ai-pilot/frontend/Dockerfile#L1-L14)
- [frontend/nginx.conf:13-28](file://safe4ai-pilot/frontend/nginx.conf#L13-L28)

### Data Plane: PostgreSQL, Qdrant, Ollama
- PostgreSQL (pgvector): Health-checked via pg_isready; persistent storage via named volume.
- Qdrant: Health-checked via TCP port; persistent storage via named volume.
- Ollama: Health-checked via CLI; pulls foundational models via a one-shot init service; persistent storage via named volume.

```mermaid
sequenceDiagram
participant Init as "ollama-init"
participant O as "Ollama"
Init->>O : "ollama pull <model>"
O-->>Init : "Models ready"
```

**Diagram sources**
- [docker-compose.ollama.yml:17-30](file://safe4ai-pilot/docker-compose.ollama.yml#L17-L30)

**Section sources**
- [docker-compose.yml:2-16](file://safe4ai-pilot/docker-compose.yml#L2-L16)
- [docker-compose.yml:18-29](file://safe4ai-pilot/docker-compose.yml#L18-L29)
- [docker-compose.yml:31-44](file://safe4ai-pilot/docker-compose.yml#L31-L44)
- [docker-compose.ollama.yml:17-30](file://safe4ai-pilot/docker-compose.ollama.yml#L17-L30)

### Observability: Tracing with Jaeger
- Jaeger all-in-one image with OTLP enabled.
- Health-checked via HTTP on the UI port.

```mermaid
graph LR
APP["App"] --> |OTLP| JAE["Jaeger"]
JAE --> UI["Jaeger UI"]
```

**Diagram sources**
- [docker-compose.yml:33-44](file://safe4ai-pilot/docker-compose.yml#L33-L44)

**Section sources**
- [docker-compose.yml:33-44](file://safe4ai-pilot/docker-compose.yml#L33-L44)

### Operational Scripts

#### Backup Procedure
End-to-end backup covering Postgres, Qdrant, and raw data:
- Postgres: pg_dump to an SQL file.
- Qdrant: trigger collection snapshot via REST API.
- Raw data: archive the raw directory to a timestamped folder.

```mermaid
flowchart TD
Start(["Run backup.py"]) --> T["Timestamp"]
T --> PG["pg_dump to SQL"]
T --> QD["POST /collections/documents/snapshots"]
T --> RAW["Archive data/raw to data/backups/raw_<ts>"]
PG --> Sum["Aggregate results"]
QD --> Sum
RAW --> Sum
Sum --> Done(["Exit 0 if all succeed"])
```

**Diagram sources**
- [scripts/backup.py:76-92](file://safe4ai-pilot/scripts/backup.py#L76-L92)

**Section sources**
- [scripts/backup.py:1-92](file://safe4ai-pilot/scripts/backup.py#L1-L92)

#### Health Checks
- Postgres: SQLAlchemy connection executes a simple query.
- Qdrant: GET /readyz endpoint.
- Ollama: GET /api/tags endpoint.

```mermaid
flowchart TD
Start(["Run healthcheck.py"]) --> P["Test Postgres"]
Start --> Q["Test Qdrant"]
Start --> O["Test Ollama"]
P --> All{"All OK?"}
Q --> All
O --> All
All --> |Yes| OK["Exit 0"]
All --> |No| Fail["Exit 1"]
```

**Diagram sources**
- [scripts/healthcheck.py:49-58](file://safe4ai-pilot/scripts/healthcheck.py#L49-L58)

**Section sources**
- [scripts/healthcheck.py:1-58](file://safe4ai-pilot/scripts/healthcheck.py#L1-L58)

#### Database Migrations
- Alembic upgrade to head using a subprocess wrapper.

**Section sources**
- [scripts/migrate.py:1-17](file://safe4ai-pilot/scripts/migrate.py#L1-L17)
- [alembic.ini:1-150](file://safe4ai-pilot/alembic.ini#L1-L150)

#### Air-Gap Package Verification
Static verification of air-gap deployment packages to ensure all required components are present and configured correctly:
- Verifies required Ollama models are included
- Confirms Docker Compose overlay presence
- Validates audit archive volume mounting
- Checks for complete runbook documentation

```mermaid
flowchart TD
Start(["Run verify_airgap_package.py"]) --> ReadFiles["Read app/Dockerfile, docker-compose.yml, docker-compose.ollama.yml"]
ReadFiles --> ParseYAML["Parse YAML configurations"]
ParseYAML --> CheckModels["Verify required Ollama models present"]
CheckModels --> CheckOverlay["Verify Ollama overlay excludes default compose"]
CheckOverlay --> CheckVolume["Verify audit archive volume mounting"]
CheckVolume --> CheckRunbook["Verify runbook documentation completeness"]
CheckRunbook --> Report["Generate verification report"]
Report --> Result{"All checks pass?"}
Result --> |Yes| Pass["Exit 0 - Valid air-gap package"]
Result --> |No| Fail["Exit 1 - Invalid air-gap package"]
```

**Diagram sources**
- [scripts/verify_airgap_package.py:26-48](file://safe4ai-pilot/scripts/verify_airgap_package.py#L26-L48)

**Section sources**
- [scripts/verify_airgap_package.py:1-59](file://safe4ai-pilot/scripts/verify_airgap_package.py#L1-L59)

### CI/CD Pipeline
- Job stages: checkout, setup Python, install system and Python dependencies, lint, format check, type check, tests with coverage, dependency audit, secrets scan.
- Coverage minimum enforced via pytest configuration.

```mermaid
sequenceDiagram
participant GH as "GitHub Actions"
participant Py as "Python Setup"
participant Deps as "Dependencies"
participant Lint as "Lint/Format/Type"
participant Test as "Tests + Coverage"
participant Audit as "Audit/Secrets"
GH->>Py : "Checkout + Setup Python"
Py->>Deps : "Install system + pip deps"
Deps->>Lint : "Ruff + Mypy"
Lint->>Test : "pytest with coverage"
Test->>Audit : "pip-audit + detect-secrets"
Audit-->>GH : "Job result"
```

**Diagram sources**
- [.github/workflows/ci.yml:1-51](file://safe4ai-pilot/.github/workflows/ci.yml#L1-L51)

**Section sources**
- [.github/workflows/ci.yml:1-51](file://safe4ai-pilot/.github/workflows/ci.yml#L1-L51)

## Air-Gap Deployment Strategy

### Overview
The Private AI system now supports fully air-gapped deployments for environments with no outbound internet access. This capability ensures compliance with security requirements while maintaining full functionality through comprehensive artifact packaging and verification procedures.

### Key Features
- **Complete Offline Capability**: All required Docker images, models, and configuration packaged for offline deployment
- **Static Verification**: Automated validation of air-gap packages before deployment
- **Model Preservation**: Warm Ollama model volumes exported and restored for optimal performance
- **Security Validation**: No-outbound connectivity checks to ensure true isolation

### Deployment Workflow

#### Phase 1: Build and Verification (Connected Environment)
1. **Package Verification**: Run static verifier to ensure all components are present
2. **Service Building**: Build application containers and pull required images
3. **Model Preparation**: Initialize and warm Ollama with required models
4. **Artifact Export**: Package all components for transfer

#### Phase 2: Artifact Export
1. **Image Packaging**: Export Docker images to tar archives
2. **Model Volume Export**: Create compressed archive of warmed Ollama models
3. **Configuration Packaging**: Bundle runtime configuration and documentation

#### Phase 3: Import and Deployment (Air-Gapped Environment)
1. **Image Import**: Load Docker images from tar archives
2. **Model Restoration**: Extract and restore Ollama model volumes
3. **Environment Setup**: Configure environment variables and start services
4. **Validation**: Execute no-outbound connectivity checks

### Required Components
- **Docker Images**: Application, frontend, PostgreSQL, Qdrant, Jaeger, and Ollama
- **Ollama Models**: `qwen3.5:9b`, `nomic-embed-text`, and `qwen2.5vl:7b`
- **Configuration Files**: Docker Compose files, environment examples, and runbooks
- **Verification Tools**: Static package verifier and health check scripts

### Security and Compliance
- **Network Isolation**: Verified no outbound connectivity from application container
- **Audit Trail**: Configured audit archive volume for compliance requirements
- **Immutable Packaging**: Complete deployment bundles prevent tampering
- **Access Control**: Approved media transfer process for artifact movement

**Section sources**
- [docs/air-gap-runbook.md:1-130](file://safe4ai-pilot/docs/air-gap-runbook.md#L1-L130)
- [docker-compose.ollama.yml:1-41](file://safe4ai-pilot/docker-compose.ollama.yml#L1-L41)
- [scripts/verify_airgap_package.py:11-19](file://safe4ai-pilot/scripts/verify_airgap_package.py#L11-L19)

## Dependency Analysis
- Backend runtime dependencies are declared in the Python project configuration.
- Alembic configuration controls migration scripts location and logging.
- Frontend Dockerfile and Nginx config define build-time and runtime behavior.
- Air-gap deployment adds verification dependencies for package completeness.

```mermaid
graph LR
PY["pyproject.toml"] --> APP["Backend App"]
APP --> DEPS["Runtime Dependencies"]
ALEMBIC["alembic.ini"] --> MIG["Migrations"]
FE_DOCKER["frontend/Dockerfile"] --> FE_NGINX["frontend/nginx.conf"]
AIRGAP["verify_airgap_package.py"] --> CHECKS["Package Verification"]
CHECKS --> COMPOSE["docker-compose.ollama.yml"]
CHECKS --> RUNBOOK["air-gap-runbook.md"]
```

**Diagram sources**
- [pyproject.toml:1-101](file://safe4ai-pilot/pyproject.toml#L1-L101)
- [alembic.ini:1-150](file://safe4ai-pilot/alembic.ini#L1-L150)
- [frontend/Dockerfile:1-14](file://safe4ai-pilot/frontend/Dockerfile#L1-L14)
- [frontend/nginx.conf:1-29](file://safe4ai-pilot/frontend/nginx.conf#L1-L29)
- [scripts/verify_airgap_package.py:26-48](file://safe4ai-pilot/scripts/verify_airgap_package.py#L26-L48)

**Section sources**
- [pyproject.toml:1-101](file://safe4ai-pilot/pyproject.toml#L1-L101)
- [alembic.ini:1-150](file://safe4ai-pilot/alembic.ini#L1-L150)
- [frontend/Dockerfile:1-14](file://safe4ai-pilot/frontend/Dockerfile#L1-L14)
- [frontend/nginx.conf:1-29](file://safe4ai-pilot/frontend/nginx.conf#L1-L29)
- [scripts/verify_airgap_package.py:1-59](file://safe4ai-pilot/scripts/verify_airgap_package.py#L1-L59)

## Performance Considerations
- Resource sizing
  - PostgreSQL: Allocate CPU/RAM proportional to concurrent connections and workload; enable appropriate shared buffers and work_mem.
  - Qdrant: Size storage for vectors plus snapshots; monitor disk throughput.
  - Ollama: Reserve memory for selected model families; keep models cached via init job.
  - Backend: Scale horizontally behind a load balancer; tune Uvicorn workers and threads.
  - Frontend: Nginx handles static assets efficiently; ensure adequate CPU for proxy buffering and gzip.
- Caching and pre-warming
  - Backend pre-bakes a cross-encoder model to reduce cold-start latency.
  - Ollama init job pulls foundational models to warm caches.
  - Air-gap deployments benefit from pre-warmed model volumes for immediate performance.
- Network and I/O
  - Persist volumes for databases and model caches to avoid repeated downloads and rebuilds.
  - Use SSD-backed storage for Qdrant and Postgres for I/O-heavy operations.
  - Air-gap deployments eliminate network latency for model downloads.

## Troubleshooting Guide
- Service readiness
  - Use the health check script to verify connectivity to Postgres, Qdrant, and Ollama.
  - Review Docker Compose health checks for timing and retry thresholds.
- Database schema
  - Run the migration script to upgrade to the latest schema.
- Backups
  - Confirm timestamped backups for Postgres, Qdrant, and raw data; investigate partial failures.
- Logs
  - Inspect container logs for backend and frontend; review Nginx access/error logs.
- Secrets and configuration
  - Ensure .env is present and contains required keys; verify settings mapping in the backend configuration.
- Air-gap deployment issues
  - Use the static verifier to identify missing components in air-gap packages.
  - Verify no outbound connectivity from application container using the no-outbound check procedure.
  - Confirm all required Ollama models are present in the restored model volume.

**Section sources**
- [scripts/healthcheck.py:1-58](file://safe4ai-pilot/scripts/healthcheck.py#L1-L58)
- [scripts/migrate.py:1-17](file://safe4ai-pilot/scripts/migrate.py#L1-L17)
- [scripts/backup.py:1-92](file://safe4ai-pilot/scripts/backup.py#L1-L92)
- [scripts/verify_airgap_package.py:26-48](file://safe4ai-pilot/scripts/verify_airgap_package.py#L26-L48)
- [docs/air-gap-runbook.md:102-119](file://safe4ai-pilot/docs/air-gap-runbook.md#L102-L119)

## Conclusion
The Private AI system is designed for containerized deployment with clear separation of concerns across backend, frontend, data, vector store, and observability. The provided Docker Compose setup, operational scripts, and CI/CD pipeline enable repeatable development and production workflows. The addition of comprehensive air-gap deployment capabilities ensures the system can operate in fully isolated environments while maintaining full functionality. By following the operational procedures and performance guidance herein, teams can deploy reliably, scale effectively, and maintain high availability across both online and offline environments.

## Appendices

### Production Deployment Strategies
- Environment configuration
  - Define environment variables for database, vector store, and model gateway URLs.
  - Set allowed origins, secret key, HTTPS enforcement, and retention policies.
  - For air-gap deployments, configure AUDIT_ARCHIVE_DIR and OLLAMA_URL appropriately.
- Scaling
  - Backend: Horizontal pod scaling behind a reverse proxy; ensure stateless sessions and shared caches where applicable.
  - Frontend: Stateless; scale replicas behind Nginx or CDN.
  - Data plane: Tune PostgreSQL and Qdrant resources; consider read replicas for reporting.
  - Air-gap deployments benefit from pre-warmed model volumes for optimal performance.
- Resource requirements
  - Start with modest allocations and profile under realistic load; adjust CPU, memory, and disk IOPS accordingly.
  - Air-gap deployments may require additional storage for model volumes and audit archives.

**Section sources**
- [app/config.py:5-24](file://safe4ai-pilot/app/config.py#L5-L24)
- [docker-compose.yml:46-83](file://safe4ai-pilot/docker-compose.yml#L46-L83)
- [docker-compose.ollama.yml:32-37](file://safe4ai-pilot/docker-compose.ollama.yml#L32-L37)

### Backup and Restore Procedures
- Backup
  - Use the backup script to generate Postgres SQL dumps, Qdrant snapshots, and raw data archives.
  - For air-gap deployments, include audit archive data in backup procedures.
- Restore
  - Restore Postgres from SQL dump.
  - Restore Qdrant from snapshot.
  - Rehydrate raw data from archived directory.
  - For air-gap deployments, restore Ollama model volumes from exported archives.
- Automation
  - Schedule periodic backups and validate integrity regularly.
  - Include air-gap package verification in backup validation procedures.

**Section sources**
- [scripts/backup.py:1-92](file://safe4ai-pilot/scripts/backup.py#L1-L92)
- [docs/air-gap-runbook.md:36-66](file://safe4ai-pilot/docs/air-gap-runbook.md#L36-L66)

### Monitoring and Alerting
- Health checks
  - Use the health check script and Docker Compose health checks to monitor service readiness.
  - For air-gap deployments, include no-outbound connectivity checks in monitoring.
- Tracing
  - Jaeger UI provides end-to-end visibility; configure SDKs to export OTLP spans.
- Metrics
  - Instrument backend endpoints and integrate with Prometheus/Grafana for metrics collection.
  - Monitor air-gap deployment health through static verification reports.

**Section sources**
- [scripts/healthcheck.py:1-58](file://safe4ai-pilot/scripts/healthcheck.py#L1-L58)
- [docker-compose.yml:33-44](file://safe4ai-pilot/docker-compose.yml#L33-L44)
- [scripts/verify_airgap_package.py:51-54](file://safe4ai-pilot/scripts/verify_airgap_package.py#L51-L54)

### Security Considerations
- Secrets management
  - Store secrets in .env and restrict access; rotate secret keys periodically.
  - Enforce HTTPS in production and configure allowed origins carefully.
  - For air-gap deployments, ensure all secrets are embedded in the deployment package.
- Network isolation
  - Limit exposure of internal ports; use reverse proxies and firewalls.
  - Air-gap deployments require complete network isolation verification.
- Dependency hygiene
  - Regularly audit dependencies and scan for secrets in committed code.
  - Use static verification to ensure all required components are present in air-gap packages.
- Compliance
  - Audit archive volume provides compliance-ready data export capabilities.
  - Air-gap deployments support WORM (Write Once Read Many) retention requirements.

**Section sources**
- [app/config.py:11-13](file://safe4ai-pilot/app/config.py#L11-L13)
- [.github/workflows/ci.yml:46-50](file://safe4ai-pilot/.github/workflows/ci.yml#L46-L50)
- [docs/air-gap-runbook.md:121-129](file://safe4ai-pilot/docs/air-gap-runbook.md#L121-L129)

### CI/CD and Automated Testing
- CI pipeline stages cover linting, formatting, type checking, testing with coverage, dependency auditing, and secrets scanning.
- Tests include unit and integration suites; smoke tests rely on Docker Compose services.
- Air-gap verification integrated into CI pipeline for deployment package validation.
- Automated testing supports both online and offline deployment scenarios.

**Section sources**
- [.github/workflows/ci.yml:1-51](file://safe4ai-pilot/.github/workflows/ci.yml#L1-L51)
- [scripts/verify_airgap_package.py:51-54](file://safe4ai-pilot/scripts/verify_airgap_package.py#L51-L54)

### Air-Gap Deployment Procedures
- **Preparation**: Run static verifier to validate air-gap package completeness
- **Export**: Package Docker images, model volumes, and configuration files
- **Transfer**: Move artifacts through approved media process
- **Import**: Load images, restore model volumes, configure environment
- **Validation**: Execute no-outbound connectivity checks and service health verification
- **Monitoring**: Include air-gap-specific monitoring and alerting in operational procedures

**Section sources**
- [docs/air-gap-runbook.md:8-130](file://safe4ai-pilot/docs/air-gap-runbook.md#L8-L130)
- [scripts/verify_airgap_package.py:26-48](file://safe4ai-pilot/scripts/verify_airgap_package.py#L26-L48)