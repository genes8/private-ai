# Test Automation and Quality Assurance

<cite>
**Referenced Files in This Document**
- [.github/workflows/ci.yml](file://.github/workflows/ci.yml)
- [safe4ai-pilot/.github/workflows/ci.yml](file://safe4ai-pilot/.github/workflows/ci.yml)
- [safe4ai-pilot/pyproject.toml](file://safe4ai-pilot/pyproject.toml)
- [safe4ai-pilot/tests/conftest.py](file://safe4ai-pilot/tests/conftest.py)
- [safe4ai-pilot/tests/test_health.py](file://safe4ai-pilot/tests/test_health.py)
- [safe4ai-pilot/tests/test_security_headers.py](file://safe4ai-pilot/tests/test_security_headers.py)
- [safe4ai-pilot/tests/test_seed.py](file://safe4ai-pilot/tests/test_seed.py)
- [safe4ai-pilot/tests/test_integration_containers.py](file://safe4ai-pilot/tests/test_integration_containers.py)
- [safe4ai-pilot/tests/test_real_services_smoke.py](file://safe4ai-pilot/tests/test_real_services_smoke.py)
- [safe4ai-pilot/scripts/healthcheck.py](file://safe4ai-pilot/scripts/healthcheck.py)
- [safe4ai-pilot/scripts/seed.py](file://safe4ai-pilot/scripts/seed.py)
- [safe4ai-pilot/README.md](file://safe4ai-pilot/README.md)
- [safe4ai-pilot/docs/deployment.md](file://safe4ai-pilot/docs/deployment.md)
- [safe4ai-pilot/docker-compose.yml](file://safe4ai-pilot/docker-compose.yml)
- [safe4ai-pilot/.pre-commit-config.yaml](file://safe4ai-pilot/.pre-commit-config.yaml)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)
10. [Appendices](#appendices)

## Introduction
This document describes the test automation and quality assurance framework for the Private AI system, focusing on continuous integration workflows, automated testing pipelines, and quality gates. It explains the GitHub Actions CI configuration, automated test execution, and deployment validation processes. It also documents health check testing, security header validation, and data seeding verification. Quality assurance processes covered include code coverage requirements, static analysis integration, and automated security scanning. Practical examples show how to configure CI/CD pipelines, implement quality gates, and handle test failures. Debugging techniques for automated test failures, log analysis, and test environment troubleshooting are included, along with best practices for maintaining test reliability and preventing flakiness.

## Project Structure
The repository includes two primary CI configurations and a comprehensive test suite:
- Root CI workflow for the monorepo-level pipeline
- Application-specific CI workflow for the Safe4AI pilot
- A pytest-based test suite with fixtures, unit, integration, and smoke tests
- Scripts for health checks and data seeding
- Docker Compose orchestration for local and CI environments

```mermaid
graph TB
subgraph "CI Workflows"
ROOT[".github/workflows/ci.yml"]
APP["safe4ai-pilot/.github/workflows/ci.yml"]
end
subgraph "Testing"
PYCONF["safe4ai-pilot/pyproject.toml"]
FIX["safe4ai-pilot/tests/conftest.py"]
T_HEALTH["safe4ai-pilot/tests/test_health.py"]
T_HEADERS["safe4ai-pilot/tests/test_security_headers.py"]
T_SEED["safe4ai-pilot/tests/test_seed.py"]
T_INTEG["safe4ai-pilot/tests/test_integration_containers.py"]
T_SMOKE["safe4ai-pilot/tests/test_real_services_smoke.py"]
end
subgraph "Scripts"
HC["safe4ai-pilot/scripts/healthcheck.py"]
SD["safe4ai-pilot/scripts/seed.py"]
end
subgraph "Runtime"
DC["safe4ai-pilot/docker-compose.yml"]
DOC["safe4ai-pilot/docs/deployment.md"]
READ["safe4ai-pilot/README.md"]
end
ROOT --> PYCONF
APP --> PYCONF
PYCONF --> FIX
FIX --> T_HEALTH
FIX --> T_HEADERS
FIX --> T_SEED
FIX --> T_INTEG
FIX --> T_SMOKE
PYCONF --> HC
PYCONF --> SD
DC --> DOC
READ --> DC
```

**Diagram sources**
- [.github/workflows/ci.yml:1-40](file://.github/workflows/ci.yml#L1-L40)
- [safe4ai-pilot/.github/workflows/ci.yml:1-51](file://safe4ai-pilot/.github/workflows/ci.yml#L1-L51)
- [safe4ai-pilot/pyproject.toml:84-98](file://safe4ai-pilot/pyproject.toml#L84-L98)
- [safe4ai-pilot/tests/conftest.py:1-88](file://safe4ai-pilot/tests/conftest.py#L1-L88)
- [safe4ai-pilot/tests/test_health.py:1-85](file://safe4ai-pilot/tests/test_health.py#L1-L85)
- [safe4ai-pilot/tests/test_security_headers.py:1-105](file://safe4ai-pilot/tests/test_security_headers.py#L1-L105)
- [safe4ai-pilot/tests/test_seed.py:1-14](file://safe4ai-pilot/tests/test_seed.py#L1-L14)
- [safe4ai-pilot/tests/test_integration_containers.py:1-28](file://safe4ai-pilot/tests/test_integration_containers.py#L1-L28)
- [safe4ai-pilot/tests/test_real_services_smoke.py:1-62](file://safe4ai-pilot/tests/test_real_services_smoke.py#L1-L62)
- [safe4ai-pilot/scripts/healthcheck.py:1-58](file://safe4ai-pilot/scripts/healthcheck.py#L1-L58)
- [safe4ai-pilot/scripts/seed.py:1-47](file://safe4ai-pilot/scripts/seed.py#L1-L47)
- [safe4ai-pilot/docker-compose.yml:1-119](file://safe4ai-pilot/docker-compose.yml#L1-L119)
- [safe4ai-pilot/docs/deployment.md:1-122](file://safe4ai-pilot/docs/deployment.md#L1-L122)
- [safe4ai-pilot/README.md:1-133](file://safe4ai-pilot/README.md#L1-L133)

**Section sources**
- [.github/workflows/ci.yml:1-40](file://.github/workflows/ci.yml#L1-L40)
- [safe4ai-pilot/.github/workflows/ci.yml:1-51](file://safe4ai-pilot/.github/workflows/ci.yml#L1-L51)
- [safe4ai-pilot/pyproject.toml:84-98](file://safe4ai-pilot/pyproject.toml#L84-L98)
- [safe4ai-pilot/README.md:1-133](file://safe4ai-pilot/README.md#L1-L133)
- [safe4ai-pilot/docs/deployment.md:1-122](file://safe4ai-pilot/docs/deployment.md#L1-L122)
- [safe4ai-pilot/docker-compose.yml:1-119](file://safe4ai-pilot/docker-compose.yml#L1-L119)

## Core Components
- CI pipelines:
  - Root CI validates linting, formatting, type checking, tests with coverage, dependency CVE scan, and secret scanning.
  - Application CI mirrors the above plus system dependency installation and extended pip-audit options.
- Testing framework:
  - Pytest configuration defines markers for integration and smoke tests, coverage exclusions, and environment overrides.
  - Fixtures provide mock transports and containerized services for deterministic tests.
- Health checks and seeding:
  - Healthcheck script verifies PostgreSQL, Qdrant, and Ollama reachability.
  - Seed script creates an admin user and test documents for functional validation.
- Orchestration:
  - Docker Compose manages service health checks and runtime dependencies.

**Section sources**
- [.github/workflows/ci.yml:1-40](file://.github/workflows/ci.yml#L1-L40)
- [safe4ai-pilot/.github/workflows/ci.yml:1-51](file://safe4ai-pilot/.github/workflows/ci.yml#L1-L51)
- [safe4ai-pilot/pyproject.toml:84-98](file://safe4ai-pilot/pyproject.toml#L84-L98)
- [safe4ai-pilot/tests/conftest.py:1-88](file://safe4ai-pilot/tests/conftest.py#L1-L88)
- [safe4ai-pilot/scripts/healthcheck.py:1-58](file://safe4ai-pilot/scripts/healthcheck.py#L1-L58)
- [safe4ai-pilot/scripts/seed.py:1-47](file://safe4ai-pilot/scripts/seed.py#L1-L47)
- [safe4ai-pilot/docker-compose.yml:1-119](file://safe4ai-pilot/docker-compose.yml#L1-L119)

## Architecture Overview
The CI/CD and QA architecture integrates GitHub Actions with local development and containerized environments. Static analysis and security scans run alongside unit and integration tests. Smoke tests validate real services when orchestrated by Docker Compose.

```mermaid
sequenceDiagram
participant GH as "GitHub Actions Runner"
participant PY as "Python Environment"
participant LINT as "Ruff"
participant TYPE as "Mypy"
participant TEST as "Pytest"
participant COV as "Coverage"
participant SEC1 as "pip-audit"
participant SEC2 as "detect-secrets"
GH->>PY : "Checkout + Setup Python"
PY->>LINT : "Lint check"
PY->>TYPE : "Type check"
PY->>TEST : "Run tests"
TEST->>COV : "Generate coverage XML"
PY->>SEC1 : "Dependency CVE scan"
PY->>SEC2 : "Secrets scan"
SEC1-->>GH : "Report"
SEC2-->>GH : "Report"
COV-->>GH : "Coverage XML"
```

**Diagram sources**
- [.github/workflows/ci.yml:15-39](file://.github/workflows/ci.yml#L15-L39)
- [safe4ai-pilot/.github/workflows/ci.yml:18-50](file://safe4ai-pilot/.github/workflows/ci.yml#L18-L50)
- [safe4ai-pilot/pyproject.toml:84-98](file://safe4ai-pilot/pyproject.toml#L84-L98)

## Detailed Component Analysis

### CI Pipelines and Quality Gates
- Root CI:
  - Triggers on pushes and pull requests to main.
  - Steps include checkout, Python setup, dependency installation, lint/format/type checks, tests with coverage threshold, dependency CVE scan, and secrets scan.
  - Coverage failure threshold is enforced via a dedicated flag.
- Application CI:
  - Adds system dependencies for file processing and PDF utilities.
  - Uses extended pip-audit options and a baseline for secrets detection.
- Quality gates:
  - Coverage threshold gate ensures maintainable test coverage.
  - Security gates enforce dependency audits and secret scanning.

```mermaid
flowchart TD
START(["CI Trigger"]) --> CHECKOUT["Checkout Code"]
CHECKOUT --> SETUP["Setup Python"]
SETUP --> DEPS["Install Dependencies"]
DEPS --> LINT["Ruff Lint"]
LINT --> FORMAT["Ruff Format Check"]
FORMAT --> TYPE["Mypy Type Check"]
TYPE --> TESTS["Pytest with Coverage"]
TESTS --> COV_FAIL{"Coverage >= 80%?"}
COV_FAIL --> |No| FAIL["Fail Build"]
COV_FAIL --> |Yes| AUDIT["pip-audit"]
AUDIT --> SECRETS["detect-secrets"]
SECRETS --> PASS["Pass"]
```

**Diagram sources**
- [.github/workflows/ci.yml:3-39](file://.github/workflows/ci.yml#L3-L39)
- [safe4ai-pilot/.github/workflows/ci.yml:3-50](file://safe4ai-pilot/.github/workflows/ci.yml#L3-L50)
- [safe4ai-pilot/pyproject.toml:84-98](file://safe4ai-pilot/pyproject.toml#L84-L98)

**Section sources**
- [.github/workflows/ci.yml:1-40](file://.github/workflows/ci.yml#L1-L40)
- [safe4ai-pilot/.github/workflows/ci.yml:1-51](file://safe4ai-pilot/.github/workflows/ci.yml#L1-L51)
- [safe4ai-pilot/pyproject.toml:84-98](file://safe4ai-pilot/pyproject.toml#L84-L98)

### Health Check Testing
Health check tests validate the application’s readiness and prompt registry behavior under mocked dependencies. They ensure the health endpoint returns expected keys and that prompt retrieval works as expected.

```mermaid
sequenceDiagram
participant TC as "TestClient"
participant APP as "FastAPI App"
participant DB as "DB Engine (Mock)"
participant NET as "HTTP (Mock)"
TC->>APP : "GET /health"
APP->>DB : "Connect and execute"
APP->>NET : "Async GET to external services"
APP-->>TC : "200 OK with status and checks"
```

**Diagram sources**
- [safe4ai-pilot/tests/test_health.py:23-41](file://safe4ai-pilot/tests/test_health.py#L23-L41)
- [safe4ai-pilot/tests/test_health.py:43-49](file://safe4ai-pilot/tests/test_health.py#L43-L49)

**Section sources**
- [safe4ai-pilot/tests/test_health.py:1-85](file://safe4ai-pilot/tests/test_health.py#L1-L85)

### Security Header Validation
Security header tests verify that the application enforces standard security headers on endpoints, including error responses. They also validate request body limits enforced by middleware.

```mermaid
flowchart TD
REQ["HTTP Request"] --> APP["FastAPI App"]
APP --> HEADERS["Apply Security Middleware"]
HEADERS --> VALIDATE{"Headers Present?<br/>X-Content-Type-Options<br/>X-Frame-Options or CSP"}
VALIDATE --> |Yes| RESP["200 OK"]
VALIDATE --> |No| FAIL["Test Failure"]
```

**Diagram sources**
- [safe4ai-pilot/tests/test_security_headers.py:51-64](file://safe4ai-pilot/tests/test_security_headers.py#L51-L64)
- [safe4ai-pilot/tests/test_security_headers.py:67-87](file://safe4ai-pilot/tests/test_security_headers.py#L67-L87)

**Section sources**
- [safe4ai-pilot/tests/test_security_headers.py:1-105](file://safe4ai-pilot/tests/test_security_headers.py#L1-L105)

### Data Seeding Verification
Seeding verification ensures that the seed script flushes the database before creating documents, preserving deterministic order for tests and demos.

```mermaid
flowchart TD
START(["Seed Script"]) --> CREATE["Create Tables"]
CREATE --> ADMIN["Create Admin User"]
ADMIN --> FLUSH["Flush DB"]
FLUSH --> LOOP["Iterate to Create Documents"]
LOOP --> COMMIT["Commit and Close Session"]
```

**Diagram sources**
- [safe4ai-pilot/scripts/seed.py:13-42](file://safe4ai-pilot/scripts/seed.py#L13-L42)
- [safe4ai-pilot/tests/test_seed.py:7-13](file://safe4ai-pilot/tests/test_seed.py#L7-L13)

**Section sources**
- [safe4ai-pilot/scripts/seed.py:1-47](file://safe4ai-pilot/scripts/seed.py#L1-L47)
- [safe4ai-pilot/tests/test_seed.py:1-14](file://safe4ai-pilot/tests/test_seed.py#L1-L14)

### Integration and Smoke Testing
Integration tests rely on Docker containers for PostgreSQL and Qdrant, skipping when Docker is unavailable. Smoke tests validate real services when orchestrated by Docker Compose.

```mermaid
sequenceDiagram
participant PYTEST as "Pytest"
participant DOCKER as "Docker"
participant PG as "Postgres Container"
participant QD as "Qdrant Container"
PYTEST->>DOCKER : "Start Containers"
DOCKER-->>PG : "Run Postgres"
DOCKER-->>QD : "Run Qdrant"
PYTEST->>PG : "Connect and Verify Extension"
PYTEST->>QD : "Connect and Verify Ready Endpoint"
PYTEST-->>PYTEST : "Assertions Pass"
```

**Diagram sources**
- [safe4ai-pilot/tests/conftest.py:64-87](file://safe4ai-pilot/tests/conftest.py#L64-L87)
- [safe4ai-pilot/tests/test_integration_containers.py:9-18](file://safe4ai-pilot/tests/test_integration_containers.py#L9-L18)
- [safe4ai-pilot/tests/test_integration_containers.py:21-27](file://safe4ai-pilot/tests/test_integration_containers.py#L21-L27)

**Section sources**
- [safe4ai-pilot/tests/conftest.py:1-88](file://safe4ai-pilot/tests/conftest.py#L1-L88)
- [safe4ai-pilot/tests/test_integration_containers.py:1-28](file://safe4ai-pilot/tests/test_integration_containers.py#L1-L28)
- [safe4ai-pilot/tests/test_real_services_smoke.py:1-62](file://safe4ai-pilot/tests/test_real_services_smoke.py#L1-L62)

### Deployment Validation and Orchestration
Deployment documentation outlines required smoke checks and local verification steps. Docker Compose defines health checks for all services, ensuring reliable CI and local development.

```mermaid
graph TB
subgraph "Compose Services"
APP["app:8000/health"]
PG["postgres:5432"]
QD["qdrant:6333"]
OL["ollama:11434"]
JG["jaeger:16686"]
end
APP --> PG
APP --> QD
APP --> OL
APP -.-> JG
```

**Diagram sources**
- [safe4ai-pilot/docker-compose.yml:12-16](file://safe4ai-pilot/docker-compose.yml#L12-L16)
- [safe4ai-pilot/docker-compose.yml:25-29](file://safe4ai-pilot/docker-compose.yml#L25-L29)
- [safe4ai-pilot/docker-compose.yml:39-44](file://safe4ai-pilot/docker-compose.yml#L39-L44)
- [safe4ai-pilot/docker-compose.yml:69-73](file://safe4ai-pilot/docker-compose.yml#L69-L73)
- [safe4ai-pilot/docker-compose.yml:98-103](file://safe4ai-pilot/docker-compose.yml#L98-L103)

**Section sources**
- [safe4ai-pilot/docs/deployment.md:55-94](file://safe4ai-pilot/docs/deployment.md#L55-L94)
- [safe4ai-pilot/README.md:104-128](file://safe4ai-pilot/README.md#L104-L128)
- [safe4ai-pilot/docker-compose.yml:1-119](file://safe4ai-pilot/docker-compose.yml#L1-L119)

## Dependency Analysis
The testing and QA stack relies on:
- Pytest for test execution and fixtures
- Ruff for linting and formatting
- Mypy for type checking
- Coverage reporting and thresholds
- pip-audit for dependency vulnerability scanning
- detect-secrets for secret scanning
- Testcontainers for integration tests
- Docker Compose for service orchestration

```mermaid
graph LR
PYCONF["pyproject.toml"] --> PYTEST["pytest"]
PYCONF --> RUFF["ruff"]
PYCONF --> MYPY["mypy"]
PYCONF --> COV["pytest-cov"]
PYCONF --> AUDIT["pip-audit"]
PYCONF --> SECRET["detect-secrets"]
PYCONF --> TC["testcontainers"]
TESTS["Tests"] --> PYTEST
TESTS --> COV
CI["CI Workflow"] --> RUFF
CI --> MYPY
CI --> PYTEST
CI --> AUDIT
CI --> SECRET
```

**Diagram sources**
- [safe4ai-pilot/pyproject.toml:48-60](file://safe4ai-pilot/pyproject.toml#L48-L60)
- [safe4ai-pilot/pyproject.toml:66-82](file://safe4ai-pilot/pyproject.toml#L66-L82)
- [safe4ai-pilot/pyproject.toml:84-98](file://safe4ai-pilot/pyproject.toml#L84-L98)
- [.github/workflows/ci.yml:23-39](file://.github/workflows/ci.yml#L23-L39)
- [safe4ai-pilot/.github/workflows/ci.yml:34-50](file://safe4ai-pilot/.github/workflows/ci.yml#L34-L50)

**Section sources**
- [safe4ai-pilot/pyproject.toml:48-60](file://safe4ai-pilot/pyproject.toml#L48-L60)
- [safe4ai-pilot/pyproject.toml:66-82](file://safe4ai-pilot/pyproject.toml#L66-L82)
- [safe4ai-pilot/pyproject.toml:84-98](file://safe4ai-pilot/pyproject.toml#L84-L98)
- [.github/workflows/ci.yml:23-39](file://.github/workflows/ci.yml#L23-L39)
- [safe4ai-pilot/.github/workflows/ci.yml:34-50](file://safe4ai-pilot/.github/workflows/ci.yml#L34-L50)

## Performance Considerations
- Keep CI runtime efficient by running linting, type checking, and tests in parallel steps where appropriate.
- Use Docker Compose health checks to reduce flakiness in service readiness.
- Prefer mocking for network-dependent tests to avoid external latency and variability.
- Limit integration tests to essential scenarios and skip them when Docker is unavailable to prevent CI timeouts.

## Troubleshooting Guide
Common issues and resolutions:
- Coverage below threshold:
  - Ensure tests exercise sufficient code paths and that coverage exclusions remain minimal.
  - Review coverage configuration and adjust thresholds as needed.
- Secret or dependency scan failures:
  - Update dependencies to address vulnerabilities or record exceptions per policy.
  - Regenerate secrets baselines after controlled updates.
- Docker-related test failures:
  - Confirm Docker availability and permissions in CI runners.
  - Use explicit waits and retry logic for container startup.
- Real-service smoke test failures:
  - Verify Docker Compose stack is fully healthy before running smoke tests.
  - Check environment variables and service URLs.
- Healthcheck failures:
  - Inspect service logs and network connectivity.
  - Validate database credentials and Qdrant/Ollama endpoints.

**Section sources**
- [safe4ai-pilot/docs/deployment.md:55-94](file://safe4ai-pilot/docs/deployment.md#L55-L94)
- [safe4ai-pilot/scripts/healthcheck.py:12-53](file://safe4ai-pilot/scripts/healthcheck.py#L12-L53)
- [safe4ai-pilot/tests/test_real_services_smoke.py:12-17](file://safe4ai-pilot/tests/test_real_services_smoke.py#L12-L17)

## Conclusion
The Private AI system employs robust CI/CD and QA practices that combine static analysis, security scanning, comprehensive testing, and deployment validation. Quality gates ensure code quality and security standards, while health checks and smoke tests validate runtime readiness. Integration and smoke tests provide confidence in real-world deployments orchestrated by Docker Compose.

## Appendices
- Pre-commit configuration integrates linting, formatting, and secret scanning into local workflows to catch issues early.

**Section sources**
- [safe4ai-pilot/.pre-commit-config.yaml:1-20](file://safe4ai-pilot/.pre-commit-config.yaml#L1-L20)