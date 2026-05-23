# Data Flow Architecture

<cite>
**Referenced Files in This Document**
- [README.md](file://safe4ai-pilot/README.md)
- [architecture.md](file://safe4ai-pilot/docs/architecture.md)
- [main.py](file://safe4ai-pilot/app/main.py)
- [config.py](file://safe4ai-pilot/app/config.py)
- [ingestion_service.py](file://safe4ai-pilot/app/services/ingestion_service.py)
- [rag_pipeline.py](file://safe4ai-pilot/app/services/rag_pipeline.py)
- [hybrid_retriever.py](file://safe4ai-pilot/app/components/hybrid_retriever.py)
- [semantic_cache.py](file://safe4ai-pilot/app/services/semantic_cache.py)
- [models.py](file://safe4ai-pilot/app/db/models.py)
- [input_guard.py](file://safe4ai-pilot/app/security/input_guard.py)
- [upload_validator.py](file://safe4ai-pilot/app/security/upload_validator.py)
- [chat_routes.py](file://safe4ai-pilot/app/api/chat_routes.py)
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
This document describes the data flow architecture of the Private AI system with a focus on data movement, transformation, and processing pipelines. It covers:
- Ingestion pipeline from file upload through OCR processing to vector embedding storage
- Query processing flow from user input through security validation to response generation
- Hybrid retrieval architecture combining dense and sparse vector search with Qdrant and pgvector
- Semantic caching mechanism and its role in reducing query latency
- Data validation rules, transformation logic, and error handling
- Data consistency guarantees, transaction boundaries, and audit trail maintenance
- Relationship between data stores and their specific use cases

## Project Structure
The system is organized around a FastAPI backend, a React frontend, and supporting services:
- Backend: FastAPI application with routers, services, components, security guards, and database models
- Vector stores: Qdrant for dense ANN retrieval and pgvector-backed semantic cache
- Embedding and LLM: Ollama for embeddings and text generation
- Observability: Health checks, tracing, and audit logging

```mermaid
graph TB
subgraph "Frontend"
FE["React SPA<br/>frontend/src"]
end
subgraph "Backend"
API["FastAPI app<br/>app/main.py"]
Routes["Chat routes<br/>app/api/chat_routes.py"]
Services["Services<br/>app/services/*"]
Components["Components<br/>app/components/*"]
Security["Security guards<br/>app/security/*"]
DB["PostgreSQL + pgvector<br/>app/db/models.py"]
end
subgraph "External Services"
Ollama["Ollama<br/>Embeddings & LLM"]
Qdrant["Qdrant<br/>Dense vectors"]
end
FE --> API
API --> Routes
Routes --> Services
Services --> Components
Services --> DB
Components --> Qdrant
Components --> Ollama
Services --> Ollama
DB --> Ollama
```

**Diagram sources**
- [main.py:63-101](file://safe4ai-pilot/app/main.py#L63-L101)
- [chat_routes.py:115-148](file://safe4ai-pilot/app/api/chat_routes.py#L115-L148)
- [hybrid_retriever.py:14-29](file://safe4ai-pilot/app/components/hybrid_retriever.py#L14-L29)
- [rag_pipeline.py:34-56](file://safe4ai-pilot/app/services/rag_pipeline.py#L34-L56)
- [models.py:104-116](file://safe4ai-pilot/app/db/models.py#L104-L116)

**Section sources**
- [README.md:1-133](file://safe4ai-pilot/README.md#L1-L133)
- [architecture.md:1-45](file://safe4ai-pilot/docs/architecture.md#L1-L45)
- [main.py:63-101](file://safe4ai-pilot/app/main.py#L63-L101)

## Core Components
- Ingestion service orchestrates background ingestion jobs, updates statuses, and coordinates the RAG pipeline
- RAG pipeline performs document loading, chunking, OCR gating, embedding, and persistence
- Hybrid retriever combines dense Qdrant ANN with sparse BM25 indexing for robust retrieval
- Semantic cache leverages pgvector similarity to accelerate repeated queries
- Security guards validate uploads and sanitize queries
- Database models define schemas for documents, chunks, audit logs, sessions, and caches

**Section sources**
- [ingestion_service.py:21-88](file://safe4ai-pilot/app/services/ingestion_service.py#L21-L88)
- [rag_pipeline.py:62-150](file://safe4ai-pilot/app/services/rag_pipeline.py#L62-L150)
- [hybrid_retriever.py:14-145](file://safe4ai-pilot/app/components/hybrid_retriever.py#L14-L145)
- [semantic_cache.py:14-104](file://safe4ai-pilot/app/services/semantic_cache.py#L14-L104)
- [models.py:75-116](file://safe4ai-pilot/app/db/models.py#L75-L116)

## Architecture Overview
The system separates concerns across ingestion and query paths, with explicit security layers and dual vector stores for retrieval and caching.

```mermaid
graph TB
U["User"]
FE["Frontend"]
API["FastAPI app"]
IR["Input Guard<br/>input_guard.py"]
QR["Query Router<br/>services/query_router.py"]
SR["Semantic Cache<br/>semantic_cache.py"]
RP["RAG Pipeline<br/>rag_pipeline.py"]
HR["Hybrid Retriever<br/>hybrid_retriever.py"]
QD["Qdrant"]
PG["PostgreSQL + pgvector"]
OLA["Ollama"]
U --> FE --> API
API --> IR
API --> QR
API --> SR
API --> RP
RP --> HR
HR --> QD
RP --> OLA
SR --> PG
RP --> PG
HR --> PG
API --> PG
```

**Diagram sources**
- [architecture.md:13-28](file://safe4ai-pilot/docs/architecture.md#L13-L28)
- [input_guard.py:24-49](file://safe4ai-pilot/app/security/input_guard.py#L24-L49)
- [semantic_cache.py:14-26](file://safe4ai-pilot/app/services/semantic_cache.py#L14-L26)
- [rag_pipeline.py:34-56](file://safe4ai-pilot/app/services/rag_pipeline.py#L34-L56)
- [hybrid_retriever.py:14-29](file://safe4ai-pilot/app/components/hybrid_retriever.py#L14-L29)

## Detailed Component Analysis

### Ingestion Pipeline: From Upload to Vector Storage
End-to-end ingestion transforms raw files into searchable chunks and embeddings.

```mermaid
sequenceDiagram
participant Client as "Client"
participant API as "FastAPI app"
participant ISvc as "IngestionService"
participant Pipe as "RagPipeline"
participant HR as "HybridRetriever"
participant QD as "Qdrant"
participant DB as "PostgreSQL"
Client->>API : "POST /upload"
API->>ISvc : "run_ingestion(doc_id, job_id, file_path, ...)"
ISvc->>DB : "Set job/document status to embedding"
ISvc->>Pipe : "ingest(file_path, doc_id, filename, uploaded_by)"
Pipe->>Pipe : "Load + Chunk"
Pipe->>Pipe : "OCR quality gate (if needed)"
Pipe->>Pipe : "Embed batch via Ollama"
Pipe->>QD : "Upsert vectors + payload"
Pipe->>DB : "Insert DocumentChunk rows"
Pipe->>DB : "Update document status"
Pipe->>HR : "Update BM25 index"
ISvc->>DB : "Set job to completed, doc to indexed"
ISvc-->>API : "Done"
```

Key transformations and validations:
- File loading and chunking with configurable size and overlap
- OCR fallback for scanned PDFs with confidence scoring
- Batch embedding via Ollama with controlled timeouts
- Payload persistence to Qdrant and document chunk records to PostgreSQL
- Status transitions and BM25 index updates

**Diagram sources**
- [ingestion_service.py:21-88](file://safe4ai-pilot/app/services/ingestion_service.py#L21-L88)
- [rag_pipeline.py:62-150](file://safe4ai-pilot/app/services/rag_pipeline.py#L62-L150)
- [hybrid_retriever.py:30-42](file://safe4ai-pilot/app/components/hybrid_retriever.py#L30-L42)

**Section sources**
- [architecture.md:36-44](file://safe4ai-pilot/docs/architecture.md#L36-L44)
- [ingestion_service.py:21-88](file://safe4ai-pilot/app/services/ingestion_service.py#L21-L88)
- [rag_pipeline.py:62-150](file://safe4ai-pilot/app/services/rag_pipeline.py#L62-L150)
- [upload_validator.py:24-73](file://safe4ai-pilot/app/security/upload_validator.py#L24-L73)

### Query Processing Flow: From Input to Response
The query pipeline enforces security, optionally uses semantic cache, retrieves and reranks chunks, and generates a response.

```mermaid
sequenceDiagram
participant Client as "Client"
participant API as "FastAPI app"
participant IR as "InputGuard"
participant SC as "SemanticCache"
participant QR as "Query Router"
participant RP as "RAG Pipeline"
participant HR as "HybridRetriever"
participant QD as "Qdrant"
participant PG as "PostgreSQL"
participant OLA as "Ollama"
Client->>API : "POST /chat or /chat/stream"
API->>IR : "check(query)"
IR-->>API : "GuardResult"
alt Allowed
API->>SC : "lookup(query)"
SC-->>API : "Cached response or miss"
opt Cache hit
API-->>Client : "Answer + Citations"
end
opt Cache miss
API->>QR : "select collection"
API->>RP : "query(query, collection)"
RP->>HR : "retrieve(query, filters)"
HR->>QD : "ANN search"
HR->>PG : "BM25 index"
RP->>RP : "rerank top-k"
RP->>OLA : "generate(prompt)"
RP-->>API : "answer + citations"
API->>SC : "store(query, answer, citations, ...)"
API-->>Client : "Answer + Citations"
end
else Blocked
API-->>Client : "400/422"
end
```

Security and routing:
- InputGuard validates length and injection patterns
- Query Router selects the target Qdrant collection
- SemanticCache reduces latency for similar queries
- HybridRetriever fuses dense and sparse signals
- RAG pipeline composes context and invokes Ollama for generation

**Diagram sources**
- [chat_routes.py:115-148](file://safe4ai-pilot/app/api/chat_routes.py#L115-L148)
- [input_guard.py:24-49](file://safe4ai-pilot/app/security/input_guard.py#L24-L49)
- [semantic_cache.py:41-70](file://safe4ai-pilot/app/services/semantic_cache.py#L41-L70)
- [architecture.md:13-18](file://safe4ai-pilot/docs/architecture.md#L13-L18)
- [rag_pipeline.py:151-182](file://safe4ai-pilot/app/services/rag_pipeline.py#L151-L182)
- [hybrid_retriever.py:57-145](file://safe4ai-pilot/app/components/hybrid_retriever.py#L57-L145)

**Section sources**
- [chat_routes.py:115-251](file://safe4ai-pilot/app/api/chat_routes.py#L115-L251)
- [input_guard.py:24-49](file://safe4ai-pilot/app/security/input_guard.py#L24-L49)
- [semantic_cache.py:14-104](file://safe4ai-pilot/app/services/semantic_cache.py#L14-L104)
- [architecture.md:13-28](file://safe4ai-pilot/docs/architecture.md#L13-L28)

### Hybrid Retrieval: Dense ANN + Sparse BM25 Fusion
HybridRetriever computes dense embeddings and dense ANN search, augments with BM25 sparse ranking, and merges results via Reciprocal Rank Fusion.

```mermaid
flowchart TD
Start(["Query received"]) --> Embed["Compute query embedding via Ollama"]
Embed --> Dense["Qdrant ANN search<br/>limit K"]
Dense --> Sparse["BM25 scoring<br/>filtered by doc_id if provided"]
Sparse --> Fuse["RRF merge<br/>scores = sum(1/(k+r))"]
Fuse --> TopN["Select top results"]
TopN --> Return(["Return RetrievedChunks"])
```

- Dense: Qdrant ANN with optional filters on document IDs
- Sparse: BM25 built from chunk contents maintained in-memory
- Fusion: Reciprocal Rank Fusion to combine heterogeneous signals

**Diagram sources**
- [hybrid_retriever.py:57-145](file://safe4ai-pilot/app/components/hybrid_retriever.py#L57-L145)

**Section sources**
- [hybrid_retriever.py:14-145](file://safe4ai-pilot/app/components/hybrid_retriever.py#L14-L145)
- [architecture.md:3-11](file://safe4ai-pilot/docs/architecture.md#L3-L11)

### Semantic Caching Mechanism
SemanticCache stores query embeddings and responses to accelerate repeated queries above a similarity threshold.

```mermaid
flowchart TD
QStart(["Incoming query"]) --> E["Embed query via Ollama"]
E --> SQL["pgvector similarity search<br/>threshold check"]
SQL --> Hit{"Hit found?"}
Hit --> |Yes| Inc["Increment hit_count"]
Inc --> Return(["Return cached response + citations"])
Hit --> |No| Gen["Generate answer via RAG pipeline"]
Gen --> Store["Persist embedding + response + citations"]
Store --> Return
```

- Uses PostgreSQL pgvector with cosine-like distance operator
- Threshold configured via settings
- Maintains hit counts and supports invalidation by document ID

**Diagram sources**
- [semantic_cache.py:41-93](file://safe4ai-pilot/app/services/semantic_cache.py#L41-L93)
- [config.py](file://safe4ai-pilot/app/config.py#L18)

**Section sources**
- [semantic_cache.py:14-104](file://safe4ai-pilot/app/services/semantic_cache.py#L14-L104)
- [config.py](file://safe4ai-pilot/app/config.py#L18)

### Data Validation Rules and Transformation Logic
- Upload validation ensures allowed extensions, declared and magic MIME types, and size limits; generates safe filenames
- InputGuard strips HTML/control characters, enforces length, and blocks injection patterns
- RAG pipeline normalizes text, chunks with overlap, applies OCR quality gating for low-text pages, and batches embeddings
- HybridRetriever maintains BM25 index from chunk contents and payloads

**Section sources**
- [upload_validator.py:24-73](file://safe4ai-pilot/app/security/upload_validator.py#L24-L73)
- [input_guard.py:24-49](file://safe4ai-pilot/app/security/input_guard.py#L24-L49)
- [rag_pipeline.py:62-150](file://safe4ai-pilot/app/services/rag_pipeline.py#L62-L150)
- [hybrid_retriever.py:30-42](file://safe4ai-pilot/app/components/hybrid_retriever.py#L30-L42)

### Error Handling Throughout Pipelines
- IngestionService wraps pipeline execution in a dedicated DB session, sets failure states, and logs errors
- Chat routes handle missing graph state, invocation failures, and stream exceptions; return structured error events
- Health endpoint validates connectivity to PostgreSQL, Qdrant, and Ollama

**Section sources**
- [ingestion_service.py:72-87](file://safe4ai-pilot/app/services/ingestion_service.py#L72-L87)
- [chat_routes.py:126-148](file://safe4ai-pilot/app/api/chat_routes.py#L126-L148)
- [main.py:118-147](file://safe4ai-pilot/app/main.py#L118-L147)

### Data Consistency Guarantees and Transaction Boundaries
- IngestionService opens a fresh SQLAlchemy session per job, commits status updates, and persists chunks atomically
- SemanticCache uses single-row updates and commits after incrementing hit counts
- Audit logs and conversation state are persisted separately; audit retention governed by settings
- HybridRetriever rebuilds BM25 index in-memory from provided chunk IDs and contents

**Section sources**
- [ingestion_service.py:33-87](file://safe4ai-pilot/app/services/ingestion_service.py#L33-L87)
- [semantic_cache.py:59-64](file://safe4ai-pilot/app/services/semantic_cache.py#L59-L64)
- [config.py:16-17](file://safe4ai-pilot/app/config.py#L16-L17)
- [hybrid_retriever.py:30-42](file://safe4ai-pilot/app/components/hybrid_retriever.py#L30-L42)

### Audit Trail Maintenance
- Audit log captures user actions, timestamps, query text, response metadata, latency, model used, and trace IDs
- Retention governed by settings; cleanup scheduled at application startup

**Section sources**
- [models.py:118-131](file://safe4ai-pilot/app/db/models.py#L118-L131)
- [config.py](file://safe4ai-pilot/app/config.py#L16)
- [main.py](file://safe4ai-pilot/app/main.py#L21)

### Data Stores and Their Use Cases
- Qdrant: Dense ANN search for document retrieval; stores vector payloads with metadata
- pgvector: Semantic cache and audit/session tables; leverages vector similarity operator
- PostgreSQL: Core domain entities (documents, chunks, users, sessions, audit logs, ingestion jobs)

**Section sources**
- [architecture.md:3-11](file://safe4ai-pilot/docs/architecture.md#L3-L11)
- [models.py:75-116](file://safe4ai-pilot/app/db/models.py#L75-L116)

## Dependency Analysis
High-level dependencies among major components:

```mermaid
graph LR
Config["config.py"]
Main["main.py"]
Chat["chat_routes.py"]
Guard["input_guard.py"]
Upload["upload_validator.py"]
Ingest["ingestion_service.py"]
RAG["rag_pipeline.py"]
Hybrid["hybrid_retriever.py"]
Cache["semantic_cache.py"]
Models["db/models.py"]
Config --> Main
Main --> Chat
Chat --> Guard
Chat --> Cache
Chat --> RAG
RAG --> Hybrid
RAG --> Models
Hybrid --> Models
Cache --> Models
Ingest --> RAG
Ingest --> Models
Upload --> Ingest
```

**Diagram sources**
- [config.py:7-48](file://safe4ai-pilot/app/config.py#L7-L48)
- [main.py:14-56](file://safe4ai-pilot/app/main.py#L14-L56)
- [chat_routes.py:115-148](file://safe4ai-pilot/app/api/chat_routes.py#L115-L148)
- [input_guard.py:24-49](file://safe4ai-pilot/app/security/input_guard.py#L24-L49)
- [upload_validator.py:24-73](file://safe4ai-pilot/app/security/upload_validator.py#L24-L73)
- [ingestion_service.py:21-88](file://safe4ai-pilot/app/services/ingestion_service.py#L21-L88)
- [rag_pipeline.py:34-56](file://safe4ai-pilot/app/services/rag_pipeline.py#L34-L56)
- [hybrid_retriever.py:14-29](file://safe4ai-pilot/app/components/hybrid_retriever.py#L14-L29)
- [semantic_cache.py:14-26](file://safe4ai-pilot/app/services/semantic_cache.py#L14-L26)
- [models.py:75-116](file://safe4ai-pilot/app/db/models.py#L75-L116)

**Section sources**
- [main.py:14-56](file://safe4ai-pilot/app/main.py#L14-L56)
- [chat_routes.py:115-148](file://safe4ai-pilot/app/api/chat_routes.py#L115-L148)
- [ingestion_service.py:21-88](file://safe4ai-pilot/app/services/ingestion_service.py#L21-L88)
- [rag_pipeline.py:34-56](file://safe4ai-pilot/app/services/rag_pipeline.py#L34-L56)
- [hybrid_retriever.py:14-29](file://safe4ai-pilot/app/components/hybrid_retriever.py#L14-L29)
- [semantic_cache.py:14-26](file://safe4ai-pilot/app/services/semantic_cache.py#L14-L26)
- [models.py:75-116](file://safe4ai-pilot/app/db/models.py#L75-L116)

## Performance Considerations
- Batch embeddings: RAG pipeline emits embeddings in batches to reduce overhead
- Pre-warming: Ollama model is prewarmed to avoid cold-start latency
- Hybrid fusion: Combines strengths of dense and sparse retrieval to improve recall and precision
- Semantic cache: Reduces latency for repeated queries above a similarity threshold
- BM25 index: Maintained in-memory for fast sparse retrieval during ingestion

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and diagnostics:
- Health checks fail: Verify PostgreSQL, Qdrant, and Ollama endpoints
- Model not ready: Confirm Ollama model availability and prewarm completion
- Ingestion stuck: Startup recovery resets jobs older than a threshold back to pending
- Upload blocked: Check allowed extensions, MIME types, and size limits
- Query blocked: InputGuard may reject overly long or suspicious queries

**Section sources**
- [main.py:118-147](file://safe4ai-pilot/app/main.py#L118-L147)
- [main.py:104-116](file://safe4ai-pilot/app/main.py#L104-L116)
- [ingestion_service.py:90-113](file://safe4ai-pilot/app/services/ingestion_service.py#L90-L113)
- [upload_validator.py:24-73](file://safe4ai-pilot/app/security/upload_validator.py#L24-L73)
- [input_guard.py:24-49](file://safe4ai-pilot/app/security/input_guard.py#L24-L49)

## Conclusion
The Private AI system implements a robust data flow architecture:
- Ingestion converts diverse document formats into dense vectors and chunk records, with OCR quality gating and BM25 index updates
- Query processing integrates security validation, optional semantic caching, hybrid retrieval, and LLM generation
- Dual vector stores enable scalable retrieval and efficient caching
- Strong separation of concerns, explicit validation, and audit logging support reliability and compliance

[No sources needed since this section summarizes without analyzing specific files]

## Appendices

### Data Models Overview
```mermaid
erDiagram
USERS {
string id PK
string email UK
string password_hash
enum role
bool is_active
int failed_login_count
timestamptz locked_until
}
SESSIONS {
string id PK
string user_id FK
json state_json
timestamptz created_at
timestamptz updated_at
}
DOCUMENTS {
string id PK
string filename
string storage_filename
string file_type
enum ingestion_status
string uploaded_by FK
timestamptz uploaded_at
json doc_metadata
timestamptz ingestion_started_at
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
timestamptz created_at
int hit_count
}
AUDIT_LOGS {
string id PK
string user_id FK
string session_id
timestamptz timestamp
string action_type
string query_text
json response_metadata
int latency_ms
string model_used
string trace_id
}
INGESTION_JOBS {
string id PK
string document_id FK
enum status
timestamptz created_at
timestamptz completed_at
text error
}
USERS ||--o{ SESSIONS : "has"
USERS ||--o{ DOCUMENTS : "uploaded"
DOCUMENTS ||--o{ DOCUMENT_CHUNKS : "chunks"
DOCUMENTS ||--o{ INGESTION_JOBS : "jobs"
```

**Diagram sources**
- [models.py:52-182](file://safe4ai-pilot/app/db/models.py#L52-L182)