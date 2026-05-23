# Feedback Collection and Analytics

<cite>
**Referenced Files in This Document**
- [feedback.py](file://safe4ai-pilot/observability/feedback.py)
- [observability_routes.py](file://safe4ai-pilot/app/api/observability_routes.py)
- [models.py](file://safe4ai-pilot/app/db/models.py)
- [useChat.ts](file://safe4ai-pilot/frontend/src/hooks/useChat.ts)
- [feedback.ts](file://safe4ai-pilot/frontend/src/api/feedback.ts)
- [FeedbackPage.tsx](file://safe4ai-pilot/frontend/src/pages/admin/FeedbackPage.tsx)
- [FeedbackListItem.tsx](file://safe4ai-pilot/frontend/src/components/admin/FeedbackListItem.tsx)
- [online_monitor.py](file://safe4ai-pilot/evaluation/online_monitor.py)
- [test_feedback.py](file://safe4ai-pilot/tests/test_feedback.py)
- [test_observability_routes.py](file://safe4ai-pilot/tests/test_observability_routes.py)
- [main.py](file://safe4ai-pilot/app/main.py)
</cite>

## Update Summary
**Changes Made**
- Added new negative feedback monitoring capability with lightweight count endpoint
- Implemented detailed trace lookup functionality for comprehensive feedback analysis
- Enhanced frontend integration with comprehensive trace visibility including latency metrics, model usage, cache hits, and timestamp information
- Updated administrative dashboard with advanced trace correlation capabilities

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Privacy and Compliance](#privacy-and-compliance)
10. [Conclusion](#conclusion)
11. [Appendices](#appendices)

## Introduction
This document explains the feedback collection and analytics system for the Private AI pilot. It covers how users provide feedback on query responses, how feedback is stored and categorized, and how administrators can inspect and analyze feedback. The system now includes advanced negative feedback monitoring, detailed trace correlation capabilities, and comprehensive administrative analytics. Privacy and compliance considerations are addressed to ensure responsible handling of feedback data.

## Project Structure
The feedback system spans three layers with enhanced administrative capabilities:
- Frontend: collects user ratings and optional comments, displays administrative feedback views with trace correlation, and provides real-time feedback monitoring.
- Backend API: validates and persists feedback, exposes administrative endpoints with negative feedback monitoring, detailed trace lookup, and integrates with analytics.
- Observability and persistence: stores feedback records, supports analytics queries, and enables trace correlation with audit logs.

```mermaid
graph TB
FE["Frontend<br/>useChat.ts, feedback.ts"] --> API["FastAPI Routes<br/>observability_routes.py"]
API --> Store["FeedbackStore<br/>feedback.py"]
Store --> DB["PostgreSQL Table<br/>query_feedback"]
API --> AdminUI["Admin Feedback Page<br/>FeedbackPage.tsx"]
API --> CountEndpoint["Negative Feedback Count<br/>/admin/feedback/count"]
API --> TraceEndpoint["Trace Lookup<br/>/admin/feedback/{feedback_id}/trace"]
Eval["Analytics Script<br/>online_monitor.py"] --> DB
```

**Diagram sources**
- [useChat.ts:95-102](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L95-L102)
- [feedback.ts:13-18](file://safe4ai-pilot/frontend/src/api/feedback.ts#L13-L18)
- [observability_routes.py:26-45](file://safe4ai-pilot/app/api/observability_routes.py#L26-L45)
- [feedback.py:16-71](file://safe4ai-pilot/observability/feedback.py#L16-L71)
- [models.py:146-156](file://safe4ai-pilot/app/db/models.py#L146-L156)
- [FeedbackPage.tsx:10-175](file://safe4ai-pilot/frontend/src/pages/admin/FeedbackPage.tsx#L10-L175)
- [observability_routes.py:53-69](file://safe4ai-pilot/app/api/observability_routes.py#L53-L69)
- [observability_routes.py:72-100](file://safe4ai-pilot/app/api/observability_routes.py#L72-L100)
- [online_monitor.py:87-109](file://safe4ai-pilot/evaluation/online_monitor.py#L87-L109)

**Section sources**
- [main.py:98-101](file://safe4ai-pilot/app/main.py#L98-L101)
- [observability_routes.py:16-57](file://safe4ai-pilot/app/api/observability_routes.py#L16-L57)
- [feedback.py:16-71](file://safe4ai-pilot/observability/feedback.py#L16-L71)
- [models.py:146-156](file://safe4ai-pilot/app/db/models.py#L146-L156)

## Core Components
- Feedback submission mechanism:
  - Frontend hook captures user ratings and posts them via the API with session and trace identifiers.
  - Backend route validates the request and delegates persistence to the FeedbackStore.
- Feedback storage and retrieval:
  - FeedbackStore writes a record to the query_feedback table and returns a generated identifier.
  - Administrative listing returns recent feedback rows for inspection with user email resolution.
- Advanced administrative capabilities:
  - Negative feedback monitoring with lightweight count endpoint for sidebar badges.
  - Detailed trace lookup correlating feedback with audit log data including latency, model usage, and cache hits.
- Analytics integration:
  - An offline monitor reads feedback counts to compute a user feedback ratio metric.
- Admin dashboard:
  - A dedicated page lists feedback, filters by rating, shows details for triage, and provides comprehensive trace correlation.

**Updated** Added negative feedback monitoring and detailed trace lookup functionality

**Section sources**
- [useChat.ts:95-102](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L95-L102)
- [feedback.ts:13-18](file://safe4ai-pilot/frontend/src/api/feedback.ts#L13-L18)
- [observability_routes.py:26-45](file://safe4ai-pilot/app/api/observability_routes.py#L26-L45)
- [feedback.py:16-71](file://safe4ai-pilot/observability/feedback.py#L16-L71)
- [observability_routes.py:53-69](file://safe4ai-pilot/app/api/observability_routes.py#L53-L69)
- [observability_routes.py:72-100](file://safe4ai-pilot/app/api/observability_routes.py#L72-L100)
- [online_monitor.py:87-109](file://safe4ai-pilot/evaluation/online_monitor.py#L87-L109)
- [FeedbackPage.tsx:10-175](file://safe4ai-pilot/frontend/src/pages/admin/FeedbackPage.tsx#L10-L175)

## Architecture Overview
The feedback lifecycle connects user actions to persistent storage, analytics, and advanced trace correlation:

```mermaid
sequenceDiagram
participant User as "User"
participant FE as "Frontend Hook<br/>useChat.ts"
participant API as "Observability Routes<br/>observability_routes.py"
participant Store as "FeedbackStore<br/>feedback.py"
participant DB as "PostgreSQL<br/>query_feedback"
participant Audit as "Audit Log<br/>audit_logs"
User->>FE : "Click thumbs up/down"
FE->>FE : "Collect session_id and trace_id"
FE->>API : "POST /feedback {session_id, trace_id, rating, comment}"
API->>Store : "store(session_id, user_id, trace_id, rating, comment)"
Store->>DB : "INSERT INTO query_feedback"
DB-->>Store : "OK"
Store-->>API : "feedback_id"
API-->>FE : "{id : feedback_id}"
FE-->>User : "Feedback acknowledged"
Note over API,DB : "Admin can access : "
API->>API : "/admin/feedback/count (negative count)"
API->>API : "/admin/feedback/{id}/trace (trace correlation)"
API->>DB : "SELECT * FROM query_feedback WHERE id = {id}"
API->>Audit : "SELECT * FROM audit_logs WHERE trace_id = {trace_id}"
Audit-->>API : "Latency, model, cache hit, timestamp"
API-->>FE : "Trace data for feedback item"
```

**Diagram sources**
- [useChat.ts:95-102](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L95-L102)
- [feedback.ts:13-18](file://safe4ai-pilot/frontend/src/api/feedback.ts#L13-L18)
- [observability_routes.py:26-35](file://safe4ai-pilot/app/api/observability_routes.py#L26-L35)
- [feedback.py:22-49](file://safe4ai-pilot/observability/feedback.py#L22-L49)
- [models.py:146-156](file://safe4ai-pilot/app/db/models.py#L146-L156)
- [observability_routes.py:53-69](file://safe4ai-pilot/app/api/observability_routes.py#L53-L69)
- [observability_routes.py:72-100](file://safe4ai-pilot/app/api/observability_routes.py#L72-L100)

## Detailed Component Analysis

### Feedback Submission Mechanism
- Frontend:
  - The chat hook sends a rating event along with the current session and trace identifiers.
  - The submission API call includes optional comment payload.
- Backend:
  - The route validates the request body against a Pydantic model and requires an authenticated user.
  - It delegates persistence to FeedbackStore and returns a feedback identifier.

```mermaid
flowchart TD
Start(["User rates response"]) --> Collect["Collect session_id and trace_id"]
Collect --> CallAPI["POST /feedback"]
CallAPI --> Validate["Validate request body"]
Validate --> Persist["FeedbackStore.store(...)"]
Persist --> ReturnID["Return feedback id"]
ReturnID --> Done(["Done"])
```

**Diagram sources**
- [useChat.ts:95-102](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L95-L102)
- [feedback.ts:13-18](file://safe4ai-pilot/frontend/src/api/feedback.ts#L13-L18)
- [observability_routes.py:26-35](file://safe4ai-pilot/app/api/observability_routes.py#L26-L35)
- [feedback.py:22-49](file://safe4ai-pilot/observability/feedback.py#L22-L49)

**Section sources**
- [useChat.ts:95-102](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L95-L102)
- [feedback.ts:13-18](file://safe4ai-pilot/frontend/src/api/feedback.ts#L13-L18)
- [observability_routes.py:19-35](file://safe4ai-pilot/app/api/observability_routes.py#L19-L35)

### Feedback Storage and Categorization
- Data model:
  - FeedbackRating enum defines positive/negative categories.
  - QueryFeedback table stores identifiers, trace/session/user linkage, rating, optional comment, and timestamps.
- Persistence:
  - FeedbackStore generates a UUID, constructs a record, commits to the database, and logs metadata.
  - Admin listing resolves user emails for better identification.

```mermaid
classDiagram
class FeedbackRating {
+positive
+negative
}
class QueryFeedback {
+string id
+string trace_id
+string session_id
+string user_id
+FeedbackRating rating
+string comment
+datetime created_at
}
class FeedbackStore {
+store(session_id, user_id, trace_id, rating, comment) string
+list_for_admin(db, limit) dict[]
}
FeedbackStore --> QueryFeedback : "creates"
FeedbackRating <.. QueryFeedback : "uses"
```

**Diagram sources**
- [models.py:41-43](file://safe4ai-pilot/app/db/models.py#L41-L43)
- [models.py:146-156](file://safe4ai-pilot/app/db/models.py#L146-L156)
- [feedback.py:16-71](file://safe4ai-pilot/observability/feedback.py#L16-L71)

**Section sources**
- [models.py:41-43](file://safe4ai-pilot/app/db/models.py#L41-L43)
- [models.py:146-156](file://safe4ai-pilot/app/db/models.py#L146-L156)
- [feedback.py:16-71](file://safe4ai-pilot/observability/feedback.py#L16-L71)

### Advanced Administrative Feedback Capabilities

#### Negative Feedback Monitoring
- Lightweight count endpoint:
  - `/admin/feedback/count` returns only negative feedback count for sidebar badges.
  - Uses SQL aggregation to efficiently count negative ratings without loading full feedback data.
  - Admin-only endpoint with rate limiting for security and performance.

```mermaid
flowchart TD
Start(["Admin requests count"]) --> Auth["Verify admin role"]
Auth --> Query["SQL COUNT query for negative ratings"]
Query --> Calc["Calculate negative count"]
Calc --> Return["Return {negative: count}"]
Return --> End(["Done"])
```

**Diagram sources**
- [observability_routes.py:53-69](file://safe4ai-pilot/app/api/observability_routes.py#L53-L69)

#### Detailed Trace Lookup
- Comprehensive trace correlation:
  - `/admin/feedback/{feedback_id}/trace` returns audit log data for a specific feedback item.
  - Correlates feedback trace_id with audit_logs to provide latency metrics, model usage, cache hits, and timestamps.
  - Handles cases where no audit log entry exists with appropriate fallback responses.

```mermaid
sequenceDiagram
participant Admin as "Admin User"
participant API as "GET /admin/feedback/{id}/trace"
participant DB as "Database"
participant Audit as "Audit Logs"
Admin->>API : "Request trace for feedback {id}"
API->>DB : "Find feedback by id"
DB-->>API : "Feedback record with trace_id"
API->>Audit : "Find audit log by trace_id"
Audit-->>API : "Audit log data (latency, model, cache, timestamp)"
API-->>Admin : "Trace details or not found"
```

**Diagram sources**
- [observability_routes.py:72-100](file://safe4ai-pilot/app/api/observability_routes.py#L72-L100)

**Section sources**
- [observability_routes.py:53-69](file://safe4ai-pilot/app/api/observability_routes.py#L53-L69)
- [observability_routes.py:72-100](file://safe4ai-pilot/app/api/observability_routes.py#L72-L100)
- [test_observability_routes.py:182-248](file://safe4ai-pilot/tests/test_observability_routes.py#L182-L248)
- [test_observability_routes.py:265-391](file://safe4ai-pilot/tests/test_observability_routes.py#L265-L391)

### Administrative Feedback Dashboard
- Listing and filtering:
  - Admin endpoint returns recent feedback rows ordered by creation time with user email resolution.
  - The admin page renders a list with up/down filters and selected item details.
- Enhanced detail view:
  - Displays user identity, session and trace identifiers, rating, and optional comment.
  - Includes comprehensive trace correlation with latency metrics, model usage, cache hits, and timestamp information.
  - Provides navigation between feedback items and detailed trace analysis.

```mermaid
sequenceDiagram
participant Admin as "Admin User"
participant UI as "FeedbackPage.tsx"
participant API as "GET /admin/feedback"
participant Store as "FeedbackStore.list_for_admin"
participant DB as "PostgreSQL"
Admin->>UI : "Open Feedback page"
UI->>API : "Fetch feedback list"
API->>Store : "list_for_admin(db, limit)"
Store->>DB : "SELECT ... ORDER BY created_at DESC LIMIT ..."
DB-->>Store : "Rows with user emails"
Store-->>API : "Plain dicts with user resolution"
API-->>UI : "Render list and details"
UI->>API : "GET /admin/feedback/{id}/trace"
API->>DB : "Correlate feedback trace_id with audit_logs"
DB-->>API : "Audit log data"
API-->>UI : "Trace details for selected feedback"
```

**Diagram sources**
- [FeedbackPage.tsx:10-175](file://safe4ai-pilot/frontend/src/pages/admin/FeedbackPage.tsx#L10-L175)
- [feedback.ts:30-43](file://safe4ai-pilot/frontend/src/api/feedback.ts#L30-L43)
- [observability_routes.py:38-45](file://safe4ai-pilot/app/api/observability_routes.py#L38-L45)
- [feedback.py:51-70](file://safe4ai-pilot/observability/feedback.py#L51-L70)
- [observability_routes.py:72-100](file://safe4ai-pilot/app/api/observability_routes.py#L72-L100)

**Section sources**
- [FeedbackPage.tsx:10-175](file://safe4ai-pilot/frontend/src/pages/admin/FeedbackPage.tsx#L10-L175)
- [FeedbackListItem.tsx:1-30](file://safe4ai-pilot/frontend/src/components/admin/FeedbackListItem.tsx#L1-L30)
- [feedback.ts:30-43](file://safe4ai-pilot/frontend/src/api/feedback.ts#L30-L43)
- [observability_routes.py:38-45](file://safe4ai-pilot/app/api/observability_routes.py#L38-L45)
- [feedback.py:51-70](file://safe4ai-pilot/observability/feedback.py#L51-L70)

### Automated Feedback Processing and Insights
- Offline analytics:
  - The monitor script computes a user feedback ratio by aggregating positive and negative counts over a configurable window.
- Integration points:
  - Admin stats and dashboards can leverage the same data source to present trends and ratios.
  - Negative feedback count endpoint provides real-time monitoring for admin interfaces.

```mermaid
flowchart TD
Start(["Run monitor"]) --> Query["Query query_feedback counts by rating"]
Query --> Compute["Compute positive/(positive+negative)"]
Compute --> Alert{"Threshold exceeded?"}
Alert --> |Yes| Warn["Emit warning"]
Alert --> |No| OK["No alert"]
Compute --> Save["Write results to JSON"]
Save --> End(["Done"])
```

**Diagram sources**
- [online_monitor.py:87-109](file://safe4ai-pilot/evaluation/online_monitor.py#L87-L109)
- [online_monitor.py:112-175](file://safe4ai-pilot/evaluation/online_monitor.py#L112-L175)

**Section sources**
- [online_monitor.py:87-109](file://safe4ai-pilot/evaluation/online_monitor.py#L87-L109)
- [online_monitor.py:112-175](file://safe4ai-pilot/evaluation/online_monitor.py#L112-L175)

### Practical Examples
- Feedback dashboard creation:
  - Use the admin feedback endpoint to populate a list with filters and pagination.
  - Render a detail panel with user, session, trace, rating, and comment.
  - Integrate negative feedback count endpoint for real-time sidebar badges.
- Enhanced trace correlation:
  - Use the trace lookup endpoint to correlate feedback with system performance metrics.
  - Display latency, model usage, and cache hit information for troubleshooting.
- Sentiment analysis integration:
  - Extend the backend to optionally tag feedback with sentiment scores derived from the comment text.
  - Store sentiment metadata alongside the feedback record for richer analytics.
- Trend analysis over time:
  - Aggregate feedback counts by day/week to produce a time series.
  - Combine with latency and retrieval metrics to correlate user satisfaction with system performance.

**Updated** Added negative feedback monitoring and trace correlation examples

## Dependency Analysis
- Router registration:
  - The observability router is included in the main application.
- Route dependencies:
  - Feedback submission requires an authenticated user and a validated request body.
  - Admin listing requires admin role.
  - Negative feedback count endpoint requires admin role with lightweight query.
  - Trace lookup endpoint requires admin role and performs audit log correlation.
- Persistence dependencies:
  - FeedbackStore depends on SQLAlchemy session and the QueryFeedback model.
  - Trace lookup correlates with AuditLog model for comprehensive system analysis.

```mermaid
graph LR
Main["app/main.py"] --> Routes["app/api/observability_routes.py"]
Routes --> Store["observability/feedback.py"]
Store --> Models["app/db/models.py"]
FE["frontend/src/api/feedback.ts"] --> Routes
FE2["frontend/src/hooks/useChat.ts"] --> Routes
Admin["frontend/src/pages/admin/FeedbackPage.tsx"] --> Routes
Count["/admin/feedback/count"] --> Routes
Trace["/admin/feedback/{id}/trace"] --> Routes
```

**Diagram sources**
- [main.py:98-101](file://safe4ai-pilot/app/main.py#L98-L101)
- [observability_routes.py:16-57](file://safe4ai-pilot/app/api/observability_routes.py#L16-L57)
- [feedback.py:16-71](file://safe4ai-pilot/observability/feedback.py#L16-L71)
- [models.py:146-156](file://safe4ai-pilot/app/db/models.py#L146-L156)
- [feedback.ts:13-18](file://safe4ai-pilot/frontend/src/api/feedback.ts#L13-L18)
- [useChat.ts:95-102](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L95-L102)
- [FeedbackPage.tsx:10-175](file://safe4ai-pilot/frontend/src/pages/admin/FeedbackPage.tsx#L10-L175)

**Section sources**
- [main.py:98-101](file://safe4ai-pilot/app/main.py#L98-L101)
- [observability_routes.py:26-45](file://safe4ai-pilot/app/api/observability_routes.py#L26-L45)
- [feedback.py:16-71](file://safe4ai-pilot/observability/feedback.py#L16-L71)
- [models.py:146-156](file://safe4ai-pilot/app/db/models.py#L146-L156)

## Performance Considerations
- Database indexing:
  - The query_feedback table includes an index on trace_id to optimize trace-scoped analytics.
  - Audit log table includes indexes on trace_id and timestamp for efficient trace correlation.
- Query efficiency:
  - Admin listing orders by creation time and applies a limit to keep responses fast.
  - Negative feedback count uses lightweight SQL aggregation to minimize database load.
  - Trace lookup performs efficient correlation using trace_id matching.
- Frontend caching:
  - The admin page refreshes periodically to surface new feedback without manual reloads.
  - Trace data caching reduces repeated API calls for the same feedback items.

**Updated** Added performance considerations for new endpoints and trace correlation

## Troubleshooting Guide
- Submission failures:
  - Verify that the request includes session_id, trace_id, and a valid rating value.
  - Ensure the user is authenticated for feedback submission.
- Missing feedback in admin view:
  - Confirm the limit and ordering behavior; adjust refetch intervals if needed.
- Negative feedback count issues:
  - Verify admin authentication for `/admin/feedback/count` endpoint.
  - Check database connectivity and that POSTGRES_URL is configured for the monitor script.
- Trace lookup failures:
  - Verify admin authentication for `/admin/feedback/{id}/trace` endpoint.
  - Check that audit log entries exist for the feedback trace_id.
  - Ensure audit log table contains latency, model, and cache hit information.
- Analytics gaps:
  - Check database connectivity and that POSTGRES_URL is configured for the monitor script.

**Updated** Added troubleshooting for new endpoints and trace correlation

**Section sources**
- [observability_routes.py:26-35](file://safe4ai-pilot/app/api/observability_routes.py#L26-L35)
- [FeedbackPage.tsx:10-175](file://safe4ai-pilot/frontend/src/pages/admin/FeedbackPage.tsx#L10-L175)
- [online_monitor.py:119-122](file://safe4ai-pilot/evaluation/online_monitor.py#L119-L122)

## Privacy and Compliance
- Data minimization:
  - Feedback records include identifiers sufficient for tracing and triage but avoid embedding sensitive personal data in comments.
  - Negative feedback count endpoint returns only aggregated counts without exposing individual feedback details.
- Anonymization:
  - Consider deidentifying user_id in dashboards and reports; retain only aggregated metrics.
  - Trace correlation respects user privacy by only exposing system-level metrics (latency, model, cache hit).
- Access control:
  - Admin-only endpoints restrict visibility of feedback to authorized personnel.
  - Rate limiting protects endpoints from abuse while maintaining functionality.
- Retention and deletion:
  - Align feedback retention with organizational policies; provide mechanisms to purge or anonymize old records.

**Updated** Added privacy considerations for new endpoints and trace correlation

## Conclusion
The feedback system provides a robust foundation for capturing user satisfaction signals, persisting them securely, and enabling administrative oversight and automated analytics. The enhanced system now includes advanced negative feedback monitoring, comprehensive trace correlation capabilities, and detailed administrative insights. By integrating feedback with operational metrics and ensuring strong privacy controls, teams can continuously improve the system's quality and reliability while maintaining strict security and compliance standards.

## Appendices

### API Definitions
- Submit feedback
  - Method: POST
  - Endpoint: /feedback
  - Body fields: session_id, trace_id, rating, comment (optional)
  - Response: feedback identifier
- List feedback (admin)
  - Method: GET
  - Endpoint: /admin/feedback
  - Response: array of feedback entries with user, session, trace, rating, comment, and timestamp
- Negative feedback count (admin)
  - Method: GET
  - Endpoint: /admin/feedback/count
  - Response: {negative: count} - lightweight count for sidebar badges
- Trace lookup (admin)
  - Method: GET
  - Endpoint: /admin/feedback/{feedback_id}/trace
  - Response: {found: boolean, traceId: string, latencyMs?: number, modelUsed?: string, timestamp?: string, actionType?: string, cacheHit?: boolean}

**Updated** Added new endpoints for negative feedback monitoring and trace correlation

**Section sources**
- [observability_routes.py:19-35](file://safe4ai-pilot/app/api/observability_routes.py#L19-L35)
- [observability_routes.py:38-45](file://safe4ai-pilot/app/api/observability_routes.py#L38-L45)
- [observability_routes.py:53-69](file://safe4ai-pilot/app/api/observability_routes.py#L53-L69)
- [observability_routes.py:72-100](file://safe4ai-pilot/app/api/observability_routes.py#L72-L100)

### Testing References
- Unit tests validate FeedbackStore behavior, including unique feedback IDs, optional comments, and admin listing projection.
- Test coverage includes negative feedback count endpoint with admin authentication and error handling.
- Test coverage includes trace lookup endpoint with audit log correlation and various failure scenarios.

**Updated** Added testing references for new endpoints

**Section sources**
- [test_feedback.py:19-122](file://safe4ai-pilot/tests/test_feedback.py#L19-L122)
- [test_observability_routes.py:182-248](file://safe4ai-pilot/tests/test_observability_routes.py#L182-L248)
- [test_observability_routes.py:265-391](file://safe4ai-pilot/tests/test_observability_routes.py#L265-L391)