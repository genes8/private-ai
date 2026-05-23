# Provider Settings Management

<cite>
**Referenced Files in This Document**
- [settings_routes.py](file://safe4ai-pilot/app/api/settings_routes.py)
- [settings_service.py](file://safe4ai-pilot/app/services/settings_service.py)
- [provider_settings.py](file://safe4ai-pilot/app/services/provider_settings.py)
- [provider_clients.py](file://safe4ai-pilot/app/services/provider_clients.py)
- [embedding_provider.py](file://safe4ai-pilot/app/components/embedding_provider.py)
- [SettingsPage.tsx](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx)
- [ProviderSettingsSection.tsx](file://safe4ai-pilot/frontend/src/components/admin/ProviderSettingsSection.tsx)
- [settings.ts](file://safe4ai-pilot/frontend/src/api/settings.ts)
- [models.py](file://safe4ai-pilot/app/db/models.py)
- [config.py](file://safe4ai-pilot/app/config.py)
</cite>

## Update Summary
**Changes Made**
- Updated Frontend Implementation section to reflect CustomModelManager component refactoring
- Updated Provider Modes and Configuration section to reflect SSE completion mode relocation to Retrieval section
- Added documentation for intersection observer-based navigation synchronization
- Enhanced user experience features documentation

## Table of Contents
1. [Introduction](#introduction)
2. [System Architecture](#system-architecture)
3. [Provider Modes and Configuration](#provider-modes-and-configuration)
4. [Backend Implementation](#backend-implementation)
5. [Frontend Implementation](#frontend-implementation)
6. [Runtime Integration](#runtime-integration)
7. [Validation and Safety Mechanisms](#validation-and-safety-mechanisms)
8. [Error Handling and Diagnostics](#error-handling-and-diagnostics)
9. [Best Practices and Guidelines](#best-practices-and-guidelines)
10. [Troubleshooting Guide](#troubleshooting-guide)

## Introduction

Provider Settings Management is a critical component of the private-ai system that controls how inference providers are configured and managed. This system enables administrators to select between different provider modes (Local, Hybrid, Cloud), configure API endpoints, manage authentication credentials, and control model selection for various AI capabilities including chat, embeddings, and vision processing.

The system provides three distinct operational modes to balance performance, privacy, and cost considerations while maintaining robust validation and safety mechanisms to prevent misconfiguration that could impact system stability or data privacy.

**Updated** Enhanced with improved user experience features including custom model management and automatic navigation synchronization.

## System Architecture

The Provider Settings Management system follows a layered architecture with clear separation of concerns between frontend presentation, backend validation, and runtime integration.

```mermaid
graph TB
subgraph "Frontend Layer"
SP[SettingsPage.tsx]
PSS[ProviderSettingsSection.tsx]
CM[CustomModelManager]
API[settings.ts]
end
subgraph "Backend Layer"
SR[settings_routes.py]
SS[settings_service.py]
PS[provider_settings.py]
PC[provider_clients.py]
end
subgraph "Infrastructure Layer"
DB[AppConfig table]
CFG[config.py]
RT[Runtime Components]
end
SP --> PSS
PSS --> CM
PSS --> API
API --> SR
SR --> SS
SS --> PS
SS --> PC
SR --> DB
SS --> DB
PS --> CFG
PC --> RT
```

**Diagram sources**
- [settings_routes.py:1-354](file://safe4ai-pilot/app/api/settings_routes.py#L1-L354)
- [settings_service.py:1-415](file://safe4ai-pilot/app/services/settings_service.py#L1-L415)
- [provider_settings.py:1-225](file://safe4ai-pilot/app/services/provider_settings.py#L1-L225)

## Provider Modes and Configuration

The system supports three distinct provider modes, each with specific characteristics and use cases:

### Local Mode
- **Description**: Chat and document search run entirely on local Ollama server
- **Privacy**: Maximum privacy - no data leaves the local server
- **Requirements**: Ollama must be running locally
- **Capabilities**: Full local processing for chat, embeddings, and vision

### Hybrid Mode
- **Description**: Cloud LLM for answers, Ollama for document search
- **Privacy**: Balanced privacy - documents stay local, queries go to cloud
- **Requirements**: Working cloud provider connection and local Ollama
- **Capabilities**: Cloud chat with local embeddings

### Cloud Mode
- **Description**: Chat and document search both via cloud API
- **Privacy**: Lower privacy - all data goes to cloud provider
- **Requirements**: Working cloud provider connection with embeddings support
- **Capabilities**: Full cloud processing for all AI tasks

```mermaid
flowchart TD
Start([Provider Selection]) --> Mode{"Select Mode"}
Mode --> |Local| Local[Local Mode<br/>• All processing local<br/>• Ollama required<br/>• Highest privacy]
Mode --> |Hybrid| Hybrid[Hybrid Mode<br/>• Cloud chat<br/>• Local embeddings<br/>• Balanced privacy]
Mode --> |Cloud| Cloud[Cloud Mode<br/>• All processing cloud<br/>• Embeddings required<br/>• Lower privacy]
Local --> LocalConfig[Configure Local Models]
Hybrid --> HybridConfig[Configure Cloud Endpoint + Local Models]
Cloud --> CloudConfig[Configure Cloud Credentials + Models]
LocalConfig --> ValidateLocal{Validate Ollama}
HybridConfig --> ValidateHybrid{Validate Ollama + Cloud}
CloudConfig --> ValidateCloud{Validate Cloud API}
ValidateLocal --> ApplyLocal[Apply Configuration]
ValidateHybrid --> ApplyHybrid[Apply Configuration]
ValidateCloud --> ApplyCloud[Apply Configuration]
```

**Diagram sources**
- [settings_routes.py:227-286](file://safe4ai-pilot/app/api/settings_routes.py#L227-L286)
- [settings_service.py:138-164](file://safe4ai-pilot/app/services/settings_service.py#L138-L164)

**Section sources**
- [settings_routes.py:17-354](file://safe4ai-pilot/app/api/settings_routes.py#L17-L354)
- [settings_service.py:38-66](file://safe4ai-pilot/app/services/settings_service.py#L38-L66)

## Backend Implementation

The backend implementation consists of three main layers: API routes, service logic, and provider-specific utilities.

### API Routes Layer

The settings routes handle HTTP requests and coordinate between different service layers:

```mermaid
sequenceDiagram
participant Client as "Admin Client"
participant Route as "settings_routes.py"
participant Service as "settings_service.py"
participant Provider as "provider_settings.py"
participant Runtime as "build_runtime_components"
Client->>Route : PATCH /settings
Route->>Service : normalize_patch_request()
Service->>Provider : expand_provider_mode()
Provider-->>Service : ProviderPatch
Service->>Service : probe_provider_prerequisites()
Service->>Provider : validate_hybrid_embedding()
Service->>Provider : sanitize_ollama_role_models()
Service->>Service : collect_field_updates()
Service->>Route : updates dict
Route->>Runtime : build_runtime_components()
Runtime-->>Route : new components
Route-->>Client : Updated settings
```

**Diagram sources**
- [settings_routes.py:227-286](file://safe4ai-pilot/app/api/settings_routes.py#L227-L286)
- [settings_service.py:138-415](file://safe4ai-pilot/app/services/settings_service.py#L138-L415)

### Service Layer Logic

The service layer implements a three-stage pipeline for processing settings updates:

1. **Normalize Stage**: Expands mode shorthands and derives effective values
2. **Probe Stage**: Validates external dependencies and sanitizes stale configurations
3. **Collect Stage**: Validates individual fields and builds database updates

### Provider Settings Resolution

The provider settings module handles the core logic for provider mode resolution and validation:

```mermaid
classDiagram
class ProviderResolution {
+string provider_type
+string embedding_source
+string provider_mode
}
class ProviderPatch {
+dict pre_updates
+dict body_overrides
}
class ProviderSettings {
+resolve_provider_config(raw_config) ProviderResolution
+expand_provider_mode(mode, base_url) ProviderPatch
+validate_hybrid_embedding() string|None
+sanitize_ollama_role_models() dict
+probe_cloud_embeddings() void
}
ProviderSettings --> ProviderResolution : creates
ProviderSettings --> ProviderPatch : creates
```

**Diagram sources**
- [provider_settings.py:18-62](file://safe4ai-pilot/app/services/provider_settings.py#L18-L62)
- [provider_settings.py:27-33](file://safe4ai-pilot/app/services/provider_settings.py#L27-L33)

**Section sources**
- [settings_routes.py:227-286](file://safe4ai-pilot/app/api/settings_routes.py#L227-L286)
- [settings_service.py:138-415](file://safe4ai-pilot/app/services/settings_service.py#L138-L415)
- [provider_settings.py:35-225](file://safe4ai-pilot/app/services/provider_settings.py#L35-L225)

## Frontend Implementation

The frontend provides an intuitive administrative interface for managing provider settings with real-time validation and feedback, enhanced with improved user experience features.

### Settings Page Architecture

```mermaid
graph LR
SP[SettingsPage.tsx] --> PSS[ProviderSettingsSection.tsx]
SP --> Models[Models Section]
SP --> Retrieval[Retrieval Section]
SP --> Sources[Sources Section]
SP --> Security[Security Section]
SP --> Cost[Cost Ceiling Section]
PSS --> ModeCards[Mode Selection Cards]
PSS --> ConfigInputs[Configuration Inputs]
PSS --> TestButton[Test Connection Button]
PSS --> CustomModelManager[CustomModelManager Component]
ModeCards --> LocalMode[Local Mode UI]
ModeCards --> HybridMode[Hybrid Mode UI]
ModeCards --> CloudMode[Cloud Mode UI]
ConfigInputs --> ModelSelect[Model Selection Dropdowns]
ConfigInputs --> TextInput[Text Input Fields]
ConfigInputs --> PasswordInput[Password Input Fields]
CustomModelManager --> CustomModelInput[Custom Model Input]
CustomModelManager --> CustomModelList[Custom Model List]
```

**Diagram sources**
- [SettingsPage.tsx:92-547](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L92-L547)
- [ProviderSettingsSection.tsx:33-294](file://safe4ai-pilot/frontend/src/components/admin/ProviderSettingsSection.tsx#L33-L294)

### Enhanced User Experience Features

**Updated** The frontend now includes several enhanced user experience features:

#### Intersection Observer-Based Navigation Synchronization
The SettingsPage implements an intersection observer that automatically synchronizes the active navigation section with the user's scroll position:

```mermaid
sequenceDiagram
participant User as "User Scroll"
participant Observer as "IntersectionObserver"
participant Nav as "Navigation"
participant Section as "Active Section"
User->>Observer : Scroll event
Observer->>Observer : Check element intersections
Observer->>Nav : Update active section
Nav->>Section : Highlight active section
Section->>User : Visual feedback
```

**Diagram sources**
- [SettingsPage.tsx:269-290](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L269-L290)

#### Custom Model Manager Component Refactoring
The CustomModelManager component has been refactored into a separate, reusable component within ProviderSettingsSection:

- **Custom Model Input**: Allows adding custom model names not present in the dropdown
- **Model List Management**: Provides visual chips for managing custom models
- **Real-time Validation**: Prevents duplicate model entries
- **Integration with Provider Settings**: Seamlessly integrated into provider configuration flows

#### SSE Completion Mode Relocation
The SSE completion mode setting has been moved from the Provider section to the Retrieval section for better logical grouping:

- **Location**: Now appears in the Retrieval section alongside other retrieval parameters
- **Functionality**: Controls streaming completion behavior (strict vs async)
- **Performance Impact**: Strict mode waits for persistence before sending completion, async mode prioritizes lower latency

### Real-time Validation and Feedback

The frontend implements sophisticated validation and user experience features:

- **Auto-save mechanism**: Changes are automatically saved with optimistic updates
- **Real-time validation**: Immediate feedback on configuration errors
- **Connection testing**: Built-in cloud provider connectivity verification
- **Model availability**: Dynamic model lists based on provider capabilities
- **Custom model management**: Enhanced model configuration with custom model support

**Section sources**
- [SettingsPage.tsx:92-547](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L92-L547)
- [ProviderSettingsSection.tsx:33-294](file://safe4ai-pilot/frontend/src/components/admin/ProviderSettingsSection.tsx#L33-L294)
- [settings.ts:8-103](file://safe4ai-pilot/frontend/src/api/settings.ts#L8-L103)

## Runtime Integration

The system integrates seamlessly with the runtime components to ensure configuration changes take effect immediately without requiring service restarts.

### Runtime Component Building

```mermaid
sequenceDiagram
participant Settings as "Settings Update"
participant DB as "Database"
participant Runtime as "Runtime Builder"
participant Components as "Components"
Settings->>DB : Commit configuration changes
DB-->>Settings : Acknowledge
Settings->>Runtime : build_runtime_components()
Runtime->>Components : Create new instances
Components-->>Runtime : Ready components
Runtime-->>Settings : Updated components
Settings->>Settings : Update application state
```

**Diagram sources**
- [settings_routes.py:267-277](file://safe4ai-pilot/app/api/settings_routes.py#L267-L277)

### Configuration Persistence

The system uses a dedicated configuration table for storing application settings with automatic timestamping and update tracking.

**Section sources**
- [settings_routes.py:265-286](file://safe4ai-pilot/app/api/settings_routes.py#L265-L286)
- [models.py:204-210](file://safe4ai-pilot/app/db/models.py#L204-L210)

## Validation and Safety Mechanisms

The system implements comprehensive validation and safety mechanisms to prevent misconfiguration and maintain system stability.

### Model Validation

```mermaid
flowchart TD
Start([Model Update Request]) --> CheckType{Provider Type?}
CheckType --> |Ollama| ValidateOllama[Validate against Ollama models]
CheckType --> |OpenAI Compatible| ValidateProvider[Validate against provider models]
ValidateOllama --> CheckAvailability{Model Available?}
ValidateProvider --> CheckDimension[Check embedding dimension]
CheckAvailability --> |No| Fallback[Fallback to default model]
CheckAvailability --> |Yes| Accept[Accept model]
CheckDimension --> DimensionMatch{Dimension matches?}
DimensionMatch --> |No| Reject[Reject - drop/recreate collection]
DimensionMatch --> |Yes| Accept
Fallback --> Accept
Accept --> Complete[Model accepted]
Reject --> Error[Validation error]
```

**Diagram sources**
- [settings_service.py:258-310](file://safe4ai-pilot/app/services/settings_service.py#L258-L310)
- [settings_service.py:99-103](file://safe4ai-pilot/app/services/settings_service.py#L99-L103)

### Safety Checks

The system performs several critical safety validations:

1. **Provider Reachability**: Ensures cloud providers are accessible before configuration
2. **Model Availability**: Verifies requested models exist in target systems
3. **Dimension Compatibility**: Confirms embedding model dimensions match existing collections
4. **Mode Invariants**: Maintains logical consistency between provider type and embedding source

**Section sources**
- [settings_service.py:171-251](file://safe4ai-pilot/app/services/settings_service.py#L171-L251)
- [provider_settings.py:99-225](file://safe4ai-pilot/app/services/provider_settings.py#L99-L225)

## Error Handling and Diagnostics

The system provides comprehensive error handling with clear diagnostic information for troubleshooting configuration issues.

### Error Categories

| Error Type | HTTP Status | Description | Recovery Action |
|------------|-------------|-------------|-----------------|
| Validation Error | 422 | Invalid configuration values | Fix input according to validation rules |
| Provider Unreachable | 503 | External service not accessible | Check network connectivity and credentials |
| Model Not Found | 422 | Requested model unavailable | Select available model or install missing model |
| Dimension Mismatch | 409 | Embedding dimension mismatch | Drop and recreate collection or change model |

### Diagnostic Features

- **Connection Testing**: Built-in cloud provider connectivity verification
- **Live Metadata**: Real-time statistics including cost tracking and model availability
- **Error Messages**: Specific, actionable error messages for each failure type
- **Audit Logging**: All configuration changes are logged for compliance tracking

**Section sources**
- [settings_routes.py:289-354](file://safe4ai-pilot/app/api/settings_routes.py#L289-L354)
- [settings_service.py:171-251](file://safe4ai-pilot/app/services/settings_service.py#L171-L251)

## Best Practices and Guidelines

### Provider Mode Selection

**Choose Local Mode When:**
- Maximum privacy requirements
- Limited or unreliable internet connectivity
- Compliance requirements mandate data stays on-premises
- Resource constraints limit cloud usage

**Choose Hybrid Mode When:**
- Need cloud-quality LLMs with local document processing
- Balance between performance and privacy
- Existing Ollama infrastructure available
- Mixed workloads with varying privacy requirements

**Choose Cloud Mode When:**
- Cloud provider offers superior LLM capabilities
- Document privacy is not a primary concern
- Centralized management preferred
- Budget allows for cloud compute costs

### Configuration Management

1. **Always test connections** before committing to new provider configurations
2. **Backup current settings** before major changes
3. **Monitor cost implications** when switching to cloud providers
4. **Validate model availability** in target environments
5. **Consider reindexing requirements** when changing embedding models

### Security Considerations

- Store API keys securely using environment variables
- Regularly rotate API keys for cloud providers
- Monitor provider access logs and usage patterns
- Limit administrative access to settings management
- Audit all configuration changes for compliance

## Troubleshooting Guide

### Common Issues and Solutions

**Issue**: "Hybrid mode requires local Ollama but Ollama is not reachable"
- **Cause**: Local Ollama service not running or accessible
- **Solution**: Start Ollama service and verify connectivity on port 11434

**Issue**: "Provider does not appear to support embeddings"
- **Cause**: Cloud provider lacks `/embeddings` endpoint support
- **Solution**: Switch to Hybrid mode or choose a different provider

**Issue**: "Embedding model is not available in Ollama"
- **Cause**: Requested model not pulled to local Ollama
- **Solution**: Run `ollama pull <model-name>` and retry

**Issue**: "Embedding model requires vector size X but collection has size Y"
- **Cause**: Changing embedding models requires collection recreation
- **Solution**: Drop and recreate Qdrant collection or revert model change

### Debugging Steps

1. **Verify provider connectivity** using the built-in test function
2. **Check model availability** in both Ollama and cloud provider
3. **Review configuration logs** for detailed error messages
4. **Validate network connectivity** to external services
5. **Confirm resource availability** (CPU, memory, disk space)

### Performance Optimization

- **Local Mode**: Optimal for privacy, moderate performance
- **Hybrid Mode**: Best balance of performance and privacy
- **Cloud Mode**: Highest performance, lowest privacy
- **Model Selection**: Choose models appropriate for workload requirements
- **Resource Allocation**: Ensure adequate resources for selected provider mode

**Section sources**
- [settings_routes.py:289-354](file://safe4ai-pilot/app/api/settings_routes.py#L289-L354)
- [settings_service.py:171-251](file://safe4ai-pilot/app/services/settings_service.py#L171-L251)