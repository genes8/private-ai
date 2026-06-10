# Audit and Monitoring API

<cite>
**Referenced Files in This Document**
- [admin_routes.py](file://safe4ai-pilot/app/api/admin_routes.py)
- [audit_routes.py](file://safe4ai-pilot/app/api/audit_routes.py)
- [observability_routes.py](file://safe4ai-pilot/app/api/observability_routes.py)
- [models.py](file://safe4ai-pilot/app/db/models.py)
- [kinds.py](file://safe4ai-pilot/app/audit/kinds.py)
- [audit.ts](file://safe4ai-pilot/frontend/src/api/audit.ts)
- [stats.ts](file://safe4ai-pilot/frontend/src/api/stats.ts)
- [ActivityPage.tsx](file://safe4ai-pilot/frontend/src/pages/admin/ActivityPage.tsx)
- [useAuditStream.ts](file://safe4ai-pilot/frontend/src/hooks/useAuditStream.ts)
- [audit_cleanup.py](file://safe4ai-pilot/scripts/audit_cleanup.py)
- [config.py](file://safe4ai-pilot/app/config.py)
- [main.py](file://safe4ai-pilot/app/main.py)
- [chat_routes.py](file://safe4ai-pilot/app/api/chat_routes.py)
- [chat_finalizer.py](file://safe4ai-pilot/app/services/chat_finalizer.py)
- [runtime_config.py](file://safe4ai-pilot/app/services/runtime_config.py)
- [provider_clients.py](file://safe4ai-pilot/app/services/provider_clients.py)
</cite>

## Update Summary
**Changes Made**
- Added unified audit classification system with canonical taxonomy for action_type → UI kind mapping
- Implemented kind filtering via ?kind= parameter for audit log retrieval
- Added kind-count endpoint (/admin/audit-logs/kind-counts) for sidebar badge counts
- Enhanced administrative statistics with new daily time-series endpoint (GET /admin/stats/timeseries)
- Time-series endpoint returns 14-day query/user/cost buckets with zero-filling for missing dates
- Updated audit model tracking to use actual chat model names instead of provider types
- Improved statistics aggregation with accurate model name attribution
- Added comprehensive model name tracking across chat processing pipeline

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
This document provides comprehensive API documentation for audit logging and system monitoring endpoints designed for administrative oversight and compliance reporting. It covers:
- Audit log retrieval with filtering by timestamp range, user ID, action kind, and pagination controls (with a maximum limit of 1000 records per request)
- CSV export functionality for compliance reporting
- System statistics aggregation including query volume, average latency, cost tracking, and cache performance analytics
- Unified audit classification system with canonical taxonomy for action_type → UI kind mapping
- Kind filtering via ?kind= parameter and kind-count endpoint for sidebar badges
- Daily time-series endpoint for 14-day query/user/cost analytics
- Enhanced model tracking with accurate model name identification using actual chat model instead of provider type
- Practical examples for audit trail analysis, compliance reporting workflows, and system health monitoring
- Error handling guidance for invalid date ranges, export formatting, and performance optimization for large datasets

## Project Structure
The audit and monitoring APIs are implemented in the backend Python service and consumed by the React frontend. Key locations:
- Backend routers: admin and observability endpoints
- Database models: audit logs, agent runs, and semantic cache
- Audit classification system: canonical taxonomy for action_type → UI kind mapping
- Frontend API clients: typed wrappers for audit and stats
- Cleanup and retention policies: automated archival and deletion
- Model tracking: enhanced with actual chat model name identification

```mermaid
graph TB
subgraph "Backend"
M["FastAPI App<br/>main.py"]
AR["Admin Router<br/>admin_routes.py"]
OR["Observability Router<br/>observability_routes.py"]
AUDR["Audit Router<br/>audit_routes.py"]
DBM["Database Models<br/>models.py"]
KINDS["Audit Kinds Taxonomy<br/>kinds.py"]
CFG["Config<br/>config.py"]
CLEAN["Audit Cleanup Script<br/>audit_cleanup.py"]
CR["Chat Routes<br/>chat_routes.py"]
CF["Chat Finalizer<br/>chat_finalizer.py"]
RC["Runtime Config<br/>runtime_config.py"]
PC["Provider Clients<br/>provider_clients.py"]
end
subgraph "Frontend"
AUD["Audit API Client<br/>frontend audit.ts"]
STS["Stats API Client<br/>frontend stats.ts"]
ACT["Activity Page<br/>ActivityPage.tsx"]
UAS["Audit Stream Hook<br/>useAuditStream.ts"]
end
M --> AR
M --> OR
M --> AUDR
AR --> DBM
OR --> DBM
AUDR --> DBM
AR --> CFG
OR --> CFG
AUDR --> KINDS
CR --> CF
CR --> RC
CR --> PC
CF --> DBM
CLEAN --> DBM
AUD --> AR
AUD --> AUDR
STS --> OR
ACT --> AUD
ACT --> STS
UAS --> AUD
```

**Diagram sources**
- [main.py:63-101](file://safe4ai-pilot/app/main.py#L63-L101)
- [admin_routes.py:43](file://safe4ai-pilot/app/api/admin_routes.py#L43)
- [observability_routes.py:16](file://safe4ai-pilot/app/api/observability_routes.py#L16)
- [audit_routes.py:241-257](file://safe4ai-pilot/app/api/audit_routes.py#L241-L257)
- [models.py:118-144](file://safe4ai-pilot/app/db/models.py#L118-L144)
- [kinds.py:10-36](file://safe4ai-pilot/app/audit/kinds.py#L10-L36)
- [config.py:7-48](file://safe4ai-pilot/app/config.py#L7-L48)
- [audit_cleanup.py:35-83](file://safe4ai-pilot/scripts/audit_cleanup.py#L35-L83)
- [audit.ts:34-72](file://safe4ai-pilot/frontend/src/api/audit.ts#L34-L72)
- [stats.ts:20-62](file://safe4ai-pilot/frontend/src/api/stats.ts#L20-L62)
- [ActivityPage.tsx:83-110](file://safe4ai-pilot/frontend/src/pages/admin/ActivityPage.tsx#L83-L110)
- [useAuditStream.ts:5-15](file://safe4ai-pilot/frontend/src/hooks/useAuditStream.ts#L5-L15)
- [chat_routes.py:56-88](file://safe4ai-pilot/app/api/chat_routes.py#L56-L88)
- [chat_finalizer.py:14-71](file://safe4ai-pilot/app/services/chat_finalizer.py#L14-L71)
- [runtime_config.py:89-129](file://safe4ai-pilot/app/services/runtime_config.py#L89-L129)
- [provider_clients.py:52-240](file://safe4ai-pilot/app/services/provider_clients.py#L52-L240)

**Section sources**
- [main.py:63-101](file://safe4ai-pilot/app/main.py#L63-L101)
- [admin_routes.py:43](file://safe4ai-pilot/app/api/admin_routes.py#L43)
- [observability_routes.py:16](file://safe4ai-pilot/app/api/observability_routes.py#L16)
- [audit_routes.py:241-257](file://safe4ai-pilot/app/api/audit_routes.py#L241-L257)
- [models.py:118-144](file://safe4ai-pilot/app/db/models.py#L118-L144)
- [kinds.py:10-36](file://safe4ai-pilot/app/audit/kinds.py#L10-L36)
- [config.py:7-48](file://safe4ai-pilot/app/config.py#L7-L48)
- [audit_cleanup.py:35-83](file://safe4ai-pilot/scripts/audit_cleanup.py#L35-L83)
- [audit.ts:34-72](file://safe4ai-pilot/frontend/src/api/audit.ts#L34-L72)
- [stats.ts:20-62](file://safe4ai-pilot/frontend/src/api/stats.ts#L20-L62)
- [ActivityPage.tsx:83-110](file://safe4ai-pilot/frontend/src/pages/admin/ActivityPage.tsx#L83-L110)
- [useAuditStream.ts:5-15](file://safe4ai-pilot/frontend/src/hooks/useAuditStream.ts#L5-L15)

## Core Components
- Audit log retrieval endpoint: GET /admin/audit-logs with filters and pagination
- CSV export endpoint: GET /admin/audit-logs/export.csv for compliance reporting
- Statistics endpoint: GET /admin/stats aggregates query volume, latency, cost, and cache hits
- Observability cost statistics: GET /admin/stats/cost for token-based cost tracking
- Kind classification system: Canonical taxonomy for action_type → UI kind mapping
- Kind filtering: ?kind= parameter for filtering audit logs by action kind
- Kind counts endpoint: GET /admin/audit-logs/kind-counts for sidebar badge counts
- Time-series statistics: GET /admin/stats/timeseries for 14-day analytics
- Enhanced model tracking: captures actual chat model names instead of provider types
- Frontend clients: typed wrappers for audit listing, CSV export, and stats with kind filtering

**Updated** Added unified audit classification system with canonical taxonomy and enhanced statistics with time-series analytics

**Section sources**
- [admin_routes.py:359-467](file://safe4ai-pilot/app/api/admin_routes.py#L359-L467)
- [audit_routes.py:241-257](file://safe4ai-pilot/app/api/audit_routes.py#L241-L257)
- [observability_routes.py:48-56](file://safe4ai-pilot/app/api/observability_routes.py#L48-L56)
- [kinds.py:10-36](file://safe4ai-pilot/app/audit/kinds.py#L10-L36)
- [audit.ts:34-72](file://safe4ai-pilot/frontend/src/api/audit.ts#L34-L72)
- [stats.ts:20-62](file://safe4ai-pilot/frontend/src/api/stats.ts#L20-L62)
- [chat_routes.py:56-88](file://safe4ai-pilot/app/api/chat_routes.py#L56-L88)
- [chat_finalizer.py:14-71](file://safe4ai-pilot/app/services/chat_finalizer.py#L14-L71)

## Architecture Overview
The audit and monitoring endpoints are part of the admin and observability routers. They rely on SQLAlchemy ORM queries against PostgreSQL, with optional integration to external systems (e.g., Qdrant for vector operations). The frontend consumes these endpoints via typed API clients and displays real-time activity streams, statistics, and kind-filtered audit trails. The unified audit classification system provides canonical taxonomy mapping for consistent UI grouping and sidebar badge counts.

```mermaid
sequenceDiagram
participant FE as "Frontend"
participant API as "Admin Router"
participant AUDR as "Audit Router"
participant DB as "PostgreSQL"
participant KINDS as "Audit Kinds"
participant CFG as "Config"
FE->>API : GET /admin/audit-logs?start&end&user_id&kind&limit&offset
API->>CFG : Read rate limits and settings
API->>KINDS : Classify action_type to kind
API->>DB : Query AuditLog with filters and pagination
DB-->>API : Paginated rows
API-->>FE : JSON array of audit events
FE->>AUDR : GET /admin/audit-logs/kind-counts?start
AUDR->>DB : Group by kind with counts
DB-->>AUDR : Kind counts
AUDR-->>FE : Kind counts for sidebar badges
FE->>API : GET /admin/stats/timeseries?days=14
API->>DB : Aggregate daily query/user/cost buckets
DB-->>API : 14-day time-series data
API-->>FE : Time-series analytics
Note over KINDS,DB : Canonical taxonomy ensures consistent kind mapping
```

**Diagram sources**
- [admin_routes.py:359-431](file://safe4ai-pilot/app/api/admin_routes.py#L359-L431)
- [audit_routes.py:241-257](file://safe4ai-pilot/app/api/audit_routes.py#L241-L257)
- [kinds.py:21-36](file://safe4ai-pilot/app/audit/kinds.py#L21-L36)
- [config.py:7-48](file://safe4ai-pilot/app/config.py#L7-L48)

**Section sources**
- [admin_routes.py:359-431](file://safe4ai-pilot/app/api/admin_routes.py#L359-L431)
- [audit_routes.py:241-257](file://safe4ai-pilot/app/api/audit_routes.py#L241-L257)
- [kinds.py:21-36](file://safe4ai-pilot/app/audit/kinds.py#L21-L36)
- [config.py:7-48](file://safe4ai-pilot/app/config.py#L7-L48)

## Detailed Component Analysis

### Unified Audit Classification System
The audit classification system provides a canonical taxonomy that maps raw action_type values to UI kinds for consistent filtering and display across the admin interface.

**Canonical Audit Kinds:**
- query: chat_query, query
- upload: upload, document, ingest, reindex
- feedback: feedback
- login: login, logout, auth
- fallback: fallback
- admin: settings, user, admin, provider, review
- other: unmapped values

**Classification Functionality:**
- Case-insensitive mapping with whitespace stripping
- Prefix-based matching for flexible categorization
- Guaranteed mapping to known kinds only
- Single source of truth for kind filtering and counting

```mermaid
flowchart TD
Start(["Raw action_type"]) --> Clean["Strip and lowercase"]
Clean --> CheckQuery{"Matches 'chat_query' or 'query'?"}
CheckUpload{"Starts with 'upload', 'document', 'ingest', or 'reindex'?"}
CheckFeedback{"Starts with 'feedback'?"}
CheckLogin{"Starts with 'login', 'logout', or 'auth'?"}
CheckFallback{"Starts with 'fallback'?"}
CheckAdmin{"Starts with 'settings', 'user', 'admin', 'provider', or 'review'?"}
Default["Return 'other'"]
CheckQuery --> |Yes| ReturnQuery["Return 'query'"]
CheckQuery --> |No| CheckUpload
CheckUpload --> |Yes| ReturnUpload["Return 'upload'"]
CheckUpload --> |No| CheckFeedback
CheckFeedback --> |Yes| ReturnFeedback["Return 'feedback'"]
CheckFeedback --> |No| CheckLogin
CheckLogin --> |Yes| ReturnLogin["Return 'login'"]
CheckLogin --> |No| CheckFallback
CheckFallback --> |Yes| ReturnFallback["Return 'fallback'"]
CheckFallback --> |No| CheckAdmin
CheckAdmin --> |Yes| ReturnAdmin["Return 'admin'"]
CheckAdmin --> |No| Default
```

**Diagram sources**
- [kinds.py:21-36](file://safe4ai-pilot/app/audit/kinds.py#L21-L36)

**Section sources**
- [kinds.py:10-36](file://safe4ai-pilot/app/audit/kinds.py#L10-L36)

### Audit Log Retrieval Endpoint
- Method and URL: GET /admin/audit-logs
- Purpose: Retrieve paginated audit events with optional filters
- Authentication and roles: Requires admin role
- Rate limiting: Applied via decorator
- Query parameters:
  - start: datetime (inclusive lower bound)
  - end: datetime (inclusive upper bound)
  - user_id: string (filter by user identifier)
  - kind: string (filter by action kind - query, upload, feedback, login, fallback, admin, other)
  - limit: integer (default 100; capped at 1000)
  - offset: integer (default 0)
- Response: Array of audit event objects ordered by timestamp descending
- Filtering behavior:
  - Timestamp range filters applied when provided
  - User filter applied when provided
  - Kind filter applied using canonical taxonomy mapping
  - Pagination enforced with a maximum of 1000 records per request
- Enhanced model tracking: Now includes accurate model name identification
- Example request:
  - GET /admin/audit-logs?start=2024-01-01T00:00:00Z&end=2024-12-31T23:59:59Z&user_id=a1b2c3&kind=query&limit=500&offset=0
- Example response fields:
  - id, user_id, session_id, timestamp, action_type, query_text, latency_ms, model_used, trace_id

```mermaid
flowchart TD
Start(["Request: GET /admin/audit-logs"]) --> Parse["Parse query params<br/>start, end, user_id, kind, limit, offset"]
Parse --> Classify["Classify kind using canonical taxonomy"]
Classify --> Build["Build SQLAlchemy query<br/>order by timestamp desc"]
Build --> Filters{"Any filters?"}
Filters --> |Timestamp range| ApplyTS["Apply start/end filters"]
Filters --> |User ID| ApplyUser["Apply user_id filter"]
Filters --> |Kind| ApplyKind["Apply kind filter via taxonomy"]
Filters --> |None| Paginate["Apply offset/limit (<=1000)"]
ApplyTS --> Combine["Combine all filters"]
ApplyUser --> Combine
ApplyKind --> Combine
Paginate --> Combine
Combine --> Exec["Execute query"]
Exec --> Map["Map to response shape<br/>with enhanced model tracking"]
Map --> End(["Return JSON array"])
```

**Diagram sources**
- [admin_routes.py:359-392](file://safe4ai-pilot/app/api/admin_routes.py#L359-L392)
- [kinds.py:21-36](file://safe4ai-pilot/app/audit/kinds.py#L21-L36)

**Section sources**
- [admin_routes.py:359-392](file://safe4ai-pilot/app/api/admin_routes.py#L359-L392)
- [kinds.py:21-36](file://safe4ai-pilot/app/audit/kinds.py#L21-L36)

### Kind Counts Endpoint
- Method and URL: GET /admin/audit-logs/kind-counts
- Purpose: Provide kind counts for sidebar badges and filtering options
- Authentication and roles: Requires admin role
- Rate limiting: Applied via decorator
- Query parameters:
  - start: datetime (optional - inclusive lower bound for counting period)
  - end: datetime (optional - inclusive upper bound for counting period)
- Response: Object containing total count and per-kind counts
- Behavior:
  - Groups audit log entries by canonical kind classification
  - Returns counts for all seven kinds: query, upload, feedback, login, fallback, admin, other
  - Optional date range filtering for counts
  - Ensures sidebar counts match filtered audit log results
- Example request:
  - GET /admin/audit-logs/kind-counts?start=2024-01-01T00:00:00Z&end=2024-12-31T23:59:59Z
- Example response fields:
  - total, kinds: { query, upload, feedback, login, fallback, admin, other }

```mermaid
sequenceDiagram
participant FE as "Frontend"
participant AUDR as "Audit Router"
participant DB as "PostgreSQL"
FE->>AUDR : GET /admin/audit-logs/kind-counts?start&end
AUDR->>DB : Group AuditLog by kind with counts
DB-->>AUDR : Kind distribution with totals
AUDR-->>FE : Kind counts for sidebar badges
Note over FE,AUDR : Sidebar displays counts and enables kind filtering
```

**Diagram sources**
- [audit_routes.py:241-257](file://safe4ai-pilot/app/api/audit_routes.py#L241-L257)

**Section sources**
- [audit_routes.py:241-257](file://safe4ai-pilot/app/api/audit_routes.py#L241-L257)

### CSV Export Endpoint
- Method and URL: GET /admin/audit-logs/export.csv
- Purpose: Stream a CSV file containing audit events for a specified date range
- Authentication and roles: Requires admin role
- Rate limiting: Applied via decorator
- Query parameters:
  - start: datetime (optional)
  - end: datetime (optional)
- Behavior:
  - Orders by ascending timestamp
  - Limits rows to a fixed cap suitable for export
  - Streams CSV content as a file attachment
  - Includes enhanced model name tracking in export
- Example request:
  - GET /admin/audit-logs/export.csv?start=2024-01-01T00:00:00Z&end=2024-12-31T23:59:59Z
- Example response:
  - Content-Type: text/csv
  - Content-Disposition: attachment; filename="audit_logs_YYYYMMDD.csv"
  - Body: CSV rows with headers id, user_id, session_id, timestamp, action_type, query_text, latency_ms, model_used, trace_id

```mermaid
sequenceDiagram
participant FE as "Frontend"
participant API as "Admin Router"
participant DB as "PostgreSQL"
FE->>API : GET /admin/audit-logs/export.csv?start&end
API->>DB : Query AuditLog with date filters (ordered asc, limited rows)
DB-->>API : Rows with enhanced model tracking
API-->>FE : StreamingResponse (CSV)
```

**Diagram sources**
- [admin_routes.py:395-431](file://safe4ai-pilot/app/api/admin_routes.py#L395-L431)

**Section sources**
- [admin_routes.py:395-431](file://safe4ai-pilot/app/api/admin_routes.py#L395-L431)

### Statistics Endpoint
- Method and URL: GET /admin/stats
- Purpose: Aggregate system statistics for a given window
- Authentication and roles: Requires admin role
- Rate limiting: Applied via decorator
- Query parameters:
  - days: integer (default 30)
- Metrics included:
  - total_queries: count of audit log entries within the window
  - avg_latency_ms: average latency in milliseconds (rounded)
  - total_cost_usd: sum of agent run costs within the window
  - cache_total_hits: total semantic cache hit count
  - unique_users: distinct users who performed actions in the period
  - model_breakdown: enhanced model name breakdown for compliance reporting
- Enhanced model tracking: Provides detailed model usage analytics
- Example request:
  - GET /admin/stats?days=30
- Example response fields:
  - days, total_queries, avg_latency_ms, total_cost_usd, cache_total_hits, unique_users, model_breakdown

```mermaid
flowchart TD
StartStats(["Request: GET /admin/stats"]) --> Window["Compute cutoff = now - days"]
Window --> Queries["Count AuditLog rows >= cutoff"]
Window --> Latency["Avg latency_ms for AuditLog >= cutoff"]
Window --> Cost["Sum AgentRun.cost_usd for runs >= cutoff"]
Window --> Cache["Sum SemanticCache.hit_count"]
Window --> Users["Count distinct user_id"]
Window --> ModelBreakdown["Aggregate model_used counts"]
Queries --> Combine["Round and format metrics<br/>with model breakdown"]
Latency --> Combine
Cost --> Combine
Cache --> Combine
Users --> Combine
ModelBreakdown --> Combine
Combine --> EndStats(["Return stats JSON<br/>with enhanced model tracking"])
```

**Diagram sources**
- [admin_routes.py:439-467](file://safe4ai-pilot/app/api/admin_routes.py#L439-L467)

**Section sources**
- [admin_routes.py:439-467](file://safe4ai-pilot/app/api/admin_routes.py#L439-L467)

### Observability Cost Statistics Endpoint
- Method and URL: GET /admin/stats/cost
- Purpose: Token-based cost statistics using a configured cost per 1K tokens
- Authentication and roles: Requires admin role
- Rate limiting: Applied via decorator
- Query parameters:
  - days: integer (default 30)
- Behavior:
  - Delegates to a cost tracker utility to compute totals and averages
  - Includes enhanced model name tracking for cost attribution
- Example request:
  - GET /admin/stats/cost?days=30

**Section sources**
- [observability_routes.py:48-56](file://safe4ai-pilot/app/api/observability_routes.py#L48-L56)

### Time-Series Statistics Endpoint
- Method and URL: GET /admin/stats/timeseries
- Purpose: Provide 14-day daily analytics for queries, unique users, and cost
- Authentication and roles: Requires admin role
- Rate limiting: Applied via decorator
- Query parameters:
  - days: integer (default 14, min 1, max 90)
- Response: Object containing days count and series array with daily buckets
- Behavior:
  - Returns calendar day buckets in UTC timezone
  - Last bucket may be partial (current day)
  - Zero-fills missing days with empty buckets
  - Aggregates queries, unique users, and cost_usd per day
  - Calendar-aligned buckets ensure consistent time-series visualization
- Example request:
  - GET /admin/stats/timeseries?days=14
- Example response fields:
  - days, series: [{ date, queries, unique_users, cost_usd }]

```mermaid
flowchart TD
StartTS(["Request: GET /admin/stats/timeseries"]) --> Validate["Validate days parameter (1-90)"]
Validate --> Calc["Calculate date range<br/>today - (days-1) to today"]
Calc --> Build["Build 14-day calendar range"]
Build --> QueryAudit["Aggregate AuditLog by date<br/>count queries & unique users"]
Build --> QueryCost["Aggregate AgentRun by date<br/>sum cost_usd"]
QueryAudit --> Merge["Merge audit and cost aggregations"]
QueryCost --> Merge
Merge --> Fill["Zero-fill missing dates"]
Fill --> Format["Format as series array"]
Format --> EndTS(["Return time-series JSON"])
```

**Diagram sources**
- [audit_routes.py:241-257](file://safe4ai-pilot/app/api/audit_routes.py#L241-L257)

**Section sources**
- [audit_routes.py:241-257](file://safe4ai-pilot/app/api/audit_routes.py#L241-L257)

### Enhanced Model Tracking Implementation
**Updated** The audit system now captures accurate model names instead of generic provider types

The enhanced model tracking system ensures precise attribution of audit events to specific chat models:

- **Chat Routes**: Captures runtime chat model configuration for audit logging
- **Chat Finalizer**: Persists model name in single transaction with audit log and cost tracking
- **Runtime Configuration**: Loads actual model names from persistent configuration
- **Provider Clients**: Supports both Ollama and OpenAI-compatible providers with accurate model identification

```mermaid
flowchart TD
StartModel["Chat Request Process"] --> LoadRuntime["Load Runtime Config<br/>runtime_config.py"]
LoadRuntime --> GetChatModel["Extract chat_model<br/>from RuntimeConfig"]
GetChatModel --> CreateAudit["_write_audit_log()<br/>chat_routes.py"]
CreateAudit --> Finalize["finalize_chat_run()<br/>chat_finalizer.py"]
Finalize --> PersistModel["Persist model_used field<br/>in AuditLog"]
PersistModel --> EndModel["Enhanced Audit Trail"]
```

**Diagram sources**
- [chat_routes.py:312-332](file://safe4ai-pilot/app/api/chat_routes.py#L312-L332)
- [chat_finalizer.py:14-71](file://safe4ai-pilot/app/services/chat_finalizer.py#L14-L71)
- [runtime_config.py:89-129](file://safe4ai-pilot/app/services/runtime_config.py#L89-L129)

**Section sources**
- [chat_routes.py:56-88](file://safe4ai-pilot/app/api/chat_routes.py#L56-L88)
- [chat_routes.py:312-332](file://safe4ai-pilot/app/api/chat_routes.py#L312-L332)
- [chat_finalizer.py:14-71](file://safe4ai-pilot/app/services/chat_finalizer.py#L14-L71)
- [runtime_config.py:89-129](file://safe4ai-pilot/app/services/runtime_config.py#L89-L129)
- [provider_clients.py:52-240](file://safe4ai-pilot/app/services/provider_clients.py#L52-L240)

### Frontend Integration Examples
- Audit listing:
  - Uses a typed client to fetch paginated events with optional start filter
  - Implements kind filtering with canonical taxonomy mapping
  - Displays enhanced model name information in audit events
  - Integrates with kind-counts endpoint for sidebar badge updates
- CSV export:
  - Initiates a download of the exported CSV file with model tracking
- Stats mapping:
  - Transforms backend stats to a normalized frontend shape
  - Includes model breakdown data for compliance reporting
  - Consumes time-series endpoint for 14-day analytics visualization
- Kind filtering UI:
  - Sidebar displays kind counts with badge numbers
  - Clickable kind buttons filter audit log results
  - Real-time badge updates when filters change

**Section sources**
- [audit.ts:34-72](file://safe4ai-pilot/frontend/src/api/audit.ts#L34-L72)
- [stats.ts:20-62](file://safe4ai-pilot/frontend/src/api/stats.ts#L20-L62)
- [ActivityPage.tsx:83-110](file://safe4ai-pilot/frontend/src/pages/admin/ActivityPage.tsx#L83-L110)
- [useAuditStream.ts:5-15](file://safe4ai-pilot/frontend/src/hooks/useAuditStream.ts#L5-L15)

## Dependency Analysis
- Backend routers depend on:
  - SQLAlchemy ORM models for AuditLog, AgentRun, and SemanticCache
  - Config settings for rate limits and retention
  - Rate limiter decorator for endpoint protection
  - Enhanced model tracking through runtime configuration
  - Canonical audit kinds taxonomy for consistent classification
- Frontend clients depend on:
  - Backend endpoints for audit listing, CSV export, and kind counts
  - Stats endpoint for system metrics with model breakdown
  - Time-series endpoint for 14-day analytics visualization
- Cleanup and retention:
  - Automated deletion of stale audit logs and cache entries
  - Audit summary log written during cleanup
- Model tracking dependencies:
  - Runtime configuration loading for actual model names
  - Provider client abstraction for different model types

```mermaid
graph LR
AR["admin_routes.py"] --> M["models.py (AuditLog, AgentRun, SemanticCache)"]
OR["observability_routes.py"] --> M
AUDR["audit_routes.py"] --> M
AUDR --> KINDS["kinds.py (canonical taxonomy)"]
AR --> CFG["config.py"]
OR --> CFG
AUDR --> CFG
FE_AUD["frontend audit.ts"] --> AR
FE_AUD --> AUDR
FE_STS["frontend stats.ts"] --> OR
FE_STS --> AUDR
CLEAN["audit_cleanup.py"] --> M
CR["chat_routes.py"] --> CF["chat_finalizer.py"]
CR --> RC["runtime_config.py"]
CF --> M
RC --> PC["provider_clients.py"]
```

**Diagram sources**
- [admin_routes.py:24-41](file://safe4ai-pilot/app/api/admin_routes.py#L24-L41)
- [observability_routes.py:13-14](file://safe4ai-pilot/app/api/observability_routes.py#L13-L14)
- [audit_routes.py:241-257](file://safe4ai-pilot/app/api/audit_routes.py#L241-L257)
- [models.py:118-144](file://safe4ai-pilot/app/db/models.py#L118-L144)
- [kinds.py:10-36](file://safe4ai-pilot/app/audit/kinds.py#L10-L36)
- [config.py:7-48](file://safe4ai-pilot/app/config.py#L7-L48)
- [audit.ts:1-1](file://safe4ai-pilot/frontend/src/api/audit.ts#L1-L1)
- [stats.ts:1-1](file://safe4ai-pilot/frontend/src/api/stats.ts#L1-L1)
- [audit_cleanup.py:25-27](file://safe4ai-pilot/scripts/audit_cleanup.py#L25-L27)
- [chat_routes.py:56-88](file://safe4ai-pilot/app/api/chat_routes.py#L56-L88)
- [chat_finalizer.py:14-71](file://safe4ai-pilot/app/services/chat_finalizer.py#L14-L71)
- [runtime_config.py:89-129](file://safe4ai-pilot/app/services/runtime_config.py#L89-L129)
- [provider_clients.py:52-240](file://safe4ai-pilot/app/services/provider_clients.py#L52-L240)

**Section sources**
- [admin_routes.py:24-41](file://safe4ai-pilot/app/api/admin_routes.py#L24-L41)
- [observability_routes.py:13-14](file://safe4ai-pilot/app/api/observability_routes.py#L13-L14)
- [audit_routes.py:241-257](file://safe4ai-pilot/app/api/audit_routes.py#L241-L257)
- [models.py:118-144](file://safe4ai-pilot/app/db/models.py#L118-L144)
- [kinds.py:10-36](file://safe4ai-pilot/app/audit/kinds.py#L10-L36)
- [config.py:7-48](file://safe4ai-pilot/app/config.py#L7-L48)
- [audit.ts:1-1](file://safe4ai-pilot/frontend/src/api/audit.ts#L1-L1)
- [stats.ts:1-1](file://safe4ai-pilot/frontend/src/api/stats.ts#L1-L1)
- [audit_cleanup.py:25-27](file://safe4ai-pilot/scripts/audit_cleanup.py#L25-L27)
- [chat_routes.py:56-88](file://safe4ai-pilot/app/api/chat_routes.py#L56-L88)
- [chat_finalizer.py:14-71](file://safe4ai-pilot/app/services/chat_finalizer.py#L14-L71)
- [runtime_config.py:89-129](file://safe4ai-pilot/app/services/runtime_config.py#L89-L129)
- [provider_clients.py:52-240](file://safe4ai-pilot/app/services/provider_clients.py#L52-L240)

## Performance Considerations
- Pagination limit: The audit retrieval endpoint caps the limit at 1000 records per request to prevent excessive loads.
- Sorting and indexing: Results are sorted by timestamp descending; timestamps are indexed in the database model to support efficient filtering and ordering.
- Export size limits: The CSV export endpoint limits the number of rows returned to a reasonable cap for streaming performance.
- Retention and cleanup: Automated cleanup removes old audit logs and cache entries, reducing long-term query load and storage overhead.
- Rate limiting: Decorators apply rate limits to protect endpoints from abuse.
- Enhanced model tracking: Efficient model name storage and indexing for accurate audit trail analysis without performance degradation.
- Kind classification caching: Canonical taxonomy provides O(1) classification for optimal filtering performance.
- Time-series aggregation: Pre-computed daily buckets reduce query complexity for analytics visualization.

## Troubleshooting Guide
Common issues and resolutions:
- Invalid date range:
  - Ensure start and end parameters are valid ISO 8601 timestamps and that start ≤ end.
  - The backend applies inclusive bounds; incorrect ordering may yield empty results.
- Excessive pagination:
  - The limit parameter is capped at 1000; requests exceeding this will be reduced automatically.
  - Use offset to navigate through pages and avoid requesting very large offsets.
- CSV export failures:
  - Verify date range parameters and confirm the export endpoint returns a CSV file with appropriate headers.
  - Large date ranges may still be subject to internal row limits for export.
- Missing or stale data:
  - Confirm retention settings and cleanup schedules; old events may be archived or deleted according to policy.
- Cost statistics:
  - Ensure cost tracking is enabled and cost_per_1k_tokens is configured appropriately.
- Enhanced model tracking issues:
  - Verify runtime configuration loads correct chat_model values from persistent settings.
  - Check provider client configuration for accurate model name resolution.
  - Ensure chat finalizer receives and persists model names correctly.
- Kind filtering issues:
  - Verify canonical taxonomy mapping for custom action_type values.
  - Ensure kind parameter matches one of the seven canonical kinds: query, upload, feedback, login, fallback, admin, other.
  - Check that kind-counts endpoint returns counts for all expected kinds.
- Time-series errors:
  - Validate days parameter is between 1 and 90 (inclusive).
  - Ensure proper calendar alignment for UTC timezone bucketing.
  - Verify zero-filling logic for missing date ranges.

**Section sources**
- [admin_routes.py:378](file://safe4ai-pilot/app/api/admin_routes.py#L378)
- [admin_routes.py:409](file://safe4ai-pilot/app/api/admin_routes.py#L409)
- [audit_routes.py:241-257](file://safe4ai-pilot/app/api/audit_routes.py#L241-L257)
- [config.py:16-19](file://safe4ai-pilot/app/config.py#L16-L19)
- [audit_cleanup.py:35-83](file://safe4ai-pilot/scripts/audit_cleanup.py#L35-L83)
- [chat_routes.py:312-332](file://safe4ai-pilot/app/api/chat_routes.py#L312-L332)
- [chat_finalizer.py:14-71](file://safe4ai-pilot/app/services/chat_finalizer.py#L14-L71)
- [kinds.py:21-36](file://safe4ai-pilot/app/audit/kinds.py#L21-L36)

## Conclusion
The audit and monitoring API suite provides robust administrative oversight with enhanced model tracking capabilities and unified classification:
- Flexible audit log retrieval and CSV export for compliance reporting with accurate model attribution
- Comprehensive statistics for query volume, latency, cost, and cache performance with model breakdown
- Unified audit classification system with canonical taxonomy for consistent kind mapping
- Kind filtering via ?kind= parameter and kind-count endpoint for sidebar badge integration
- Daily time-series endpoint for 14-day analytics with zero-filling for missing dates
- Enhanced model tracking using actual chat model names instead of generic provider types
- Strong defaults for performance and safety, including pagination caps, retention policies, and rate limiting

These capabilities enable effective audit trail analysis, compliance workflows, and system health monitoring with precise model identification for regulatory compliance and cost allocation, while providing consistent kind-based filtering and rich time-series analytics for operational insights.

## Appendices

### API Reference Summary

- GET /admin/audit-logs
  - Filters: start, end, user_id, kind (query, upload, feedback, login, fallback, admin, other)
  - Pagination: limit (≤1000), offset
  - Response: Array of audit events with enhanced model tracking
  - Example: GET /admin/audit-logs?start=2024-01-01T00:00:00Z&end=2024-12-31T23:59:59Z&user_id=a1b2c3&kind=query&limit=500&offset=0

- GET /admin/audit-logs/kind-counts
  - Filters: start, end
  - Response: Kind counts object with total and per-kind breakdown
  - Example: GET /admin/audit-logs/kind-counts?start=2024-01-01T00:00:00Z&end=2024-12-31T23:59:59Z

- GET /admin/audit-logs/export.csv
  - Filters: start, end
  - Response: CSV file attachment with model tracking
  - Example: GET /admin/audit-logs/export.csv?start=2024-01-01T00:00:00Z&end=2024-12-31T23:59:59Z

- GET /admin/stats
  - Parameter: days (default 30)
  - Metrics: total_queries, avg_latency_ms, total_cost_usd, cache_total_hits, unique_users, model_breakdown
  - Example: GET /admin/stats?days=30

- GET /admin/stats/cost
  - Parameter: days (default 30)
  - Metrics: token-based cost statistics with model attribution
  - Example: GET /admin/stats/cost?days=30

- GET /admin/stats/timeseries
  - Parameter: days (default 14, min 1, max 90)
  - Metrics: 14-day daily buckets for queries, unique_users, cost_usd
  - Example: GET /admin/stats/timeseries?days=14

### Canonical Audit Kind Taxonomy

**Seven Canonical Kinds:**
- query: chat_query, query
- upload: upload, document, ingest, reindex
- feedback: feedback
- login: login, logout, auth
- fallback: fallback
- admin: settings, user, admin, provider, review
- other: all unmapped values

**Classification Logic:**
- Case-insensitive with whitespace stripping
- Prefix-based matching for flexible categorization
- Guaranteed mapping to known kinds only
- Single source of truth for UI consistency

### Data Model Overview (Audit and Related Entities)

```mermaid
erDiagram
AUDIT_LOG {
string id PK
string user_id FK
string session_id
timestamptz timestamp
string action_type
string query_text
jsonb response_metadata
int latency_ms
string model_used
string trace_id
}
AGENT_RUN {
string id PK
string session_id FK
timestamptz started_at
timestamptz finished_at
string status
text final_output
text error
float cost_usd
}
SEMANTIC_CACHE {
string id PK
vector query_embedding
text query_text
json response_json
json citations_json
json source_document_ids
json source_chunk_ids
timestamptz created_at
int hit_count
}
AUDIT_LOG ||--o{ AGENT_RUN : "used in cost aggregation"
AUDIT_LOG ||--o{ SEMANTIC_CACHE : "referenced by cache metrics"
```

**Diagram sources**
- [models.py:118-144](file://safe4ai-pilot/app/db/models.py#L118-L144)

### Enhanced Model Tracking Architecture

```mermaid
flowchart TD
RuntimeCfg["Runtime Configuration<br/>load_runtime_config()"] --> ChatModel["chat_model<br/>actual model name"]
ChatModel --> AuditLog["_write_audit_log()"]
ChatModel --> Finalize["finalize_chat_run()"]
AuditLog --> DBAudit["AuditLog.model_used<br/>persisted in database"]
Finalize --> DBAgent["AgentRun.cost_usd<br/>tracked with model"]
DBAudit --> Compliance["Enhanced Compliance Reporting"]
DBAgent --> CostTracking["Accurate Cost Attribution"]
```

**Diagram sources**
- [runtime_config.py:89-129](file://safe4ai-pilot/app/services/runtime_config.py#L89-L129)
- [chat_routes.py:56-88](file://safe4ai-pilot/app/api/chat_routes.py#L56-L88)
- [chat_finalizer.py:14-71](file://safe4ai-pilot/app/services/chat_finalizer.py#L14-L71)

### Time-Series Analytics Visualization

**Daily Bucket Structure:**
- Date: YYYY-MM-DD (UTC)
- Queries: Count of audit log entries for the day
- Unique Users: Distinct users who performed actions
- Cost USD: Sum of costs for agent runs (token-based)

**Bucket Characteristics:**
- Calendar-aligned (UTC timezone)
- Zero-filled for missing dates
- Partial bucket for current day
- Maximum 90 days range (validated)

**Section sources**
- [admin_routes.py:359-467](file://safe4ai-pilot/app/api/admin_routes.py#L359-L467)
- [audit_routes.py:241-257](file://safe4ai-pilot/app/api/audit_routes.py#L241-L257)
- [observability_routes.py:48-56](file://safe4ai-pilot/app/api/observability_routes.py#L48-L56)
- [kinds.py:10-36](file://safe4ai-pilot/app/audit/kinds.py#L10-L36)
- [models.py:118-144](file://safe4ai-pilot/app/db/models.py#L118-L144)
- [runtime_config.py:89-129](file://safe4ai-pilot/app/services/runtime_config.py#L89-L129)
- [chat_routes.py:56-88](file://safe4ai-pilot/app/api/chat_routes.py#L56-L88)
- [chat_finalizer.py:14-71](file://safe4ai-pilot/app/services/chat_finalizer.py#L14-L71)