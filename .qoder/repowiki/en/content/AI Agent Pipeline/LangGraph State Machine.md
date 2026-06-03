# LangGraph State Machine

<cite>
**Referenced Files in This Document**
- [graph.py](file://safe4ai-pilot/app/agents/graph.py)
- [models.py](file://safe4ai-pilot/app/models.py)
- [chat_routes.py](file://safe4ai-pilot/app/api/chat_routes.py)
- [adaptive_router.py](file://safe4ai-pilot/app/agents/adaptive_router.py)
- [document_grader.py](file://safe4ai-pilot/app/agents/document_grader.py)
- [query_decomposer.py](file://safe4ai-pilot/app/agents/query_decomposer.py)
- [hybrid_retriever.py](file://safe4ai-pilot/app/components/hybrid_retriever.py)
- [reranker.py](file://safe4ai-pilot/app/components/reranker.py)
- [input_guard.py](file://safe4ai-pilot/app/security/input_guard.py)
- [output_filter.py](file://safe4ai-pilot/app/security/output_filter.py)
- [tracer.py](file://safe4ai-pilot/observability/tracer.py)
- [agent_runner.py](file://safe4ai-pilot/app/services/agent_runner.py)
- [test_chat.py](file://safe4ai-pilot/tests/test_chat.py)
</cite>

## Update Summary
**Changes Made**
- Updated documentation to reflect enhanced type handling in the graph implementation
- Simplified GradedChunk→RankedChunk conversion logic explanation in output filtering
- Improved sequence handling documentation for output filtering operations
- Enhanced streaming state merging documentation with current implementation details
- Updated architecture diagrams to reflect current graph-based implementation

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Streaming Implementation](#streaming-implementation)
6. [Detailed Component Analysis](#detailed-component-analysis)
7. [Dependency Analysis](#dependency-analysis)
8. [Performance Considerations](#performance-considerations)
9. [Troubleshooting Guide](#troubleshooting-guide)
10. [Conclusion](#conclusion)
11. [Appendices](#appendices)

## Introduction
This document explains the LangGraph State Machine that powers the PrivateAI RAG pipeline. It focuses on the StateGraph architecture, the PrivateAIState model, and the end-to-end flow across pipeline nodes. The implementation now includes enhanced streaming capabilities with improved handling of partial state updates from streaming LangGraph nodes, better type safety through Pydantic models, and simplified chunk conversion logic. It also documents state transitions, conditional routing, observability via OpenTelemetry, error handling, and recovery strategies. Practical guidance is included for extending the state machine with new nodes, modifying state variables, and implementing custom routing logic.

## Project Structure
The state machine is implemented in a single module that composes nodes from dedicated components. The orchestration logic lives in the graph builder, while supporting services handle retrieval, reranking, grading, decomposition, guards, and tracing. The system now supports both blocking and streaming execution modes with enhanced type safety.

```mermaid
graph TB
subgraph "Agents"
G["graph.py<br/>StateGraph builder"]
AR["adaptive_router.py<br/>routing helpers"]
DG["document_grader.py<br/>chunk relevance"]
QD["query_decomposer.py<br/>sub-query generation"]
end
subgraph "Components"
HR["hybrid_retriever.py<br/>Qdrant+BM25 fusion"]
RR["reranker.py<br/>cross-encoder rerank"]
end
subgraph "Security"
IG["input_guard.py<br/>input validation"]
OF["output_filter.py<br/>PII and safety"]
end
subgraph "API Layer"
CR["chat_routes.py<br/>streaming and state management"]
end
subgraph "Observability"
TR["tracer.py<br/>OpenTelemetry tracer"]
AG_RUN["agent_runner.py<br/>pipeline span wrapper"]
end
subgraph "Models"
M["models.py<br/>PrivateAIState and types"]
end
G --> AR
G --> DG
G --> QD
G --> HR
G --> RR
G --> IG
G --> OF
G --> TR
CR --> G
CR --> M
AG_RUN --> G
AG_RUN --> M
G --> M
```

**Diagram sources**
- [graph.py:39-342](file://safe4ai-pilot/app/agents/graph.py#L39-L342)
- [adaptive_router.py:1-18](file://safe4ai-pilot/app/agents/adaptive_router.py#L1-L18)
- [document_grader.py:1-72](file://safe4ai-pilot/app/agents/document_grader.py#L1-L72)
- [query_decomposer.py:10-41](file://safe4ai-pilot/app/agents/query_decomposer.py#L10-L41)
- [hybrid_retriever.py:13-143](file://safe4ai-pilot/app/components/hybrid_retriever.py#L13-L143)
- [reranker.py:11-36](file://safe4ai-pilot/app/components/reranker.py#L11-L36)
- [input_guard.py:24-49](file://safe4ai-pilot/app/security/input_guard.py#L24-L49)
- [output_filter.py:26-74](file://safe4ai-pilot/app/security/output_filter.py#L26-L74)
- [chat_routes.py:224-361](file://safe4ai-pilot/app/api/chat_routes.py#L224-L361)
- [tracer.py:34-76](file://safe4ai-pilot/observability/tracer.py#L34-L76)
- [agent_runner.py:14-55](file://safe4ai-pilot/app/services/agent_runner.py#L14-L55)
- [models.py:49-113](file://safe4ai-pilot/app/models.py#L49-L113)

**Section sources**
- [graph.py:39-342](file://safe4ai-pilot/app/agents/graph.py#L39-L342)
- [models.py:49-113](file://safe4ai-pilot/app/models.py#L49-L113)
- [chat_routes.py:224-361](file://safe4ai-pilot/app/api/chat_routes.py#L224-L361)

## Core Components
- PrivateAIState: Central state container that tracks conversation context, retrieval metadata, grounding, citations, observability attributes, and human review flags. It defines the current execution step and status using Pydantic's Literal types for enhanced type safety. Now supports enhanced state merging for streaming operations.
- Node functions: Asynchronous functions representing each stage of the pipeline, returning updates to the state to drive transitions with improved type handling.
- Conditional routing: Uses LLM-based decisions with fallback rules to choose the next node, now with better type safety guarantees.
- Streaming support: Enhanced with `graph.astream()` for real-time state updates and partial state merging with improved sequence handling.
- Observability: Per-node spans inherit from a pipeline-level span; spans capture session identifiers, trace IDs, and node-specific attributes.

Key state variables and roles:
- Control flow: messages, current_step, status
- Retrieval: rewritten_query, retrieved_chunks (RankedChunk), graded_chunks (GradedChunk), retrieval_score_max, retrieval_attempts
- Decomposition: sub_queries
- Generation: draft_answer, citations, generation_context
- Quality and safety: grounded, requires_human_review, errors, trace_id, cost_usd
- Human review: requires_human_review flag triggers manual intervention

**Section sources**
- [models.py:49-113](file://safe4ai-pilot/app/models.py#L49-L113)
- [graph.py:51-342](file://safe4ai-pilot/app/agents/graph.py#L51-L342)

## Architecture Overview
The StateGraph orchestrates a self-correcting RAG pipeline with the following stages:
- Intake: Validates input and decides whether to rewrite or fall back.
- Rewrite: Rewrites the query using a prompt and model.
- Retrieve: Retrieves candidate chunks and reranks them.
- Grade: Grades chunks for relevance and decides between generate or decompose.
- Decompose: Generates sub-queries and re-runs retrieval/grading per sub-query.
- Generate: Builds a grounded answer from relevant chunks.
- Output Filter: Checks for PII hallucinations and suspicious length with simplified sequence handling.
- Quality Gate: Decides whether to respond, retrieve again (self-correction), or fall back.
- Respond/Fallback: Finalization nodes.

```mermaid
graph LR
A["Intake"] --> B["Rewrite"]
B --> C["Retrieve"]
C --> D["Grade"]
D --> E["Generate"]
D --> F["Decompose"]
F --> E
E --> G["Output Filter"]
G --> H["Quality Gate"]
H --> I["Respond"]
H --> J["Retrieve"]
H --> K["Fallback"]
J --> C
```

**Diagram sources**
- [graph.py:315-342](file://safe4ai-pilot/app/agents/graph.py#L315-L342)

## Streaming Implementation
The system now supports real-time streaming via LangGraph's `astream()` method, enabling progressive state updates and immediate feedback to clients with enhanced type safety.

### Streaming Flow
1. **Initialization**: Create run state with `_build_run_state()` and establish trace ID
2. **Streaming**: Use `graph.astream(run_state)` to iterate through node states
3. **State Merging**: Apply `_merge_stream_state()` to combine partial updates with improved type handling
4. **Progressive Updates**: Emit SSE events for step transitions and token streaming
5. **Finalization**: Complete processing and save session state

### State Merging Mechanism
The `_merge_stream_state()` function handles partial state updates from streaming nodes with enhanced type safety:

```mermaid
flowchart TD
Start(["Stream State Merge"]) --> CheckType{"Is update PrivateAIState?"}
CheckType --> |Yes| ReturnPS["Return PrivateAIState directly"]
CheckType --> |No| DumpCurrent["Dump current state to dict"]
DumpCurrent --> UpdateDict["Update with partial dict"]
UpdateDict --> Reconstruct["Reconstruct PrivateAIState"]
Reconstruct --> End(["Merged State"])
ReturnPS --> End
```

**Diagram sources**
- [chat_routes.py:115-121](file://safe4ai-pilot/app/api/chat_routes.py#L115-L121)

**Section sources**
- [chat_routes.py:234-361](file://safe4ai-pilot/app/api/chat_routes.py#L234-L361)
- [chat_routes.py:115-121](file://safe4ai-pilot/app/api/chat_routes.py#L115-L121)
- [test_chat.py:179-223](file://safe4ai-pilot/tests/test_chat.py#L179-L223)

## Detailed Component Analysis

### PrivateAIState Model
PrivateAIState encapsulates the conversation state and pipeline metadata. It is a Pydantic model that enforces type safety and defaults for optional fields. The model now supports enhanced state merging for streaming operations with improved type annotations:

- Conversation history: list of messages with role and content using Pydantic's Literal types
- Execution control: current_step and status using Pydantic's Literal types for enhanced type safety
- Retrieval pipeline: rewritten_query, retrieved_chunks (RankedChunk), graded_chunks (GradedChunk), retrieval_score_max, retrieval_attempts
- Decomposition: sub_queries
- Generation: draft_answer, citations, generation_context
- Safety and observability: grounded, requires_human_review, errors, trace_id, cost_usd
- Provider usage tracking: provider_usage field for cost monitoring

```mermaid
classDiagram
class PrivateAIState {
+string session_id
+string user_id
+Message[] messages
+Literal current_step
+Literal status
+string rewritten_query
+RankedChunk[] retrieved_chunks
+GradedChunk[] graded_chunks
+float retrieval_score_max
+string[] sub_queries
+string draft_answer
+Citation[] citations
+bool grounded
+string trace_id
+float cost_usd
+string[] errors
+bool requires_human_review
+int retrieval_attempts
+GradedChunk[] generation_context
+ProviderUsage provider_usage
}
class Message {
+Literal role
+string content
+datetime created_at
}
class RankedChunk {
+string chunk_id
+string doc_id
+string filename
+int page_number
+string content
+float score
+float rerank_score
}
class GradedChunk {
+bool relevant
+string reason
}
class Citation {
+string filename
+int page_number
+string excerpt
+float score
}
PrivateAIState --> Message : "messages"
PrivateAIState --> RankedChunk : "retrieved_chunks"
PrivateAIState --> GradedChunk : "graded_chunks"
PrivateAIState --> Citation : "citations"
RankedChunk <|-- GradedChunk : "extends"
```

**Diagram sources**
- [models.py:49-113](file://safe4ai-pilot/app/models.py#L49-L113)
- [models.py:17-46](file://safe4ai-pilot/app/models.py#L17-L46)

**Section sources**
- [models.py:49-113](file://safe4ai-pilot/app/models.py#L49-L113)

### Node: intake
Purpose: Validate the latest message and enforce input safety. If invalid, route to fallback; otherwise, move to rewrite.

Behavior:
- If no messages, set current_step to fallback and record an error.
- Apply InputGuard to the query; if disallowed, append reason to errors and route to fallback.
- Otherwise, advance to rewrite.

```mermaid
flowchart TD
Start(["Entry: intake"]) --> CheckMsgs["Has messages?"]
CheckMsgs --> |No| SetFallback["Set current_step=fallback<br/>Add error: no messages"]
CheckMsgs --> |Yes| Guard["InputGuard.check(query)"]
Guard --> Allowed{"Allowed?"}
Allowed --> |No| RouteFB["Append reason to errors<br/>Set current_step=fallback"]
Allowed --> |Yes| NextRR["Set current_step=rewrite"]
SetFallback --> End(["Exit"])
RouteFB --> End
NextRR --> End
```

**Diagram sources**
- [graph.py:62-74](file://safe4ai-pilot/app/agents/graph.py#L62-L74)
- [input_guard.py:27-49](file://safe4ai-pilot/app/security/input_guard.py#L27-L49)

**Section sources**
- [graph.py:62-74](file://safe4ai-pilot/app/agents/graph.py#L62-L74)
- [input_guard.py:24-49](file://safe4ai-pilot/app/security/input_guard.py#L24-L49)

### Node: rewrite
Purpose: Produce a rewritten query using a prompt and model.

Behavior:
- Render a rewrite prompt with the latest message content and up to 6 prior exchanges.
- Call LLM generate endpoint; on success, set rewritten_query and advance to retrieve.
- On failure, preserve original query and still advance to retrieve.

```mermaid
sequenceDiagram
participant N as "rewrite_node"
participant P as "Prompts"
participant O as "LLM"
N->>P : "Load rewrite prompt"
N->>O : "Generate (prompt with history)"
O-->>N : "response (text)"
N->>N : "Set rewritten_query"
N-->>N : "Set current_step=retrieve"
```

**Diagram sources**
- [graph.py:75-100](file://safe4ai-pilot/app/agents/graph.py#L75-L100)

**Section sources**
- [graph.py:75-100](file://safe4ai-pilot/app/agents/graph.py#L75-L100)

### Node: retrieve
Purpose: Retrieve candidate chunks and rerank them.

Behavior:
- Retrieve chunks via HybridRetriever and rerank via Reranker.
- Record chunk count and max score in span attributes.
- Increment retrieval_attempts and proceed to grade.
- On exceptions, record error and continue to grade.

```mermaid
sequenceDiagram
participant N as "retrieve_node"
participant R as "HybridRetriever"
participant X as "Reranker"
N->>R : "retrieve(query, top_k)"
R-->>N : "raw chunks"
N->>X : "rerank(query, raw, top_n)"
X-->>N : "ranked chunks"
N->>N : "Update retrieved_chunks, retrieval_score_max, retrieval_attempts"
N-->>N : "Set current_step=grade"
```

**Diagram sources**
- [graph.py:101-123](file://safe4ai-pilot/app/agents/graph.py#L101-L123)
- [hybrid_retriever.py:56-143](file://safe4ai-pilot/app/components/hybrid_retriever.py#L56-L143)
- [reranker.py:15-36](file://safe4ai-pilot/app/components/reranker.py#L15-L36)

**Section sources**
- [graph.py:101-123](file://safe4ai-pilot/app/agents/graph.py#L101-L123)
- [hybrid_retriever.py:13-143](file://safe4ai-pilot/app/components/hybrid_retriever.py#L13-L143)
- [reranker.py:11-36](file://safe4ai-pilot/app/components/reranker.py#L11-L36)

### Node: grade
Purpose: Determine whether to generate or decompose based on relevance.

Behavior:
- Grade chunks using document_grader and compute relevant_count.
- Use LLM-based routing via decide_next_step with allowed steps ["generate","decompose"].
- Fallback to synchronous rule: ≥2 relevant → generate, else → decompose.
- Enforce safety: if synchronous rule says decompose, override LLM decision to decompose.
- Set current_step accordingly.

```mermaid
flowchart TD
Start(["Entry: grade"]) --> Grade["grade_chunks(query, chunks)"]
Grade --> Count["Count relevant chunks"]
Count --> Decide["decide_next_step(state, ['generate','decompose'])"]
Decide --> Decision{"Decision"}
Decision --> |generate| Gen["Set current_step=generate"]
Decision --> |decompose| Decomp["Set current_step=decompose"]
Decide --> |error| Sync["route_after_grade(state)"]
Sync --> SyncDec{"≥2 relevant?"}
SyncDec --> |Yes| Gen
SyncDec --> |No| Decomp
```

**Diagram sources**
- [graph.py:124-142](file://safe4ai-pilot/app/agents/graph.py#L124-L142)
- [adaptive_router.py:6-11](file://safe4ai-pilot/app/agents/adaptive_router.py#L6-L11)
- [document_grader.py:29-72](file://safe4ai-pilot/app/agents/document_grader.py#L29-L72)

**Section sources**
- [graph.py:124-142](file://safe4ai-pilot/app/agents/graph.py#L124-L142)
- [adaptive_router.py:1-18](file://safe4ai-pilot/app/agents/adaptive_router.py#L1-L18)
- [document_grader.py:1-72](file://safe4ai-pilot/app/agents/document_grader.py#L1-L72)

### Node: decompose
Purpose: Generate sub-queries and re-run retrieval/grading per sub-query.

Behavior:
- Call query_decomposer to produce sub-queries.
- For each sub-query, retrieve, rerank, grade, and accumulate results.
- Compute max score across all graded chunks and set requires_human_review if none relevant.
- Proceed to generate.

```mermaid
sequenceDiagram
participant N as "decompose_node"
participant D as "query_decomposer"
participant R as "HybridRetriever"
participant X as "Reranker"
participant G as "document_grader"
N->>D : "decompose_query(query)"
D-->>N : "sub_queries"
loop for each sub_query
N->>R : "retrieve(sub_query)"
R-->>N : "raw chunks"
N->>X : "rerank(sub_query, raw, top_n)"
X-->>N : "ranked"
N->>G : "grade_chunks(sub_query, ranked)"
G-->>N : "graded"
end
N->>N : "Update sub_queries, graded_chunks, retrieval_score_max, requires_human_review"
N-->>N : "Set current_step=generate"
```

**Diagram sources**
- [graph.py:143-183](file://safe4ai-pilot/app/agents/graph.py#L143-L183)
- [query_decomposer.py:10-41](file://safe4ai-pilot/app/agents/query_decomposer.py#L10-L41)
- [hybrid_retriever.py:56-143](file://safe4ai-pilot/app/components/hybrid_retriever.py#L56-L143)
- [reranker.py:15-36](file://safe4ai-pilot/app/components/reranker.py#L15-L36)
- [document_grader.py:29-72](file://safe4ai-pilot/app/agents/document_grader.py#L29-L72)

**Section sources**
- [graph.py:143-183](file://safe4ai-pilot/app/agents/graph.py#L143-L183)
- [query_decomposer.py:10-41](file://safe4ai-pilot/app/agents/query_decomposer.py#L10-L41)
- [hybrid_retriever.py:13-143](file://safe4ai-pilot/app/components/hybrid_retriever.py#L13-L143)
- [reranker.py:11-36](file://safe4ai-pilot/app/components/reranker.py#L11-L36)
- [document_grader.py:1-72](file://safe4ai-pilot/app/agents/document_grader.py#L1-L72)

### Node: generate
Purpose: Construct a grounded answer from relevant chunks.

Behavior:
- If no relevant chunks, set a safe default answer and skip citations.
- Otherwise, build context from relevant chunks and render a prompt to generate an answer.
- On success, create citations from relevant chunks; on failure, record error and fall back to safe answer.
- Advance to output_filter.

```mermaid
flowchart TD
Start(["Entry: generate"]) --> FindRel["Find relevant graded chunks"]
FindRel --> HasRel{"Any relevant?"}
HasRel --> |No| SafeAns["Set draft_answer=safe default<br/>Set citations=[]"]
HasRel --> |Yes| BuildCtx["Build context from relevant"]
BuildCtx --> Prompt["Render answer prompt"]
Prompt --> CallLLM["Call LLM generate"]
CallLLM --> AnsOK{"Success?"}
AnsOK --> |Yes| MakeCites["Create citations from relevant"]
AnsOK --> |No| ErrPath["Record error<br/>Set safe answer"]
SafeAns --> Next["Set current_step=output_filter"]
MakeCites --> Next
ErrPath --> Next
```

**Diagram sources**
- [graph.py:184-241](file://safe4ai-pilot/app/agents/graph.py#L184-L241)

**Section sources**
- [graph.py:184-241](file://safe4ai-pilot/app/agents/graph.py#L184-L241)

### Node: output_filter
Purpose: Validate the generated answer for safety and PII with simplified sequence handling.

Behavior:
- If no relevant context or empty answer, skip filtering and go to quality_gate.
- Otherwise, check answer against source chunks for PII hallucinations and suspicious length.
- **Updated**: Simplified sequence handling - GradedChunk extends RankedChunk, so we can pass GradedChunk instances directly to output_filter which accepts Sequence[RankedChunk].
- If blocked, set requires_human_review and record reason; otherwise, proceed to quality_gate.

```mermaid
flowchart TD
Start(["Entry: output_filter"]) --> CheckCtx["Has relevant context and non-empty answer?"]
CheckCtx --> |No| ToGate["Set current_step=quality_gate"]
CheckCtx --> |Yes| Guard["OutputFilter.check(answer, relevant, citations)"]
Guard --> Allowed{"Allowed?"}
Allowed --> |No| Block["Set draft_answer=safe default<br/>Set requires_human_review=true<br/>Append reason to errors"]
Allowed --> |Yes| ToGate2["Set current_step=quality_gate"]
Block --> ToGate
ToGate2 --> End(["Exit"])
```

**Diagram sources**
- [graph.py:242-261](file://safe4ai-pilot/app/agents/graph.py#L242-L261)
- [output_filter.py:26-74](file://safe4ai-pilot/app/security/output_filter.py#L26-L74)

**Section sources**
- [graph.py:242-261](file://safe4ai-pilot/app/agents/graph.py#L242-L261)
- [output_filter.py:26-74](file://safe4ai-pilot/app/security/output_filter.py#L26-L74)

### Node: quality_gate
Purpose: Final routing decision with self-correction guard.

Behavior:
- Compute groundedness from draft_answer and presence of relevant chunks.
- Allow ["respond","retrieve","fallback"] unless retrieval attempts exceed a maximum.
- Use LLM-based routing with decide_next_step; fallback to synchronous rule if LLM fails.
- Safety: never route ungrounded state to respond; if LLM selects respond but state is not grounded, select fallback.
- Set grounded and current_step accordingly.

```mermaid
flowchart TD
Start(["Entry: quality_gate"]) --> Grounded["Compute grounded from draft_answer and relevant chunks"]
Grounded --> Attempts{"retrieval_attempts < max?"}
Attempts --> |Yes| Allowed["allowed=['respond','retrieve','fallback']"]
Attempts --> |No| Allowed2["allowed=['respond','fallback']"]
Allowed --> Decide["decide_next_step(state, allowed)"]
Allowed2 --> Decide
Decide --> Decision{"Decision"}
Decision --> |respond & grounded| Res["Set grounded=true<br/>Set current_step=respond"]
Decision --> |respond & not grounded| FB["Set current_step=fallback"]
Decision --> |retrieve| Retr["Set current_step=retrieve"]
Decision --> |fallback| FB2["Set current_step=fallback"]
Decide --> |error| Sync["Default to 'respond' if grounded else 'fallback'"]
Sync --> Decision
```

**Diagram sources**
- [graph.py:262-288](file://safe4ai-pilot/app/agents/graph.py#L262-L288)
- [adaptive_router.py:13-18](file://safe4ai-pilot/app/agents/adaptive_router.py#L13-L18)

**Section sources**
- [graph.py:262-288](file://safe4ai-pilot/app/agents/graph.py#L262-L288)
- [adaptive_router.py:1-18](file://safe4ai-pilot/app/agents/adaptive_router.py#L1-L18)

### Node: respond
Purpose: Mark completion and terminate the graph.

Behavior:
- Set status to completed and current_step to respond.

**Section sources**
- [graph.py:289-292](file://safe4ai-pilot/app/agents/graph.py#L289-L292)

### Node: fallback
Purpose: Provide a safe default answer and mark completion.

Behavior:
- Use draft_answer if present; otherwise, use a safe default.
- Set status to completed, current_step to fallback, and requires_human_review if errors or previously flagged.

**Section sources**
- [graph.py:293-302](file://safe4ai-pilot/app/agents/graph.py#L293-L302)

### Routing Logic and Transitions
- Conditional edges:
  - intake → rewrite or fallback based on current_step after intake.
  - grade → generate or decompose based on LLM decision with fallback to synchronous rule.
  - quality_gate → respond, retrieve, or fallback based on groundedness and retrieval attempts.
- Deterministic edges:
  - rewrite → retrieve
  - retrieve → grade
  - decompose → generate
  - generate → output_filter
  - output_filter → quality_gate
  - respond → END
  - fallback → END

```mermaid
sequenceDiagram
participant G as "StateGraph"
G->>G : "intake → decide : rewrite or fallback"
G->>G : "rewrite → retrieve"
G->>G : "retrieve → grade"
G->>G : "grade → decide : generate or decompose"
G->>G : "decompose → generate"
G->>G : "generate → output_filter"
G->>G : "output_filter → quality_gate"
G->>G : "quality_gate → decide : respond/retrieve/fallback"
G->>G : "respond → END"
G->>G : "fallback → END"
```

**Diagram sources**
- [graph.py:318-342](file://safe4ai-pilot/app/agents/graph.py#L318-L342)

**Section sources**
- [graph.py:318-342](file://safe4ai-pilot/app/agents/graph.py#L318-L342)

## Dependency Analysis
The graph composes specialized components with enhanced type safety:
- Retrieval: HybridRetriever depends on Qdrant and Ollama embeddings; Reranker uses a cross-encoder model.
- Grading: Asynchronous per-chunk grading via LLM with improved type handling through Pydantic models.
- Decomposition: Sub-query generation via LLM.
- Guards: InputGuard and OutputFilter provide safety checks with enhanced sequence handling.
- Routing: LLM-based routing with synchronous fallbacks.
- Streaming: Enhanced with state merging for real-time updates and improved type safety.

```mermaid
graph TB
G["graph.py"]
AR["adaptive_router.py"]
DG["document_grader.py"]
QD["query_decomposer.py"]
HR["hybrid_retriever.py"]
RR["reranker.py"]
IG["input_guard.py"]
OF["output_filter.py"]
CR["chat_routes.py"]
M["models.py"]
G --> AR
G --> DG
G --> QD
G --> HR
G --> RR
G --> IG
G --> OF
CR --> G
CR --> M
```

**Diagram sources**
- [graph.py:11-22](file://safe4ai-pilot/app/agents/graph.py#L11-L22)
- [adaptive_router.py:1-10](file://safe4ai-pilot/app/agents/adaptive_router.py#L1-L10)
- [document_grader.py:9-12](file://safe4ai-pilot/app/agents/document_grader.py#L9-L12)
- [query_decomposer.py:7-10](file://safe4ai-pilot/app/agents/query_decomposer.py#L7-L10)
- [hybrid_retriever.py:10](file://safe4ai-pilot/app/components/hybrid_retriever.py#L10)
- [reranker.py:6](file://safe4ai-pilot/app/components/reranker.py#L6)
- [input_guard.py:7](file://safe4ai-pilot/app/security/input_guard.py#L7)
- [output_filter.py:9](file://safe4ai-pilot/app/security/output_filter.py#L9)
- [chat_routes.py:224-361](file://safe4ai-pilot/app/api/chat_routes.py#L224-L361)
- [models.py:49-113](file://safe4ai-pilot/app/models.py#L49-L113)

**Section sources**
- [graph.py:11-22](file://safe4ai-pilot/app/agents/graph.py#L11-L22)

## Performance Considerations
- Parallelism:
  - Chunk grading uses asynchronous gathering to process multiple chunks concurrently with improved type safety.
  - Decompose runs retrieval/grading per sub-query; consider batching and rate limiting to avoid downstream saturation.
- Latency:
  - Retrieval and reranking are I/O bound; caching or precomputation of rerank scores can help.
  - LLM calls are latency-sensitive; timeouts are configured; consider connection pooling and retries with backoff.
- Cost:
  - PrivateAIState includes a cost accumulator field and provider_usage tracking; integrate cost tracking around LLM calls for visibility.
- Memory:
  - generation_context snapshots ensure output_filter validates against a stable set of chunks; keep this bounded to control memory growth.
- Streaming:
  - State merging overhead is minimal compared to network latency for streaming responses.
  - Token streaming provides immediate feedback while maintaining state consistency with enhanced type safety.

## Troubleshooting Guide
Common issues and remedies:
- No messages in state:
  - intake_node sets current_step to fallback and records an error; ensure callers populate messages.
- Input rejected by guard:
  - intake_node appends the reason to errors and routes to fallback; sanitize input or adjust guard thresholds.
- LLM failures during rewrite or grading:
  - Nodes fall back to safe defaults and still advance; inspect errors and retry logic.
- Retrieval failures:
  - retrieve_node increments retrieval_attempts and continues to grade; monitor errors and backend health.
- Un-grounded answer:
  - quality_gate prevents responding with ungrounded answers; trigger fallback and human review if needed.
- PII hallucination:
  - output_filter blocks answers containing PII not present in source chunks; refined sequence handling ensures proper validation.
- Streaming issues:
  - State merging failures: verify `_merge_stream_state()` handles both PrivateAIState and dict updates correctly with enhanced type safety.
  - Partial updates: ensure nodes return consistent state updates that can be merged safely.
  - Client disconnection: streaming gracefully handles disconnections and cleans up resources.

Operational hooks:
- Per-node spans capture session_id, trace_id, and node attributes for debugging.
- Pipeline-level span wraps the entire run for end-to-end tracing.
- Streaming state merging ensures consistent state even with partial updates and improved type safety.

**Section sources**
- [graph.py:62-74](file://safe4ai-pilot/app/agents/graph.py#L62-L74)
- [graph.py:75-100](file://safe4ai-pilot/app/agents/graph.py#L75-L100)
- [graph.py:101-123](file://safe4ai-pilot/app/agents/graph.py#L101-L123)
- [graph.py:124-142](file://safe4ai-pilot/app/agents/graph.py#L124-L142)
- [graph.py:242-261](file://safe4ai-pilot/app/agents/graph.py#L242-L261)
- [graph.py:262-288](file://safe4ai-pilot/app/agents/graph.py#L262-L288)
- [chat_routes.py:115-121](file://safe4ai-pilot/app/api/chat_routes.py#L115-L121)
- [tracer.py:34-76](file://safe4ai-pilot/observability/tracer.py#L34-L76)
- [agent_runner.py:26-32](file://safe4ai-pilot/app/services/agent_runner.py#L26-L32)

## Conclusion
The LangGraph State Machine orchestrates a robust, self-correcting RAG pipeline with strong safety and observability. PrivateAIState centralizes conversation context and execution metadata with enhanced type safety through Pydantic models, enabling clear state transitions and resilient routing. The enhanced streaming capabilities with improved state merging mechanism provide real-time feedback while maintaining state consistency. The design balances LLM-driven adaptivity with synchronous fallbacks, ensuring reliable outcomes under failure conditions. The simplified GradedChunk→RankedChunk conversion logic and improved sequence handling in output filtering demonstrate better type safety and cleaner code architecture. Extensibility is achieved by adding nodes, updating state fields, and integrating custom routing logic with streaming support.

## Appendices

### Extending the State Machine
- Add a new node:
  - Define an async function that takes PrivateAIState and returns a dict of state updates.
  - Register the node with builder.add_node and wire edges (conditional or deterministic).
  - Ensure the node returns state updates compatible with streaming state merging and enhanced type safety.
- Modify state variables:
  - Extend PrivateAIState with new fields using Pydantic's Field defaults; initialize defaults in the model.
  - Update nodes to read/write the new fields with proper type annotations.
  - Verify state merging compatibility for streaming operations and enhanced type safety.
- Custom routing:
  - Implement a decision function similar to decide_next_step and route_after_grade.
  - Use it in a conditional edge to route to new nodes.
- Streaming compatibility:
  - Ensure all state updates are serializable and mergeable with proper type handling.
  - Test with `_merge_stream_state()` to verify proper state reconstruction with enhanced type safety.

**Section sources**
- [graph.py:296-342](file://safe4ai-pilot/app/agents/graph.py#L296-L342)
- [models.py:49-113](file://safe4ai-pilot/app/models.py#L49-L113)
- [chat_routes.py:115-121](file://safe4ai-pilot/app/api/chat_routes.py#L115-L121)

### Observability and Tracing
- Per-node spans:
  - Each node starts a child span inheriting from the pipeline span; attributes include session_id, trace_id, and node name.
- Pipeline span:
  - agent_runner.py wraps the entire graph execution in a pipeline span and saves session state afterward.
- Exporter:
  - tracer.py configures OTLP exporter and batch processor; spans are exported to the configured endpoint.

```mermaid
sequenceDiagram
participant Runner as "agent_runner.run_agent_query"
participant Tracer as "PipelineSpan"
participant Graph as "StateGraph"
Runner->>Tracer : "Enter pipeline span"
Runner->>Graph : "ainvoke(state)"
Graph-->>Runner : "final state"
Runner->>Runner : "Save session and optionally queue human review"
Runner->>Tracer : "Exit pipeline span"
```

**Diagram sources**
- [agent_runner.py:14-55](file://safe4ai-pilot/app/services/agent_runner.py#L14-L55)
- [tracer.py:34-76](file://safe4ai-pilot/observability/tracer.py#L34-L76)
- [graph.py:24-32](file://safe4ai-pilot/app/agents/graph.py#L24-L32)

**Section sources**
- [agent_runner.py:14-55](file://safe4ai-pilot/app/services/agent_runner.py#L14-L55)
- [tracer.py:27-31](file://safe4ai-pilot/observability/tracer.py#L27-L31)
- [graph.py:24-32](file://safe4ai-pilot/app/agents/graph.py#L24-L32)

### State Persistence and Recovery
- Persistence:
  - After graph completion, agent_runner persists the final state via ConversationManager.save_session.
  - Human review entries are inserted when requires_human_review is true.
- Recovery:
  - retrieval_attempts guard prevents infinite self-correction loops; after exceeding the maximum, routing is restricted to respond or fallback.
  - Fallback ensures a safe default answer is returned when groundedness cannot be established.
- Streaming recovery:
  - State merging mechanism ensures partial updates are safely combined with enhanced type safety.
  - Streaming gracefully handles client disconnections and maintains state consistency.

**Section sources**
- [agent_runner.py:36-54](file://safe4ai-pilot/app/services/agent_runner.py#L36-L54)
- [graph.py:270-288](file://safe4ai-pilot/app/agents/graph.py#L270-L288)
- [graph.py:293-302](file://safe4ai-pilot/app/agents/graph.py#L293-L302)
- [chat_routes.py:234-361](file://safe4ai-pilot/app/api/chat_routes.py#L234-L361)

### Streaming State Management
The streaming implementation provides real-time state updates with robust merging capabilities and enhanced type safety:

- **State Merging**: `_merge_stream_state()` handles both PrivateAIState objects and dict updates with improved type handling
- **Streaming Flow**: `graph.astream()` provides node-by-node state updates with enhanced type safety
- **Progressive Updates**: SSE events deliver step transitions and token streaming
- **Error Handling**: Graceful degradation with fallback to safe defaults
- **Testing**: Comprehensive test coverage for partial state update scenarios with proper type validation

**Section sources**
- [chat_routes.py:115-121](file://safe4ai-pilot/app/api/chat_routes.py#L115-L121)
- [chat_routes.py:234-361](file://safe4ai-pilot/app/api/chat_routes.py#L234-L361)
- [test_chat.py:179-223](file://safe4ai-pilot/tests/test_chat.py#L179-L223)