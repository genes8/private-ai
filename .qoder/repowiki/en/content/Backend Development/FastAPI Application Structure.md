# FastAPI Application Structure

<cite>
**Referenced Files in This Document**
- [main.py](file://safe4ai-pilot/app/main.py)
- [config.py](file://safe4ai-pilot/app/config.py)
- [pyproject.toml](file://safe4ai-pilot/pyproject.toml)
- [admin_routes.py](file://safe4ai-pilot/app/api/admin_routes.py)
- [chat_routes.py](file://safe4ai-pilot/app/api/chat_routes.py)
- [observability_routes.py](file://safe4ai-pilot/app/api/observability_routes.py)
- [router.py](file://safe4ai-pilot/app/auth/router.py)
- [middleware.py](file://safe4ai-pilot/app/auth/middleware.py)
- [__init__.py](file://safe4ai-pilot/app/db/__init__.py)
- [models.py](file://safe4ai-pilot/app/db/models.py)
- [docker-compose.yml](file://safe4ai-pilot/docker-compose.yml)
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
This document explains the FastAPI application structure for the Safe4AI Pilot backend. It focuses on application initialization, lifespan management, middleware configuration, routing patterns, configuration management, and operational deployment. It also provides practical guidance for extending the application with new middleware, custom exception handlers, and performance optimizations.

## Project Structure
The backend is organized around a FastAPI application with modular routers, shared configuration, database integration, and authentication utilities. The main application entry point initializes the lifespan, registers middleware, and mounts API routers. Configuration is managed centrally via Pydantic settings, and environment variables are supported. The project includes Docker Compose services for local development and production-like orchestration.

```mermaid
graph TB
subgraph "Application"
M["app/main.py"]
C["app/config.py"]
DBInit["app/db/__init__.py"]
Models["app/db/models.py"]
AuthRouter["app/auth/router.py"]
AuthMW["app/auth/middleware.py"]
Admin["app/api/admin_routes.py"]
Chat["app/api/chat_routes.py"]
Obs["app/api/observability_routes.py"]
end
subgraph "External Services"
PG["PostgreSQL"]
QD["Qdrant"]
OL["Ollama"]
end
M --> Admin
M --> Chat
M --> Obs
M --> AuthRouter
M --> DBInit
DBInit --> PG
M --> QD
M --> OL
M --> C
AuthRouter --> AuthMW
Admin --> Models
Chat --> Models
Obs --> Models
```

**Diagram sources**
- [main.py:63-101](file://safe4ai-pilot/app/main.py#L63-L101)
- [config.py:5-24](file://safe4ai-pilot/app/config.py#L5-L24)
- [__init__.py:8-21](file://safe4ai-pilot/app/db/__init__.py#L8-L21)
- [models.py:45-175](file://safe4ai-pilot/app/db/models.py#L45-L175)
- [router.py:24-24](file://safe4ai-pilot/app/auth/router.py#L24-L24)
- [middleware.py:51-71](file://safe4ai-pilot/app/auth/middleware.py#L51-L71)
- [admin_routes.py:39-39](file://safe4ai-pilot/app/api/admin_routes.py#L39-L39)
- [chat_routes.py:28-28](file://safe4ai-pilot/app/api/chat_routes.py#L28-L28)
- [observability_routes.py:16-16](file://safe4ai-pilot/app/api/observability_routes.py#L16-L16)

**Section sources**
- [main.py:63-101](file://safe4ai-pilot/app/main.py#L63-L101)
- [config.py:5-24](file://safe4ai-pilot/app/config.py#L5-L24)
- [pyproject.toml:9-46](file://safe4ai-pilot/pyproject.toml#L9-L46)

## Core Components
- Application entry point and lifespan: Initializes database extensions, creates tables, recovers stuck jobs, builds reusable components (HybridRetriever, Reranker, LangGraph), pre-warms Ollama, schedules cleanup, and registers exception handlers and middleware.
- Middleware stack: CORS, security headers, request size limiting, and custom HTTP middleware.
- Router registration: Mounts authentication, chat, observability, and admin routers.
- Configuration management: Centralized settings via Pydantic settings with environment variable support.
- Database integration: SQLAlchemy engine/session factory and declarative base with ORM models.

**Section sources**
- [main.py:28-67](file://safe4ai-pilot/app/main.py#L28-L67)
- [main.py:69-96](file://safe4ai-pilot/app/main.py#L69-L96)
- [main.py:98-101](file://safe4ai-pilot/app/main.py#L98-L101)
- [config.py:5-24](file://safe4ai-pilot/app/config.py#L5-L24)
- [__init__.py:8-21](file://safe4ai-pilot/app/db/__init__.py#L8-L21)
- [models.py:45-175](file://safe4ai-pilot/app/db/models.py#L45-L175)

## Architecture Overview
The application initializes long-lived resources during startup and exposes modular API endpoints grouped by feature. Authentication is handled via JWT cookies with role-based access control. The chat endpoints integrate a LangGraph pipeline and support both synchronous and streaming responses. Administrative endpoints manage documents, users, audit logs, and statistics. Observability endpoints collect feedback and compute cost statistics.

```mermaid
sequenceDiagram
participant Client as "Client"
participant App as "FastAPI App"
participant Lifespan as "Lifespan Manager"
participant DB as "SQLAlchemy Engine"
participant Ext as "External Services"
Client->>App : "Startup"
App->>Lifespan : "Enter lifespan"
Lifespan->>DB : "Ensure vector extension and create tables"
Lifespan->>Ext : "Pre-warm Ollama"
Lifespan-->>App : "Yield to serve requests"
App-->>Client : "Ready"
```

**Diagram sources**
- [main.py:28-60](file://safe4ai-pilot/app/main.py#L28-L60)

## Detailed Component Analysis

### Application Initialization and Lifespan Management
- Lifespan performs:
  - Ensures the Postgres vector extension is available.
  - Creates all database tables.
  - Recovers stuck ingestion jobs.
  - Builds reusable components (HybridRetriever, Reranker) and stores them in app.state for reuse.
  - Pre-warms Ollama to reduce first-query latency.
  - Schedules periodic cleanup tasks.
- Startup and shutdown:
  - Startup: database bootstrapping, component initialization, pre-warming, scheduling.
  - Shutdown: implicit via lifespan context manager; no explicit teardown shown.
- Health endpoint:
  - Validates connectivity to Postgres, Qdrant, and Ollama.

```mermaid
flowchart TD
Start(["Startup"]) --> EnsureVector["Ensure Postgres vector extension"]
EnsureVector --> CreateTables["Create database tables"]
CreateTables --> RecoverJobs["Recover stuck ingestion jobs"]
RecoverJobs --> BuildComponents["Build HybridRetriever and Reranker"]
BuildComponents --> StoreState["Store components in app.state"]
StoreState --> Prewarm["Pre-warm Ollama"]
Prewarm --> ScheduleCleanup["Schedule cleanup tasks"]
ScheduleCleanup --> Ready(["Ready to serve"])
```

**Diagram sources**
- [main.py:35-60](file://safe4ai-pilot/app/main.py#L35-L60)

**Section sources**
- [main.py:28-67](file://safe4ai-pilot/app/main.py#L28-L67)
- [main.py:118-147](file://safe4ai-pilot/app/main.py#L118-L147)

### Middleware Stack
- CORS: Configured with origins parsed from settings, allowing credentials and common HTTP methods.
- Security headers: Adds secure headers to every response via a custom HTTP middleware.
- Request size limit: Enforces a maximum upload size based on settings.
- Rate limiting: SlowAPI limiter is attached to the app state and used by route decorators across modules.

```mermaid
flowchart TD
Req["Incoming Request"] --> CORS["CORS Middleware"]
CORS --> SecHeaders["Security Headers Middleware"]
SecHeaders --> SizeLimit["Body Size Limit Middleware"]
SizeLimit --> Route["Route Handler"]
Route --> Resp["Response"]
```

**Diagram sources**
- [main.py:69-96](file://safe4ai-pilot/app/main.py#L69-L96)

**Section sources**
- [main.py:69-96](file://safe4ai-pilot/app/main.py#L69-L96)
- [router.py:21-22](file://safe4ai-pilot/app/auth/router.py#L21-L22)

### Router Registration Pattern
- Routers are included in the main application with no prefix, and each router defines its own tags for grouping.
- Routes are decorated with rate limiting where applicable and depend on shared dependencies (database sessions, current user).

```mermaid
graph LR
Main["app/main.py"] --> AR["app/api/admin_routes.py"]
Main --> CR["app/api/chat_routes.py"]
Main --> OR["app/api/observability_routes.py"]
Main --> AuR["app/auth/router.py"]
```

**Diagram sources**
- [main.py:98-101](file://safe4ai-pilot/app/main.py#L98-L101)
- [admin_routes.py:39-39](file://safe4ai-pilot/app/api/admin_routes.py#L39-L39)
- [chat_routes.py:28-28](file://safe4ai-pilot/app/api/chat_routes.py#L28-L28)
- [observability_routes.py:16-16](file://safe4ai-pilot/app/api/observability_routes.py#L16-L16)
- [router.py:24-24](file://safe4ai-pilot/app/auth/router.py#L24-L24)

**Section sources**
- [main.py:98-101](file://safe4ai-pilot/app/main.py#L98-L101)
- [admin_routes.py:63-114](file://safe4ai-pilot/app/api/admin_routes.py#L63-L114)
- [chat_routes.py:109-142](file://safe4ai-pilot/app/api/chat_routes.py#L109-L142)
- [observability_routes.py:26-35](file://safe4ai-pilot/app/api/observability_routes.py#L26-L35)
- [router.py:39-105](file://safe4ai-pilot/app/auth/router.py#L39-L105)

### Authentication and Authorization
- JWT-based authentication with HTTP-only cookies and role-based access control.
- Password hashing and verification utilities.
- Login enforces minimum password length, brute-force protection, and sets a signed cookie.
- Logout clears the cookie.

```mermaid
sequenceDiagram
participant Client as "Client"
participant Auth as "Auth Router"
participant DB as "Database"
participant MW as "Auth Middleware"
Client->>Auth : "POST /auth/login"
Auth->>DB : "Lookup user"
Auth->>Auth : "Verify password and lockout checks"
Auth-->>Client : "Set HTTP-only JWT cookie"
Client->>Protected : "Call protected route"
Protected->>MW : "Extract and verify JWT"
MW-->>Protected : "Active user"
Protected-->>Client : "Authorized response"
```

**Diagram sources**
- [router.py:39-105](file://safe4ai-pilot/app/auth/router.py#L39-L105)
- [middleware.py:51-71](file://safe4ai-pilot/app/auth/middleware.py#L51-L71)

**Section sources**
- [router.py:39-105](file://safe4ai-pilot/app/auth/router.py#L39-L105)
- [middleware.py:25-48](file://safe4ai-pilot/app/auth/middleware.py#L25-L48)
- [middleware.py:51-82](file://safe4ai-pilot/app/auth/middleware.py#L51-L82)

### Chat Pipeline and Streaming
- Blocking chat endpoint returns structured results.
- Streaming chat endpoint emits Server-Sent Events with steps and tokens.
- Uses app.state.graph built during lifespan.

```mermaid
sequenceDiagram
participant Client as "Client"
participant Chat as "Chat Router"
participant Graph as "LangGraph Pipeline"
participant DB as "Database"
Client->>Chat : "POST /chat or /chat/stream"
Chat->>DB : "Resolve session and user"
Chat->>Graph : "Invoke or stream pipeline"
Graph-->>Chat : "Final state"
Chat-->>Client : "Response or SSE stream"
```

**Diagram sources**
- [chat_routes.py:109-142](file://safe4ai-pilot/app/api/chat_routes.py#L109-L142)
- [chat_routes.py:150-244](file://safe4ai-pilot/app/api/chat_routes.py#L150-L244)

**Section sources**
- [chat_routes.py:109-142](file://safe4ai-pilot/app/api/chat_routes.py#L109-L142)
- [chat_routes.py:150-244](file://safe4ai-pilot/app/api/chat_routes.py#L150-L244)

### Admin and Observability Endpoints
- Admin endpoints manage documents (upload, list, status, delete, reindex), users, audit logs, stats, human review queue, and expose current user info.
- Observability endpoints handle feedback submission and admin feedback listing, plus cost statistics.

```mermaid
flowchart TD
AdminReq["Admin Request"] --> DocOps["Document Operations"]
AdminReq --> UserOps["User Management"]
AdminReq --> Audit["Audit Logs"]
AdminReq --> Stats["Stats"]
AdminReq --> Review["Human Review Queue"]
AdminReq --> Me["Current User Info"]
ObsReq["Observability Request"] --> Feed["Feedback"]
ObsReq --> AdminFeed["Admin Feedback"]
ObsReq --> Cost["Cost Stats"]
```

**Diagram sources**
- [admin_routes.py:63-114](file://safe4ai-pilot/app/api/admin_routes.py#L63-L114)
- [admin_routes.py:117-148](file://safe4ai-pilot/app/api/admin_routes.py#L117-L148)
- [admin_routes.py:346-418](file://safe4ai-pilot/app/api/admin_routes.py#L346-L418)
- [admin_routes.py:426-458](file://safe4ai-pilot/app/api/admin_routes.py#L426-L458)
- [admin_routes.py:466-529](file://safe4ai-pilot/app/api/admin_routes.py#L466-L529)
- [admin_routes.py:537-539](file://safe4ai-pilot/app/api/admin_routes.py#L537-L539)
- [observability_routes.py:26-35](file://safe4ai-pilot/app/api/observability_routes.py#L26-L35)
- [observability_routes.py:38-45](file://safe4ai-pilot/app/api/observability_routes.py#L38-L45)
- [observability_routes.py:48-56](file://safe4ai-pilot/app/api/observability_routes.py#L48-L56)

**Section sources**
- [admin_routes.py:63-114](file://safe4ai-pilot/app/api/admin_routes.py#L63-L114)
- [admin_routes.py:117-175](file://safe4ai-pilot/app/api/admin_routes.py#L117-L175)
- [admin_routes.py:178-243](file://safe4ai-pilot/app/api/admin_routes.py#L178-L243)
- [admin_routes.py:346-418](file://safe4ai-pilot/app/api/admin_routes.py#L346-L418)
- [admin_routes.py:426-458](file://safe4ai-pilot/app/api/admin_routes.py#L426-L458)
- [admin_routes.py:466-529](file://safe4ai-pilot/app/api/admin_routes.py#L466-L529)
- [admin_routes.py:537-539](file://safe4ai-pilot/app/api/admin_routes.py#L537-L539)
- [observability_routes.py:26-35](file://safe4ai-pilot/app/api/observability_routes.py#L26-L35)
- [observability_routes.py:38-45](file://safe4ai-pilot/app/api/observability_routes.py#L38-L45)
- [observability_routes.py:48-56](file://safe4ai-pilot/app/api/observability_routes.py#L48-L56)

### Configuration Management
- Settings class encapsulates environment-driven configuration with defaults and computed properties.
- Environment file support is configured via model_config.
- Settings consumed across the app include database URLs, external service endpoints, security keys, rate-limiting thresholds, and upload size limits.

```mermaid
classDiagram
class Settings {
+string postgres_url
+string qdrant_url
+string ollama_url
+string ollama_model
+string embedding_model
+string secret_key
+string allowed_origins
+bool enforce_https
+int audit_log_retention_days
+int cache_retention_days
+float semantic_cache_threshold
+float cost_per_1k_tokens
+int max_upload_size_mb
+allowed_origins_list() string[]
}
```

**Diagram sources**
- [config.py:5-24](file://safe4ai-pilot/app/config.py#L5-L24)

**Section sources**
- [config.py:5-24](file://safe4ai-pilot/app/config.py#L5-L24)

### Database Integration
- SQLAlchemy engine and session factory are configured with connection pooling and pre-ping.
- Declarative base is extended by domain models representing users, sessions, documents, chunks, audit logs, agent runs, feedback, ingestion jobs, and human review queue.

```mermaid
erDiagram
USERS {
string id PK
string email UK
string password_hash
enum role
timestamp created_at
boolean is_active
int failed_login_count
timestamp locked_until
}
SESSIONS {
string id PK
string user_id FK
timestamp created_at
timestamp updated_at
json state_json
}
DOCUMENTS {
string id PK
string filename
string storage_filename
string file_type
enum ingestion_status
string uploaded_by FK
timestamp uploaded_at
json doc_metadata
timestamp ingestion_started_at
int version
int active_version
}
DOCUMENT_CHUNKS {
string id PK
string document_id FK
int chunk_index
int chunk_version
string content_preview
string qdrant_point_id
}
SEMANTIC_CACHE {
string id PK
vector query_embedding
text query_text
json response_json
json citations_json
json source_document_ids
json source_chunk_ids
timestamp created_at
int hit_count
}
AUDIT_LOGS {
string id PK
string user_id FK
string session_id
timestamp timestamp
string action_type
string query_text
json response_metadata
int latency_ms
string model_used
string trace_id
}
AGENT_RUNS {
string id PK
string session_id
timestamp started_at
timestamp finished_at
string status
text final_output
text error
float cost_usd
}
QUERY_FEEDBACK {
string id PK
string trace_id
string session_id
string user_id FK
enum rating
text comment
timestamp created_at
}
INGESTION_JOBS {
string id PK
string document_id FK
string status
timestamp created_at
timestamp completed_at
text error
}
HUMAN_REVIEW_QUEUE {
string id PK
string session_id
string user_id FK
text query
text draft_answer
json citations_json
text risk_reason
enum status
string reviewed_by
timestamp reviewed_at
}
USERS ||--o{ SESSIONS : "owns"
USERS ||--o{ DOCUMENTS : "uploads"
DOCUMENTS ||--o{ DOCUMENT_CHUNKS : "chunks"
DOCUMENTS ||--o{ INGESTION_JOBS : "jobs"
USERS ||--o{ QUERY_FEEDBACK : "leaves"
AGENT_RUNS ||--o{ AUDIT_LOGS : "generates"
```

**Diagram sources**
- [models.py:45-175](file://safe4ai-pilot/app/db/models.py#L45-L175)

**Section sources**
- [__init__.py:8-21](file://safe4ai-pilot/app/db/__init__.py#L8-L21)
- [models.py:45-175](file://safe4ai-pilot/app/db/models.py#L45-L175)

## Dependency Analysis
- External dependencies include FastAPI, Uvicorn, SQLAlchemy, Pydantic, Alembic, Qdrant client, Ollama integrations, OpenTelemetry, SlowAPI, Secure headers, structlog, APScheduler, and others.
- Internal dependencies:
  - main.py depends on routers, auth middleware, config, database, and scripts.
  - Routers depend on auth middleware, database sessions, and models.
  - Auth router depends on auth middleware and settings.

```mermaid
graph TB
P["pyproject.toml"] --> F["FastAPI"]
P --> U["Uvicorn"]
P --> S["SQLAlchemy"]
P --> PS["Pydantic Settings"]
P --> L["LangChain / LangGraph"]
P --> Q["Qdrant Client"]
P --> O["Ollama Integrations"]
P --> OT["OpenTelemetry"]
P --> SL["SlowAPI"]
P --> SC["Secure"]
P --> ST["structlog"]
P --> AP["APScheduler"]
```

**Diagram sources**
- [pyproject.toml:9-46](file://safe4ai-pilot/pyproject.toml#L9-L46)

**Section sources**
- [pyproject.toml:9-46](file://safe4ai-pilot/pyproject.toml#L9-L46)
- [main.py:14-21](file://safe4ai-pilot/app/main.py#L14-L21)
- [router.py:14-17](file://safe4ai-pilot/app/auth/router.py#L14-L17)

## Performance Considerations
- Reuse expensive components: The lifespan builds HybridRetriever, Reranker, and the compiled LangGraph once and stores them in app.state for reuse across requests.
- Pre-warm external models: A background task pre-warms Ollama to avoid cold-start latency on first queries.
- Database optimization: Connection pooling and pre-ping are enabled; vector extension is ensured at startup.
- Rate limiting: Route decorators apply per-endpoint limits to protect downstream services.
- Streaming responses: SSE streaming reduces memory overhead and improves perceived latency for chat.

**Section sources**
- [main.py:43-58](file://safe4ai-pilot/app/main.py#L43-L58)
- [main.py:104-115](file://safe4ai-pilot/app/main.py#L104-L115)
- [__init__.py:8-9](file://safe4ai-pilot/app/db/__init__.py#L8-L9)
- [chat_routes.py:150-244](file://safe4ai-pilot/app/api/chat_routes.py#L150-L244)

## Troubleshooting Guide
- Health endpoint diagnostics:
  - Checks Postgres readiness, Qdrant readiness, and Ollama tags endpoint.
  - Aggregates statuses and returns overall status.
- CORS errors:
  - Verify allowed origins list matches frontend origin.
- Rate limit exceeded:
  - The application registers a global exception handler for RateLimitExceeded.
- Large uploads:
  - Body size middleware enforces max upload size; adjust settings if needed.
- Authentication failures:
  - Ensure cookies are sent with SameSite and Secure flags as configured.
- Database connectivity:
  - Confirm engine URL and pool settings; enable pre-ping for robustness.

**Section sources**
- [main.py:118-147](file://safe4ai-pilot/app/main.py#L118-L147)
- [main.py:69-96](file://safe4ai-pilot/app/main.py#L69-L96)
- [main.py:67-67](file://safe4ai-pilot/app/main.py#L67-L67)
- [config.py:18-18](file://safe4ai-pilot/app/config.py#L18-L18)
- [router.py:96-103](file://safe4ai-pilot/app/auth/router.py#L96-L103)

## Conclusion
The application follows a clean FastAPI structure with centralized configuration, robust middleware, modular routers, and lifecycle management for long-lived resources. It integrates authentication, rate limiting, security headers, and streaming responses, while leveraging external services for vector search and local LLM inference. The design supports easy extension with new middleware, exception handlers, and performance optimizations.

## Appendices

### Development Server Setup
- Run the application locally using Uvicorn with hot reload from the main module.

**Section sources**
- [main.py:150-153](file://safe4ai-pilot/app/main.py#L150-L153)

### Production Deployment Considerations
- Use Docker Compose to orchestrate Postgres, Qdrant, Ollama, Jaeger, and the application service.
- Configure environment variables via the app service’s env_file and environment overrides.
- Expose health checks and ensure dependent services are healthy before starting the app.
- Persist volumes for databases and model storage.

**Section sources**
- [docker-compose.yml:81-86](file://safe4ai-pilot/docker-compose.yml#L81-L86)
- [docker-compose.yml:98-103](file://safe4ai-pilot/docker-compose.yml#L98-L103)