# Content Filtering

<cite>
**Referenced Files in This Document**
- [content_filter.py](file://safe4ai-pilot/app/security/content_filter.py)
- [input_guard.py](file://safe4ai-pilot/app/security/input_guard.py)
- [output_filter.py](file://safe4ai-pilot/app/security/output_filter.py)
- [upload_validator.py](file://safe4ai-pilot/app/security/upload_validator.py)
- [graph.py](file://safe4ai-pilot/app/agents/graph.py)
- [models.py](file://safe4ai-pilot/app/models.py)
- [chat_routes.py](file://safe4ai-pilot/app/api/chat_routes.py)
- [config.py](file://safe4ai-pilot/app/config.py)
- [AdminAudit.tsx](file://safe4ai-pilot/design/components/AdminAudit.tsx)
- [test_security_guards.py](file://safe4ai-pilot/tests/test_security_guards.py)
- [rag_pipeline.py](file://safe4ai-pilot/app/services/rag_pipeline.py)
</cite>

## Update Summary
**Changes Made**
- Added documentation for the new `redact()` method in ContentFilter that replaces PII patterns with '[REDACTED]' instead of filtering out entire document chunks
- Updated ContentFilter section to explain the dual approach of filtering and redaction for privacy compliance
- Added integration examples showing how redact() is used in the RAG pipeline for document ingestion
- Enhanced troubleshooting guide with redaction-specific scenarios
- Updated architecture diagrams to reflect the new redaction capability

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
This document describes the content filtering system used to monitor and block inappropriate or sensitive content across ingestion, retrieval, generation, and output stages. It explains filtering criteria, keyword detection, and contextual analysis approaches, and documents how the system integrates with AI response generation to intercept and modify content before delivery. The system now includes advanced redaction capabilities that replace PII patterns with '[REDACTED]' instead of filtering out entire document chunks, addressing critical data loss issues while maintaining privacy compliance.

## Project Structure
The content filtering system spans several modules:
- Security guards: input validation, output verification, content filtering for retrieved chunks, and upload validation.
- Pipeline orchestration: LangGraph nodes that invoke guards during chat processing.
- Data models: shared types used across guards and pipeline nodes.
- API endpoints: chat endpoints that trigger the pipeline and stream results.
- Configuration: global settings such as retention and upload limits.
- Frontend admin: audit visualization indicating retention policies.
- Redaction service: automatic PII replacement during document ingestion.

```mermaid
graph TB
subgraph "Security Guards"
IG["InputGuard<br/>input_guard.py"]
OF["OutputFilter<br/>output_filter.py"]
CF["ContentFilter<br/>content_filter.py"]
UV["UploadValidator<br/>upload_validator.py"]
end
subgraph "Pipeline"
G["LangGraph build_graph<br/>graph.py"]
ST["PrivateAIState<br/>models.py"]
RP["RAG Pipeline<br/>rag_pipeline.py"]
end
subgraph "API"
CR["POST /chat<br/>chat_routes.py"]
CSR["POST /chat/stream<br/>chat_routes.py"]
end
subgraph "Config & Audit"
CFG["Settings<br/>config.py"]
AUD["AdminAudit UI<br/>AdminAudit.tsx"]
end
CR --> G
CSR --> G
G --> IG
G --> CF
G --> OF
G --> ST
CFG --> UV
CFG --> CF
AUD --> CFG
RP --> CF
```

**Diagram sources**
- [graph.py:43-352](file://safe4ai-pilot/app/agents/graph.py#L43-L352)
- [input_guard.py:24-49](file://safe4ai-pilot/app/security/input_guard.py#L24-L49)
- [output_filter.py:31-61](file://safe4ai-pilot/app/security/output_filter.py#L31-L61)
- [content_filter.py:25-73](file://safe4ai-pilot/app/security/content_filter.py#L25-L73)
- [upload_validator.py:24-73](file://safe4ai-pilot/app/security/upload_validator.py#L24-L73)
- [models.py:38-95](file://safe4ai-pilot/app/models.py#L38-L95)
- [chat_routes.py:115-251](file://safe4ai-pilot/app/api/chat_routes.py#L115-L251)
- [config.py:7-48](file://safe4ai-pilot/app/config.py#L7-L48)
- [AdminAudit.tsx:1-115](file://safe4ai-pilot/design/components/AdminAudit.tsx#L1-L115)
- [rag_pipeline.py:130-150](file://safe4ai-pilot/app/services/rag_pipeline.py#L130-L150)

**Section sources**
- [graph.py:43-352](file://safe4ai-pilot/app/agents/graph.py#L43-L352)
- [models.py:38-95](file://safe4ai-pilot/app/models.py#L38-L95)
- [chat_routes.py:115-251](file://safe4ai-pilot/app/api/chat_routes.py#L115-L251)
- [config.py:7-48](file://safe4ai-pilot/app/config.py#L7-L48)
- [AdminAudit.tsx:1-115](file://safe4ai-pilot/design/components/AdminAudit.tsx#L1-L115)

## Core Components
- InputGuard: Validates and sanitizes user queries before they enter the retrieval phase. It strips HTML and control characters, enforces a maximum length, and detects prompt-injection patterns.
- ContentFilter: Provides dual protection through PII detection and filtering, plus redaction capabilities. It can either remove chunks containing PII or replace PII patterns with '[REDACTED]' to preserve document context while maintaining privacy compliance.
- OutputFilter: Verifies generated answers for PII hallucinations (PII present in the answer but not in the source chunks) and suspiciously long outputs.
- UploadValidator: Enforces allowed file extensions, declared and detected MIME types, and file size limits to prevent risky uploads.

These components integrate with the LangGraph pipeline and RAG ingestion process to enforce safety at each stage while minimizing data loss through intelligent redaction.

**Section sources**
- [input_guard.py:24-49](file://safe4ai-pilot/app/security/input_guard.py#L24-L49)
- [content_filter.py:25-73](file://safe4ai-pilot/app/security/content_filter.py#L25-L73)
- [output_filter.py:31-61](file://safe4ai-pilot/app/security/output_filter.py#L31-L61)
- [upload_validator.py:24-73](file://safe4ai-pilot/app/security/upload_validator.py#L24-L73)

## Architecture Overview
The chat pipeline invokes guards at strategic points to ensure content safety:
- Intake: InputGuard checks the incoming query.
- Retrieve: ContentFilter removes PII-containing chunks from the ranked results.
- Generate: Produces an answer grounded in filtered, relevant chunks.
- Output Filter: Blocks answers with hallucinated PII or warns on excessive length.
- Quality Gate: Routes to respond or fallback based on grounding and policy decisions.

The RAG pipeline includes automatic redaction during document ingestion to prevent PII exposure while preserving document context.

```mermaid
sequenceDiagram
participant Client as "Client"
participant API as "chat_routes.py"
participant Graph as "graph.py"
participant Guard as "InputGuard"
participant CF as "ContentFilter"
participant Gen as "Generate Node"
participant OF as "OutputFilter"
Client->>API : "POST /chat" or "/chat/stream"
API->>Graph : "invoke/astream with PrivateAIState"
Graph->>Guard : "check(query)"
alt "allowed"
Graph->>Graph : "rewrite/retrieve/grade"
Graph->>CF : "filter_chunks(ranked)"
Graph->>Gen : "generate(answer, citations)"
Graph->>OF : "check(answer, generation_context)"
alt "blocked"
Graph->>Graph : "fallback with NO_ANSWER"
else "allowed"
Graph->>Graph : "quality_gate → respond/fallback"
end
else "rejected"
Graph->>Graph : "fallback with error"
end
Graph-->>API : "final PrivateAIState"
API-->>Client : "answer/citations or SSE tokens"
```

**Diagram sources**
- [chat_routes.py:115-251](file://safe4ai-pilot/app/api/chat_routes.py#L115-L251)
- [graph.py:56-352](file://safe4ai-pilot/app/agents/graph.py#L56-L352)
- [input_guard.py:27-49](file://safe4ai-pilot/app/security/input_guard.py#L27-L49)
- [content_filter.py:29-73](file://safe4ai-pilot/app/security/content_filter.py#L29-L73)
- [output_filter.py:32-61](file://safe4ai-pilot/app/security/output_filter.py#L32-L61)

## Detailed Component Analysis

### InputGuard
- Purpose: Prevent prompt injection and excessive input length.
- Mechanism:
  - Strips HTML tags and non-printable characters.
  - Enforces a maximum character count.
  - Detects injection patterns (e.g., instructions to ignore prior constraints, system prompt mentions, special tokens).
- Decision: Returns a guard result indicating allowed or blocked with a reason.

```mermaid
flowchart TD
Start(["InputGuard.check(query)"]) --> Clean["Strip HTML and control chars"]
Clean --> LenCheck{"Length ≤ limit?"}
LenCheck --> |No| BlockLen["Return blocked: too long"]
LenCheck --> |Yes| InjectCheck["Scan for injection patterns"]
InjectCheck --> Found{"Pattern found?"}
Found --> |Yes| BlockInject["Return blocked: injection"]
Found --> |No| Allow["Return allowed"]
```

**Diagram sources**
- [input_guard.py:27-49](file://safe4ai-pilot/app/security/input_guard.py#L27-L49)

**Section sources**
- [input_guard.py:24-49](file://safe4ai-pilot/app/security/input_guard.py#L24-L49)

### ContentFilter
- Purpose: Provide comprehensive PII protection through both filtering and redaction capabilities.
- Mechanism:
  - PII detection via compiled regular expressions for SSNs, credit cards, and passports.
  - **Filtering mode**: Removes chunks containing PII, logging each exclusion for auditability.
  - **Redaction mode**: Replaces PII patterns with '[REDACTED]' while preserving surrounding content context.
  - Optional blocked terms list (case-insensitive substring matching).
  - Comprehensive logging for both filtering and redaction actions.
- Decision: Returns filtered chunks or redacted text depending on the method used.

**Updated** Added redact() method that replaces PII patterns with '[REDACTED]' instead of filtering out entire document chunks, addressing critical data loss issues while maintaining privacy compliance.

```mermaid
flowchart TD
Start(["filter_chunks(chunks)"]) --> Loop["For each chunk"]
Loop --> PII{"Contains PII?"}
PII --> |Yes| LogPII["Log exclusion: pii_chunk_excluded"]
LogPII --> Next["Next chunk"]
PII --> |No| Keep["Keep chunk"]
Keep --> Next
Next --> Done(["Return clean list"])
Start2(["redact(text)"]) --> RedactLoop["For each PII pattern"]
RedactLoop --> Replace["Replace with [REDACTED]"]
Replace --> NextPattern["Next pattern"]
NextPattern --> Done2(["Return redacted text"])
Start3(["filter_blocked_sections(chunks)"]) --> CheckTerms{"Blocked terms configured?"}
CheckTerms --> |No| ReturnAll["Return original chunks"]
CheckTerms --> |Yes| Loop2["For each chunk"]
Loop2 --> Lower["Lowercase content"]
Lower --> Match["Any blocked term contained?"]
Match --> |Yes| LogTerm["Log exclusion: blocked_term_chunk_excluded"]
LogTerm --> Next2["Next chunk"]
Match --> |No| Keep2["Keep chunk"]
Keep2 --> Next2
Next2 --> Done2(["Return clean list"])
```

**Diagram sources**
- [content_filter.py:29-73](file://safe4ai-pilot/app/security/content_filter.py#L29-L73)

**Section sources**
- [content_filter.py:25-73](file://safe4ai-pilot/app/security/content_filter.py#L25-L73)

### OutputFilter
- Purpose: Verify generated answers before delivery.
- Mechanism:
  - Detects PII in the answer using the same patterns as ContentFilter.
  - Blocks answers containing PII not present in the source chunks (hallucination detection).
  - Warns on answers exceeding a configured length threshold.
- Decision: Returns a guard result indicating allowed or blocked with a reason.

```mermaid
flowchart TD
Start(["OutputFilter.check(answer, source_chunks)"]) --> FindPII["Find PII matches in answer"]
FindPII --> HasPII{"Any PII?"}
HasPII --> |No| LongCheck["Check length vs threshold"]
HasPII --> |Yes| Combine["Combine source chunk texts"]
Combine --> Absent{"All PII absent from sources?"}
Absent --> |Yes| BlockPII["Return blocked: hallucinated PII"]
Absent --> |No| LongCheck
LongCheck --> Long{"Answer > threshold?"}
Long --> |Yes| Warn["Log warning: suspiciously long"]
Long --> |No| Allow["Return allowed"]
Warn --> Allow
```

**Diagram sources**
- [output_filter.py:32-61](file://safe4ai-pilot/app/security/output_filter.py#L32-L61)

**Section sources**
- [output_filter.py:31-61](file://safe4ai-pilot/app/security/output_filter.py#L31-L61)

### UploadValidator
- Purpose: Enforce safe file ingestion at upload time.
- Mechanism:
  - Allowed extensions and MIME types lists.
  - Declared Content-Type validation.
  - Magic-byte detection for actual MIME type.
  - Size enforcement based on settings.
- Decision: Returns a guard result indicating allowed or blocked with a reason.

```mermaid
flowchart TD
Start(["validate(filename, content_type, bytes)"]) --> Ext["Check extension in allowed list"]
Ext --> |Not allowed| BlockExt["Return blocked: extension"]
Ext --> |Allowed| CType["Check declared Content-Type"]
CType --> |Not allowed| BlockCType["Return blocked: Content-Type"]
CType --> |Allowed| Magic["Detect MIME via magic bytes"]
Magic --> |Not allowed| BlockMagic["Return blocked: detected MIME"]
Magic --> |Allowed| Size["Check size ≤ max"]
Size --> |Too big| BlockSize["Return blocked: size"]
Size --> |OK| Allow["Return allowed"]
```

**Diagram sources**
- [upload_validator.py:25-73](file://safe4ai-pilot/app/security/upload_validator.py#L25-L73)

**Section sources**
- [upload_validator.py:24-73](file://safe4ai-pilot/app/security/upload_validator.py#L24-L73)

### RAG Pipeline Integration
- Purpose: Automatically redact PII during document ingestion to prevent privacy violations.
- Mechanism:
  - During document processing, ContentFilter.is_pii() checks if chunks contain PII.
  - If PII is detected, ContentFilter.redact() replaces patterns with '[REDACTED]'.
  - Redaction events are logged for audit trail.
  - Processed chunks are embedded and stored with redacted content.
- Decision: Preserves document context while eliminating privacy risks.

**New** Added automatic redaction during document ingestion to address data loss issues while maintaining privacy compliance.

```mermaid
flowchart TD
Start(["Document Ingestion"]) --> Extract["Extract Text Chunks"]
Extract --> CheckPII{"PII Detected?"}
CheckPII --> |Yes| Redact["Apply ContentFilter.redact()"]
Redact --> LogPII["Log pii_redacted_in_chunk"]
LogPII --> Embed["Generate Embeddings"]
CheckPII --> |No| Embed
Embed --> Store["Store in Vector Database"]
Store --> Index["Update BM25 Index"]
Index --> Complete(["Ingestion Complete"])
```

**Diagram sources**
- [rag_pipeline.py:130-150](file://safe4ai-pilot/app/services/rag_pipeline.py#L130-L150)
- [content_filter.py:66-68](file://safe4ai-pilot/app/security/content_filter.py#L66-L68)

**Section sources**
- [rag_pipeline.py:130-150](file://safe4ai-pilot/app/services/rag_pipeline.py#L130-L150)
- [content_filter.py:66-68](file://safe4ai-pilot/app/security/content_filter.py#L66-L68)

### Integration with AI Response Generation
- The pipeline builds guards and invokes them at each node:
  - intake_node calls InputGuard.
  - retrieve_node applies ContentFilter to ranked chunks.
  - generate_node produces the answer and citations.
  - output_filter_node calls OutputFilter and may route to fallback.
- The generation_context snapshot ensures the output filter validates against the exact chunks supplied to generation, preventing dynamic changes from bypassing checks.
- RAG pipeline automatically redacts PII during document ingestion using ContentFilter.redact().

**Updated** Added RAG pipeline integration showing automatic redaction during document processing.

```mermaid
classDiagram
class PrivateAIState {
+string session_id
+string user_id
+Message[] messages
+string current_step
+string status
+string rewritten_query
+RankedChunk[] retrieved_chunks
+GradedChunk[] graded_chunks
+string draft_answer
+Citation[] citations
+bool grounded
+string trace_id
+float cost_usd
+string[] errors
+bool requires_human_review
+int retrieval_attempts
+GradedChunk[] generation_context
}
class ContentFilter {
+filter_chunks(chunks) RankedChunk[]
+filter_blocked_sections(chunks) RankedChunk[]
+redact(text) str
+is_pii(text) bool
}
class InputGuard {
+check(query) GuardResult
}
class OutputFilter {
+check(answer, source_chunks) GuardResult
}
class GuardResult {
+bool allowed
+string reason
}
PrivateAIState --> InputGuard : "validated by"
PrivateAIState --> ContentFilter : "filters chunks"
PrivateAIState --> OutputFilter : "validates answer"
GuardResult <.. InputGuard
GuardResult <.. OutputFilter
```

**Diagram sources**
- [models.py:38-95](file://safe4ai-pilot/app/models.py#L38-L95)
- [input_guard.py:27-49](file://safe4ai-pilot/app/security/input_guard.py#L27-L49)
- [content_filter.py:29-73](file://safe4ai-pilot/app/security/content_filter.py#L29-L73)
- [output_filter.py:32-61](file://safe4ai-pilot/app/security/output_filter.py#L32-L61)

**Section sources**
- [graph.py:56-352](file://safe4ai-pilot/app/agents/graph.py#L56-L352)
- [models.py:38-95](file://safe4ai-pilot/app/models.py#L38-L95)

## Dependency Analysis
- Guards depend on:
  - Regular expressions for pattern matching.
  - Structlog for logging.
  - Pydantic models for typed results and state.
- Pipeline depends on guards and orchestrates their invocation.
- RAG pipeline integrates ContentFilter for automatic document redaction.
- Configuration influences upload size limits, retention, and redaction preferences.
- Audit UI reflects retention policies and redaction settings.

**Updated** Added RAG pipeline integration and configuration dependencies.

```mermaid
graph LR
CFG["config.py: Settings"] --> UV["upload_validator.py: UploadValidator"]
CFG --> CF["content_filter.py: ContentFilter"]
IG["input_guard.py: InputGuard"] --> G["graph.py: intake_node"]
CF --> G
OF["output_filter.py: OutputFilter"] --> G
CF --> RP["rag_pipeline.py: Document Redaction"]
ST["models.py: GuardResult/PrivateAIState"] --> IG
ST --> CF
ST --> OF
G --> CR["chat_routes.py: POST /chat"]
G --> CSR["chat_routes.py: POST /chat/stream"]
AUD["AdminAudit.tsx: retention UI"] --> CFG
```

**Diagram sources**
- [config.py:7-48](file://safe4ai-pilot/app/config.py#L7-L48)
- [upload_validator.py:24-73](file://safe4ai-pilot/app/security/upload_validator.py#L24-L73)
- [input_guard.py:24-49](file://safe4ai-pilot/app/security/input_guard.py#L24-L49)
- [content_filter.py:25-73](file://safe4ai-pilot/app/security/content_filter.py#L25-L73)
- [output_filter.py:31-61](file://safe4ai-pilot/app/security/output_filter.py#L31-L61)
- [models.py:38-95](file://safe4ai-pilot/app/models.py#L38-L95)
- [chat_routes.py:115-251](file://safe4ai-pilot/app/api/chat_routes.py#L115-L251)
- [AdminAudit.tsx:1-115](file://safe4ai-pilot/design/components/AdminAudit.tsx#L1-L115)
- [rag_pipeline.py:130-150](file://safe4ai-pilot/app/services/rag_pipeline.py#L130-L150)

**Section sources**
- [config.py:7-48](file://safe4ai-pilot/app/config.py#L7-L48)
- [models.py:38-95](file://safe4ai-pilot/app/models.py#L38-L95)
- [chat_routes.py:115-251](file://safe4ai-pilot/app/api/chat_routes.py#L115-L251)
- [AdminAudit.tsx:1-115](file://safe4ai-pilot/design/components/AdminAudit.tsx#L1-L115)

## Performance Considerations
- Regex scanning scales linearly with text length; keep patterns minimal and specific.
- PII detection in output filtering scans the answer and concatenates source texts; avoid extremely large contexts to reduce overhead.
- GuardResult short-circuits after the first violation, minimizing unnecessary work.
- Streaming responses mitigate latency while maintaining safety checks at the end of the pipeline.
- **Redaction performance**: The redact() method processes text once per PII pattern, making it efficient for typical document sizes.
- **Memory considerations**: Redaction preserves original text structure, avoiding the memory overhead of filtering entire chunks.

**Updated** Added performance considerations for the new redact() method.

## Troubleshooting Guide
Common issues and resolutions:
- Queries rejected at intake:
  - Cause: Exceeds maximum length or contains injection patterns.
  - Resolution: Shorten the query or rephrase to avoid directive-like phrasing.
- Retrieval yields no relevant chunks:
  - Cause: All chunks filtered due to PII or blocked terms.
  - Resolution: Adjust blocked terms or reprocess documents; verify ContentFilter configuration.
- Generated answer blocked:
  - Cause: Hallucinated PII not present in source chunks.
  - Resolution: Improve retrieval grounding or adjust prompts to avoid generating unsupported claims.
- Upload rejected:
  - Cause: Disallowed extension/type or size exceeded.
  - Resolution: Use allowed formats and sizes; verify declared Content-Type and file integrity.
- **Redaction not working**:
  - Cause: PII patterns not matching expected formats.
  - Resolution: Verify ContentFilter patterns and ensure documents are processed through the RAG pipeline.
- **Data loss concerns**:
  - Cause: Previous filtering approach removed entire chunks.
  - Resolution: Use ContentFilter.redact() instead of filter_chunks() to preserve document context.

**Updated** Added troubleshooting guidance for redaction-specific issues.

**Section sources**
- [input_guard.py:27-49](file://safe4ai-pilot/app/security/input_guard.py#L27-L49)
- [content_filter.py:32-41](file://safe4ai-pilot/app/security/content_filter.py#L32-L41)
- [output_filter.py:42-50](file://safe4ai-pilot/app/security/output_filter.py#L42-L50)
- [upload_validator.py:39-68](file://safe4ai-pilot/app/security/upload_validator.py#L39-L68)
- [chat_routes.py:176-242](file://safe4ai-pilot/app/api/chat_routes.py#L176-L242)

## Conclusion
The content filtering system enforces safety across ingestion, retrieval, generation, and output stages using targeted guards. InputGuard prevents harmful prompts, ContentFilter provides dual protection through filtering and redaction, OutputFilter blocks hallucinated PII and warns on excessive length, and UploadValidator ensures safe ingestion. The new redact() method addresses critical data loss issues by replacing PII patterns with '[REDACTED]' instead of removing entire document chunks, while the RAG pipeline automatically redacts PII during document ingestion. Together with structured logging and audit UI, the system supports compliance and operational visibility.

**Updated** Enhanced conclusion to reflect the new redaction capabilities and their benefits.

## Appendices

### Filter Configuration Examples
- Blocked terms:
  - Configure a list of terms to block in ContentFilter initialization. Tests demonstrate behavior when terms are present.
- Upload limits:
  - Adjust maximum upload size via settings; validators enforce declared and detected MIME types and file size.
- Retention:
  - Audit events are retained per configuration; admin UI indicates retention and archival policies.
- **Redaction settings**:
  - Enable automatic PII redaction during document ingestion through the redactPII setting in admin configuration.

**Updated** Added redaction settings configuration.

**Section sources**
- [test_security_guards.py:132-166](file://safe4ai-pilot/tests/test_security_guards.py#L132-L166)
- [config.py:16-20](file://safe4ai-pilot/app/config.py#L16-L20)
- [AdminAudit.tsx:110-113](file://safe4ai-pilot/design/components/AdminAudit.tsx#L110-L113)

### Redaction Implementation Details
- **Pattern matching**: Uses the same PII detection patterns as filtering (SSNs, credit cards, passports).
- **Replacement strategy**: Replaces detected patterns with '[REDACTED]' while preserving surrounding text context.
- **Logging**: Records redaction events with document and page information for audit trails.
- **Performance**: Processes text efficiently with minimal computational overhead.

**New** Added implementation details for the redact() method.

**Section sources**
- [content_filter.py:13-17](file://safe4ai-pilot/app/security/content_filter.py#L13-L17)
- [content_filter.py:24-27](file://safe4ai-pilot/app/security/content_filter.py#L24-L27)
- [rag_pipeline.py:140-143](file://safe4ai-pilot/app/services/rag_pipeline.py#L140-L143)