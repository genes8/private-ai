# Admin Dashboard

<cite>
**Referenced Files in This Document**
- [AdminLayout.tsx](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx)
- [OverviewPage.tsx](file://safe4ai-pilot/frontend/src/pages/admin/OverviewPage.tsx)
- [DocumentsPage.tsx](file://safe4ai-pilot/frontend/src/pages/admin/DocumentsPage.tsx)
- [ActivityPage.tsx](file://safe4ai-pilot/frontend/src/pages/admin/ActivityPage.tsx)
- [FeedbackPage.tsx](file://safe4ai-pilot/frontend/src/pages/admin/FeedbackPage.tsx)
- [UsersPage.tsx](file://safe4ai-pilot/frontend/src/pages/admin/UsersPage.tsx)
- [SettingsPage.tsx](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx)
- [App.tsx](file://safe4ai-pilot/frontend/src/App.tsx)
- [AdminAudit.tsx](file://design/components/AdminAudit.tsx)
- [AdminDocs.tsx](file://design/components/AdminDocs.tsx)
- [AdminFeedback.tsx](file://design/components/AdminFeedback.tsx)
- [AdminStats.tsx](file://design/components/AdminStats.tsx)
- [AdminShell.tsx](file://design/components/AdminShell.tsx)
- [Sparkline.tsx](file://safe4ai-pilot/frontend/src/components/admin/Sparkline.tsx)
- [DocumentRow.tsx](file://safe4ai-pilot/frontend/src/components/admin/DocumentRow.tsx)
- [FeedbackListItem.tsx](file://safe4ai-pilot/frontend/src/components/admin/FeedbackListItem.tsx)
- [ActivityEvent.tsx](file://safe4ai-pilot/frontend/src/components/admin/ActivityEvent.tsx)
- [useDocuments.ts](file://safe4ai-pilot/frontend/src/hooks/useDocuments.ts)
- [useAuditStream.ts](file://safe4ai-pilot/frontend/src/hooks/useAuditStream.ts)
- [useAuth.ts](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts)
- [stats.ts](file://safe4ai-pilot/frontend/src/api/stats.ts)
- [documents.ts](file://safe4ai-pilot/frontend/src/api/documents.ts)
- [feedback.ts](file://safe4ai-pilot/frontend/src/api/feedback.ts)
- [audit.ts](file://safe4ai-pilot/frontend/src/api/audit.ts)
- [settings.ts](file://safe4ai-pilot/frontend/src/api/settings.ts)
- [client.ts](file://safe4ai-pilot/frontend/src/api/client.ts)
- [admin_routes.py](file://safe4ai-pilot/app/api/admin_routes.py)
- [oidc.py](file://safe4ai-pilot/app/auth/oidc.py)
- [input_guard.py](file://safe4ai-pilot/app/security/input_guard.py)
- [test_admin.py](file://safe4ai-pilot/tests/test_admin.py)
- [test_oidc.py](file://safe4ai-pilot/tests/test_oidc.py)
- [test_runtime_config.py](file://safe4ai-pilot/tests/test_runtime_config.py)
</cite>

## Update Summary
**Changes Made**
- Enhanced OverviewPage with real 14-day sparkline charts using new timeseries endpoint
- Added document inspector panel with metadata, chunk previews, and ingestion history
- Updated ActivityPage with kind-based filtering and badge counts
- Improved data visualization with enhanced chart series mapping
- Expanded document management with detailed inspection capabilities

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Security Considerations](#security-considerations)
10. [Practical Extensions](#practical-extensions)
11. [Conclusion](#conclusion)

## Introduction
This document describes the enhanced admin dashboard system for the private·ai platform. The system now includes comprehensive administrative interfaces covering monitoring, document management, activity auditing, feedback administration, user management, and system configuration. The dashboard features six core pages: OverviewPage for system monitoring, DocumentsPage for document management, ActivityPage for audit trails, FeedbackPage for user feedback analysis, UsersPage for team administration, and SettingsPage for system configuration. The system leverages a consistent admin layout with navigation patterns, real-time data visualization through enhanced Sparkline charts, and robust API integration for all administrative functions.

**Updated** Enhanced with improved authentication flows including OIDC integration, better security measures with blocked terms filtering, and updated frontend hooks/components supporting modern authentication and content filtering systems.

## Project Structure
The admin dashboard has been significantly enhanced with new components and pages. The system now includes both frontend-based admin pages and design system components that provide comprehensive administrative capabilities, along with enhanced security and authentication features.

```mermaid
graph TB
subgraph "Enhanced Admin Pages"
AL["AdminLayout.tsx"]
OP["OverviewPage.tsx"]
DP["DocumentsPage.tsx"]
AP["ActivityPage.tsx"]
FP["FeedbackPage.tsx"]
UP["UsersPage.tsx"]
SP["SettingsPage.tsx"]
end
subgraph "Application Routing"
APP["App.tsx"]
end
subgraph "Design System Components"
DA["AdminAudit.tsx"]
DD["AdminDocs.tsx"]
DF["AdminFeedback.tsx"]
DS["AdminStats.tsx"]
AS["AdminShell.tsx"]
end
subgraph "Components"
SL["Sparkline.tsx"]
DR["DocumentRow.tsx"]
FLI["FeedbackListItem.tsx"]
AE["ActivityEvent.tsx"]
end
subgraph "Hooks & APIs"
UDM["useDocuments.ts"]
UAS["useAuditStream.ts"]
UA["useAuth.ts"]
CLI["client.ts"]
ST["stats.ts"]
DOC["documents.ts"]
FB["feedback.ts"]
AT["audit.ts"]
SET["settings.ts"]
end
subgraph "Security & Authentication"
OIDC["OIDC Authentication"]
IG["Input Guard"]
BT["Blocked Terms"]
end
AL --> SP
AL --> UP
AL --> FP
AL --> AP
AL --> DP
AL --> OP
APP --> AL
SP --> SET
UP --> CLI
FP --> FB
AP --> AT
DP --> DOC
OP --> ST
SP --> OIDC
SP --> IG
IG --> BT
```

**Diagram sources**
- [AdminLayout.tsx:12-19](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L12-L19)
- [SettingsPage.tsx:186-184](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L186-L184)
- [App.tsx:50-57](file://safe4ai-pilot/frontend/src/App.tsx#L50-L57)
- [AdminAudit.tsx:5-278](file://design/components/AdminAudit.tsx#L5-L278)
- [AdminDocs.tsx:5-238](file://design/components/AdminDocs.tsx#L5-L238)
- [AdminFeedback.tsx:5-215](file://design/components/AdminFeedback.tsx#L5-L215)
- [AdminStats.tsx:5-258](file://design/components/AdminStats.tsx#L5-L258)
- [AdminShell.tsx:12-20](file://design/components/AdminShell.tsx#L12-L20)
- [oidc.py:78-149](file://safe4ai-pilot/app/auth/oidc.py#L78-L149)
- [input_guard.py:39-71](file://safe4ai-pilot/app/security/input_guard.py#L39-L71)

**Section sources**
- [AdminLayout.tsx:10-19](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L10-L19)
- [SettingsPage.tsx:176-184](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L176-L184)
- [App.tsx:50-57](file://safe4ai-pilot/frontend/src/App.tsx#L50-L57)

## Core Components
The admin dashboard now encompasses six comprehensive pages with distinct responsibilities, enhanced by seamless navigation between admin and chat interfaces and strengthened security measures:

**AdminLayout**: Enhanced with Settings navigation, improved feedback badge display, and the new 'Back to chat' navigation option
**OverviewPage**: System monitoring and analytics with real-time metrics and enhanced 14-day sparkline visualization
**DocumentsPage**: Document lifecycle management with upload, indexing, inspection, and detailed metadata viewing
**ActivityPage**: Comprehensive audit trail with filtering, export capabilities, and kind-based badge counts
**FeedbackPage**: User feedback analysis with rating categorization and trace details
**UsersPage**: Team management with invitation, status control, and role assignment
**SettingsPage**: Complete system configuration with redesigned mode selector cards, OIDC authentication settings, and blocked terms management

**Enhanced SettingsPage Features**:
- **Mode Selector Cards**: Visual cards for Local, Hybrid, and Cloud provider modes
- **Context-Specific Model Dropdowns**: Intelligent model selection based on provider type
- **Custom Model Management**: Support for external provider model names
- **Real-time Provider Validation**: Connectivity testing with immediate feedback
- **Intelligent Model Options**: Dynamic model lists based on current configuration
- **OIDC Authentication Settings**: Client ID, client secret, redirect URI, and domain restrictions
- **Blocked Terms Management**: Configurable content filtering and prompt injection prevention
- **Security Configuration**: Enhanced authentication and access control settings

**Enhanced Security Features**:
- **Input Guard**: Comprehensive input validation with blocked terms filtering
- **Prompt Injection Detection**: Advanced pattern matching for security threats
- **SSRF Protection**: Secure server-side request forgery prevention in OIDC flows
- **Domain Restriction**: Email domain validation for OIDC authentication
- **Auto-Provisioning**: Controlled user creation after successful OIDC authentication

**Enhanced Components**:
- Sparkline: Enhanced trend visualization with 14-day real-time data
- DocumentRow: Document status and action management with inspection capabilities
- FeedbackListItem: Feedback item presentation
- ActivityEvent: Audit event display with kind-based filtering

**Enhanced Navigation Features**:
- **Back to chat**: Dedicated navigation option in admin sidebar for seamless interface switching
- **Improved feedback integration**: Dynamic negative feedback badge display
- **Active route highlighting**: Visual indicators for current navigation state
- **Enhanced user session management**: Integrated logout functionality

**Section sources**
- [AdminLayout.tsx:12-19](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L12-L19)
- [SettingsPage.tsx:176-378](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L176-L378)
- [AdminAudit.tsx:52-278](file://design/components/AdminAudit.tsx#L52-L278)
- [AdminDocs.tsx:27-238](file://design/components/AdminDocs.tsx#L27-238)
- [AdminFeedback.tsx:29-215](file://design/components/AdminFeedback.tsx#L29-215)
- [AdminStats.tsx:44-258](file://design/components/AdminStats.tsx#L44-L258)
- [oidc.py:78-149](file://safe4ai-pilot/app/auth/oidc.py#L78-L149)
- [input_guard.py:39-71](file://safe4ai-pilot/app/security/input_guard.py#L39-L71)

## Architecture Overview
The enhanced admin architecture follows a modular pattern with clear separation of concerns across six specialized pages, each leveraging shared components and APIs. The new 'Back to chat' navigation creates seamless integration between admin and chat interfaces, while enhanced security measures protect against various threats.

```mermaid
sequenceDiagram
participant Admin as "Admin User"
participant Layout as "AdminLayout"
participant Chat as "Chat Interface"
participant Router as "React Router"
Admin->>Layout : Click "Back to chat"
Layout->>Router : Navigate to "/chat"
Router->>Chat : Render ChatPage
Chat-->>Admin : Display chat interface
Note over Admin,Chat : Seamless navigation between admin and chat
```

**Diagram sources**
- [AdminLayout.tsx:81-89](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L81-L89)
- [App.tsx:41-48](file://safe4ai-pilot/frontend/src/App.tsx#L41-L48)

## Detailed Component Analysis

### Enhanced AdminLayout with Back-to-Chat Navigation
The AdminLayout now includes comprehensive navigation for all six admin pages with improved feedback integration, active route detection, and the new 'Back to chat' navigation option.

**Navigation Structure**:
- Overview: System monitoring and analytics with 14-day sparklines
- Documents: Document management, indexing, and detailed inspection
- Activity: Audit trail with kind-based filtering and badge counts
- Feedback: User feedback analysis with rating categorization
- Users: Team management and administration
- Settings: System configuration and controls
- **Back to chat**: Seamless navigation back to main chat interface

**Enhanced Features**:
- Dynamic feedback badge display showing negative feedback count
- Active route highlighting with visual indicators
- Improved index health monitoring
- Enhanced user session management
- **New**: Dedicated 'Back to chat' navigation option with arrow icon
- **New**: Consistent navigation pattern across admin and chat interfaces

```mermaid
flowchart TD
Start(["AdminLayout Render"]) --> GetRoute["Parse URL path"]
GetRoute --> FindNav["Match against NAV array"]
FindNav --> SetActive["Set active navigation item"]
SetActive --> RenderNav["Render 6-item navigation"]
RenderNav --> FeedbackBadge["Display negative feedback count"]
FeedbackBadge --> BackToChat["Render 'Back to chat' option"]
BackToChat --> ChatNav["Navigate to '/chat'"]
ChatNav --> End(["Complete"])
```

**Diagram sources**
- [AdminLayout.tsx:36-72](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L36-L72)
- [AdminLayout.tsx:81-89](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L81-L89)

**Section sources**
- [AdminLayout.tsx:12-19](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L12-L19)
- [AdminLayout.tsx:25-36](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L25-L36)

### Application Routing Integration
The application routing system provides seamless navigation between admin and chat interfaces through the RequireAdmin wrapper and dedicated routes.

**Routing Structure**:
- `/chat`: Main chat interface accessible to authenticated users
- `/admin`: Admin interface restricted to admin users
- `/admin/*`: All admin sub-pages with automatic redirection to overview

**Enhanced Features**:
- **RequireAdmin wrapper**: Redirects non-admin users to chat interface
- **Automatic admin redirection**: Redirects admin users to `/admin/overview`
- **Consistent navigation patterns**: Both admin and chat interfaces use similar navigation approaches

```mermaid
flowchart TD
User["User Access"] --> CheckAuth["Check Authentication"]
CheckAuth --> IsAdmin{"Is Admin?"}
IsAdmin --> |Yes| AdminRoute["/admin/*"]
IsAdmin --> |No| ChatRoute["/chat"]
AdminRoute --> AutoRedirect["Auto redirect to /admin/overview"]
ChatRoute --> ChatInterface["Render Chat Interface"]
AutoRedirect --> OverviewPage["Render OverviewPage"]
```

**Diagram sources**
- [App.tsx:29-34](file://safe4ai-pilot/frontend/src/App.tsx#L29-L34)
- [App.tsx:50-57](file://safe4ai-pilot/frontend/src/App.tsx#L50-L57)

**Section sources**
- [App.tsx:29-34](file://safe4ai-pilot/frontend/src/App.tsx#L29-L34)
- [App.tsx:50-57](file://safe4ai-pilot/frontend/src/App.tsx#L50-L57)

### Enhanced OverviewPage - Real-Time 14-Day Monitoring
The OverviewPage has been significantly enhanced with real-time 14-day sparkline visualization using a new timeseries endpoint, providing comprehensive system monitoring and analytics.

**Enhanced Monitoring Features**:
- **14-Day Timeseries Data**: Real-time queries, unique users, and cost metrics
- **Enhanced Sparkline Charts**: Interactive visualization with configurable time ranges
- **Multi-Metric Dashboard**: Queries, unique users, and cost USD tracking
- **Responsive Chart Layout**: Adaptive sizing with consistent styling
- **Real-Time Data Updates**: Automatic refresh with 60-second intervals

**Timeseries Data Processing**:
- **Data Structure**: Array of objects containing daily metrics
- **Series Mapping**: Direct mapping of timeseries data to chart series
- **Date Handling**: Proper timestamp conversion and date formatting
- **Missing Data**: Graceful handling of incomplete 14-day periods

**Chart Configuration**:
- **Queries Chart**: Line chart showing daily query volumes
- **Unique Users Chart**: Area chart displaying user engagement trends
- **Cost Chart**: Bar chart illustrating daily spending patterns
- **Interactive Elements**: Hover effects and tooltip displays

```mermaid
flowchart TD
OverviewPage["OverviewPage"] --> Query["useQuery: stats.timeseries"]
Query --> TimeseriesData["Fetch 14-day timeseries data"]
TimeseriesData --> ProcessData["Process daily metrics"]
ProcessData --> Chart1["Queries Sparkline Chart"]
ProcessData --> Chart2["Unique Users Sparkline Chart"]
ProcessData --> Chart3["Cost USD Sparkline Chart"]
Chart1 --> Series1["Map series: timeseries.queries"]
Chart2 --> Series2["Map series: timeseries.uniqueUsers"]
Chart3 --> Series3["Map series: timeseries.costUsd"]
Series1 --> RenderCharts["Render Enhanced Charts"]
Series2 --> RenderCharts
Series3 --> RenderCharts
RenderCharts --> UpdateUI["Update Dashboard UI"]
```

**Diagram sources**
- [OverviewPage.tsx:32-33](file://safe4ai-pilot/frontend/src/pages/admin/OverviewPage.tsx#L32-L33)
- [OverviewPage.tsx:119-129](file://safe4ai-pilot/frontend/src/pages/admin/OverviewPage.tsx#L119-L129)

**Section sources**
- [OverviewPage.tsx:25-40](file://safe4ai-pilot/frontend/src/pages/admin/OverviewPage.tsx#L25-L40)
- [OverviewPage.tsx:110-135](file://safe4ai-pilot/frontend/src/pages/admin/OverviewPage.tsx#L110-L135)

### Enhanced DocumentsPage - Document Inspector Panel
The DocumentsPage now features a comprehensive document inspector panel that provides detailed metadata, chunk previews, and ingestion history for individual documents.

**Enhanced Document Inspection Features**:
- **Metadata Display**: Document name, type, size, chunks, status, and processing date
- **Chunk Previews**: Visual representation of document chunking and retrieval patterns
- **Ingestion History**: Complete processing timeline with status updates
- **Status Indicators**: Color-coded status chips (indexed, embedding, failed, skipped)
- **Progress Tracking**: Real-time progress bars for ongoing operations

**Document Status Management**:
- **Status Chips**: Interactive status indicators with hover details
- **Action Buttons**: Re-index, delete, and inspect document actions
- **Batch Operations**: Multiple document selection and bulk actions
- **Search and Filter**: Enhanced document discovery with status filtering

**Enhanced User Experience**:
- **Responsive Layout**: Adaptive grid system for document listings
- **Drag-and-Drop Upload**: Intuitive file upload interface
- **Real-Time Updates**: Automatic refresh of document statuses
- **Error Handling**: Comprehensive error messages and recovery options

```mermaid
flowchart TD
DocumentsPage["DocumentsPage"] --> InspectorPanel["Document Inspector Panel"]
InspectorPanel --> Metadata["Document Metadata"]
Metadata --> FileName["File Name & Type"]
Metadata --> FileSize["File Size"]
Metadata --> ChunkCount["Chunk Count"]
Metadata --> ProcessingStatus["Processing Status"]
InspectorPanel --> ChunkPreviews["Chunk Previews"]
ChunkPreviews --> TopChunks["Top Retrieved Chunks"]
ChunkPreviews --> ChunkDistribution["Chunk Distribution"]
InspectorPanel --> IngestionHistory["Ingestion History"]
IngestionHistory --> ProcessingTimeline["Processing Timeline"]
IngestionHistory --> StatusUpdates["Status Updates"]
```

**Diagram sources**
- [DocumentsPage.tsx:150-200](file://safe4ai-pilot/frontend/src/pages/admin/DocumentsPage.tsx#L150-L200)
- [AdminDocs.tsx:150-238](file://design/components/AdminDocs.tsx#L150-L238)

**Section sources**
- [DocumentsPage.tsx:120-220](file://safe4ai-pilot/frontend/src/pages/admin/DocumentsPage.tsx#L120-L220)
- [AdminDocs.tsx:41-238](file://design/components/AdminDocs.tsx#L41-L238)

### Enhanced ActivityPage - Kind-Based Filtering and Badge Counts
The ActivityPage has been updated with advanced filtering capabilities and badge counts, providing more granular control over audit trail analysis.

**Enhanced Activity Filtering Features**:
- **Kind-Based Filtering**: Filter by event type (queries, uploads, feedback, auth)
- **Badge Counts**: Visual indicators showing event counts by kind
- **Multi-Level Filtering**: Combine kind, user, and date range filters
- **Live Updates**: Real-time activity monitoring with status indicators

**Activity Event Categorization**:
- **Query Events**: User query activities with latency and model details
- **Upload Events**: Document upload and processing activities
- **Feedback Events**: User feedback and rating activities
- **Auth Events**: Authentication and authorization activities
- **System Events**: Platform maintenance and system activities

**Enhanced User Interface**:
- **Filter Rail**: Persistent filter sidebar with expand/collapse functionality
- **Timeline Visualization**: Chronological event display with visual indicators
- **Export Functionality**: Download filtered activity reports
- **Search Integration**: Quick search within filtered results

```mermaid
flowchart TD
ActivityPage["ActivityPage"] --> FilterRail["Enhanced Filter Rail"]
FilterRail --> KindFilter["Kind Filter with Badges"]
KindFilter --> QueryBadge["Query Badge Count"]
KindFilter --> UploadBadge["Upload Badge Count"]
KindFilter --> FeedbackBadge["Feedback Badge Count"]
KindFilter --> AuthBadge["Auth Badge Count"]
ActivityPage --> ActivityStream["Enhanced Activity Stream"]
ActivityStream --> Timeline["Timeline Visualization"]
Timeline --> EventNodes["Event Nodes with Kind Indicators"]
EventNodes --> QueryEvents["Query Events"]
EventNodes --> UploadEvents["Upload Events"]
EventNodes --> FeedbackEvents["Feedback Events"]
EventNodes --> AuthEvents["Auth Events"]
EventNodes --> FallbackEvents["Fallback Events"]
```

**Diagram sources**
- [ActivityPage.tsx:1-50](file://safe4ai-pilot/frontend/src/pages/admin/ActivityPage.tsx#L1-L50)
- [AdminAudit.tsx:68-278](file://design/components/AdminAudit.tsx#L68-L278)

**Section sources**
- [ActivityPage.tsx:1-80](file://safe4ai-pilot/frontend/src/pages/admin/ActivityPage.tsx#L1-L80)
- [AdminAudit.tsx:5-278](file://design/components/AdminAudit.tsx#L5-L278)

### SettingsPage - Redesigned Configuration Management
The SettingsPage provides complete system configuration with redesigned mode selector cards and context-specific model management, now enhanced with OIDC authentication and blocked terms filtering capabilities.

**Redesigned Mode Selector System**:
- **Visual Mode Cards**: Three distinct provider mode cards with icons and badges
- **Intelligent Context Switching**: Automatic model dropdown population based on mode
- **Context-Specific Guidance**: Mode-appropriate hints and warnings
- **Real-time Validation**: Immediate feedback during configuration changes

**Enhanced Security Configuration**:
- **OIDC Authentication Settings**: Client ID, client secret, redirect URI, and domain restrictions
- **Blocked Terms Management**: Configurable content filtering and prompt injection prevention
- **Security Configuration**: Enhanced authentication and access control settings

**Configuration Sections**:
- **Models**: Generation, fallback, and embedding model selection with version control
- **Retrieval**: Chunk management, scoring thresholds, and processing parameters
- **Sources**: Document source connections (S3, Google Drive, watch folders)
- **Security**: Authentication, session management, audit retention, and content filtering
- **Cost**: Spend monitoring, daily/monthly ceilings, and budget controls
- **Provider**: Enhanced provider configuration with mode selector cards

**Enhanced Features**:
- **Mode Selector Cards**: Local, Hybrid, and Cloud provider modes with visual indicators
- **Context-Specific Model Dropdowns**: Intelligent model selection based on provider type
- **Custom Model Management**: Support for external provider model names
- **Real-time Configuration Validation**: Immediate feedback on configuration changes
- **Scroll-snap Layout**: Left-rail navigation with section-based scrolling
- **Automatic Change Propagation**: Configuration changes applied to all users within 30 seconds
- **Comprehensive Audit Logging**: All configuration changes tracked and logged
- **OIDC Integration**: Secure single sign-on configuration and management
- **Content Filtering**: Blocked terms and prompt injection prevention

```mermaid
flowchart TD
SettingsPage["SettingsPage"] --> Query["useQuery: getSettings()"]
Query --> Parse["Parse AppSettings interface"]
Parse --> RenderSections["Render 6 configuration sections"]
subgraph "Enhanced Provider Configuration"
ModeCards["Mode Selector Cards"] --> LocalMode["Local Mode Card"]
ModeCards --> HybridMode["Hybrid Mode Card"]
ModeCards --> CloudMode["Cloud Mode Card"]
LocalMode --> LocalModels["Ollama Model Dropdowns"]
HybridMode --> CloudModels["Provider Model Dropdowns"]
CloudMode --> CloudModels2["Provider Model Dropdowns"]
CustomModels["Custom Model Manager"] --> AddCustom["Add Custom Models"]
AddCustom --> SaveCustom["Save Custom Models"]
end
subgraph "Enhanced Security Configuration"
OIDCConfig["OIDC Authentication"] --> ClientID["Client ID Input"]
OIDCConfig --> ClientSecret["Client Secret Input"]
OIDCConfig --> RedirectURI["Redirect URI Input"]
OIDCConfig --> AllowedDomains["Allowed Domains Input"]
OIDCConfig --> AutoProvision["Auto-Provision Toggle"]
BlockedTerms["Blocked Terms"] --> TermsInput["Terms Input Field"]
BlockedTerms --> TermsList["Terms List Display"]
end
RenderSections --> Mutations["useMutation: patchSettings()"]
Mutations --> Success["Update UI with new settings"]
```

**Diagram sources**
- [SettingsPage.tsx:189-193](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L189-L193)
- [settings.ts:56-62](file://safe4ai-pilot/frontend/src/api/settings.ts#L56-L62)
- [SettingsPage.tsx:455-486](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L455-L486)
- [SettingsPage.tsx:474-483](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L474-L483)

**Section sources**
- [SettingsPage.tsx:176-378](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L176-L378)
- [settings.ts:3-54](file://safe4ai-pilot/frontend/src/api/settings.ts#L3-L54)

### Enhanced UsersPage - Advanced Team Management
The UsersPage provides comprehensive team management with invitation workflows, status control, and role assignment.

**User Management Features**:
- User invitation with automatic password generation
- Role-based access control (admin, pilot_user)
- User status management (active, inactive)
- Document scope assignment per user
- Audit trail integration for all user changes

**Advanced Functionality**:
- Real-time user filtering and search
- Bulk status updates with confirmation dialogs
- Invitation modal with domain validation
- Audit footer showing retention policies
- Responsive design with hover states

```mermaid
sequenceDiagram
participant Admin as "Admin User"
participant UsersPage as "UsersPage"
participant Modal as "Invite Modal"
participant API as "Admin Users API"
Admin->>UsersPage : Click "Invite teammate"
UsersPage->>Modal : Open invitation dialog
Modal->>Modal : Validate email/domain
Modal->>API : POST /admin/users
API-->>Modal : User created with temp password
Modal-->>UsersPage : Display temporary password
UsersPage->>UsersPage : Invalidate user list cache
UsersPage-->>Admin : Updated user table
```

**Diagram sources**
- [UsersPage.tsx:277-299](file://safe4ai-pilot/frontend/src/pages/admin/UsersPage.tsx#L277-L299)
- [UsersPage.tsx:439-443](file://safe4ai-pilot/frontend/src/pages/admin/UsersPage.tsx#L439-L443)

**Section sources**
- [UsersPage.tsx:271-459](file://safe4ai-pilot/frontend/src/pages/admin/UsersPage.tsx#L271-L459)

### Redesigned Provider Configuration System

#### Mode Selector Cards Implementation
The SettingsPage now features redesigned mode selector cards that provide intuitive visual selection for provider modes.

**Mode Cards Configuration**:
- **Local Mode**: Server icon, "Local only" description, no API key requirement
- **Hybrid Mode**: Lightning bolt icon, "Hybrid" description with "Recommended" badge, cloud chat + local embeddings
- **Cloud Mode**: Cloud icon, "Fully cloud" description, requires external API access

**Card Interaction Logic**:
- Visual selection with border highlighting and background color change
- Badge display for recommended mode
- immediate provider mode change without form submission
- Contextual model dropdown population based on selected mode

```mermaid
flowchart TD
ModeSelector["Mode Selector Cards"] --> LocalCard["Local Card"]
ModeSelector --> HybridCard["Hybrid Card"]
ModeSelector --> CloudCard["Cloud Card"]
LocalCard --> LocalModels["Ollama Model Dropdowns"]
HybridCard --> CloudModels["Provider Model Dropdowns"]
CloudCard --> CloudModels2["Provider Model Dropdowns"]
CustomModels["Custom Model Manager"] --> AddCustom["Add Custom Models"]
AddCustom --> SaveCustom["Save Custom Models"]
```

**Diagram sources**
- [SettingsPage.tsx:627-664](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L627-L664)
- [SettingsPage.tsx:667-739](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L667-L739)

#### Context-Specific Model Dropdowns
The system now implements intelligent model dropdowns that adapt based on the selected provider mode.

**Model Selection Logic**:
- **Local Mode**: Uses Ollama model list exclusively
- **Hybrid Mode**: Uses provider models for chat, Ollama for embeddings
- **Cloud Mode**: Uses provider models for all components
- **Dynamic Options**: Combines available models with current selections

**Model Dropdown Features**:
- Intelligent model option merging with current selections
- Placeholder text indicating model availability
- Automatic fallback to compatible models
- Support for custom model names in provider modes

```mermaid
flowchart TD
ModelDropdown["Context-Specific Model Dropdown"] --> LocalMode["Local Mode"]
ModelDropdown --> HybridMode["Hybrid Mode"]
ModelDropdown --> CloudMode["Cloud Mode"]
LocalMode --> OllamaModels["Ollama Models Only"]
HybridMode --> ProviderModels["Provider Models + Ollama Embeddings"]
CloudMode --> AllProviderModels["All Provider Models"]
OllamaModels --> MergeOptions["Merge with Current Selections"]
ProviderModels --> MergeOptions
AllProviderModels --> MergeOptions
MergeOptions --> DisplayOptions["Display Available Options"]
```

**Diagram sources**
- [SettingsPage.tsx:498-505](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L498-L505)
- [SettingsPage.tsx:236-252](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L236-L252)

#### Custom Model Management
The enhanced SettingsPage includes comprehensive custom model management for external providers.

**Custom Model Features**:
- **Model Name Input**: Text field for adding custom model identifiers
- **Model List Display**: Visual chips for managing custom models
- **Dynamic Validation**: Model identifier validation and deduplication
- **Persistence**: Automatic saving of custom models to configuration

**Custom Model Workflow**:
- Input validation for model identifier format
- duplicate prevention in model list
- Individual model removal with confirmation
- Batch persistence to server configuration

```mermaid
flowchart TD
CustomModelManager["Custom Model Manager"] --> InputField["Model Name Input"]
InputField --> ValidateInput["Validate Model Identifier"]
ValidateInput --> AddToList["Add to Custom Models List"]
AddToList --> DisplayChips["Display Model Chips"]
DisplayChips --> RemoveModel["Remove Individual Model"]
RemoveModel --> UpdateList["Update Model List"]
UpdateList --> SaveModels["Save to Server"]
SaveModels --> Success["Custom Models Saved"]
```

**Diagram sources**
- [SettingsPage.tsx:574-625](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L574-L625)
- [settings.ts:98-103](file://safe4ai-pilot/frontend/src/api/settings.ts#L98-L103)

#### Real-time Provider Validation and Connectivity Testing
The system now provides comprehensive real-time validation for provider configurations with immediate feedback.

**Validation Features**:
- **Provider Type Validation**: Ensures valid provider selection
- **API Key Requirements**: Enforces API key presence for external providers
- **Connectivity Testing**: Validates provider accessibility
- **Model Compatibility**: Checks model availability and compatibility

**Testing Mechanisms**:
- **Ollama Testing**: Validates local service accessibility
- **API Testing**: Tests external provider connectivity
- **Model Availability**: Verifies model existence and accessibility

```mermaid
sequenceDiagram
participant User as "Admin User"
participant SettingsPage as "SettingsPage"
participant TestEndpoint as "Provider Test Endpoint"
participant Provider as "External Provider"
User->>SettingsPage : Configure Provider
SettingsPage->>TestEndpoint : POST /settings/provider/test
TestEndpoint->>Provider : Validate Connection
Provider-->>TestEndpoint : Connection Result
TestEndpoint-->>SettingsPage : Validation Response
SettingsPage-->>User : Show Validation Status
```

**Diagram sources**
- [admin_routes.py:1330-1380](file://safe4ai-pilot/app/api/admin_routes.py#L1330-L1380)
- [test_admin.py:902-951](file://safe4ai-pilot/tests/test_admin.py#L902-L951)

**Section sources**
- [SettingsPage.tsx:517-559](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L517-L559)
- [admin_routes.py:1095-1137](file://safe4ai-pilot/app/api/admin_routes.py#L1095-L1137)
- [test_admin.py:902-951](file://safe4ai-pilot/tests/test_admin.py#L902-L951)

### Enhanced Security Features

#### OIDC Authentication Integration
The SettingsPage now includes comprehensive OIDC authentication configuration with secure integration and domain restriction capabilities.

**OIDC Configuration Features**:
- **Client ID Management**: Secure client ID input with validation
- **Client Secret Handling**: Protected client secret storage and transmission
- **Redirect URI Configuration**: Callback URL management for authentication flows
- **Domain Restrictions**: Email domain validation for user authentication
- **Auto-Provisioning**: Automatic user creation after successful OIDC login
- **SSRF Protection**: Secure server-side request forgery prevention

**Authentication Flow**:
- Discovery of OIDC endpoints via well-known configuration
- Authorization URL construction with state parameter
- Token exchange for user information retrieval
- Domain validation and user provisioning

```mermaid
sequenceDiagram
participant User as "End User"
participant OIDC as "OIDC Provider"
participant Backend as "Private-AI Backend"
participant Database as "User Database"
User->>Backend : Request OIDC Login
Backend->>OIDC : Discover Configuration
OIDC-->>Backend : Return Endpoints
Backend->>OIDC : Redirect with Authorization Code
OIDC-->>Backend : Return Authorization Code
Backend->>OIDC : Exchange Code for Tokens
OIDC-->>Backend : Return Access Token
Backend->>OIDC : Fetch User Info
OIDC-->>Backend : Return User Information
Backend->>Database : Validate Domain & Provision User
Database-->>Backend : User Created/Found
Backend-->>User : Redirect to Application
```

**Diagram sources**
- [oidc.py:105-149](file://safe4ai-pilot/app/auth/oidc.py#L105-L149)
- [SettingsPage.tsx:455-486](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L455-L486)

#### Blocked Terms Filtering and Input Guard
The system implements comprehensive input filtering to prevent prompt injection attacks and enforce content policies.

**Input Guard Features**:
- **HTML Entity Decoding**: Proper handling of encoded HTML content
- **Unicode Normalization**: NFKC normalization for homoglyph prevention
- **HTML Tag Removal**: Stripping of potentially malicious HTML tags
- **Length Validation**: Maximum character limits for input safety
- **Blocked Terms Detection**: Configurable term filtering with case-insensitive matching
- **Injection Pattern Detection**: Advanced pattern matching for prompt injection attempts

**Security Measures**:
- **SSRF Protection**: Secure URL validation and pinned transport for OIDC endpoints
- **Domain Restriction**: Email domain validation for OIDC authentication
- **Auto-Provisioning Control**: Controlled user creation after successful authentication
- **Content Filtering**: Real-time input validation and blocking

```mermaid
flowchart TD
InputGuard["Input Guard System"] --> Decode["Decode HTML Entities"]
Decode --> Normalize["Normalize Unicode"]
Normalize --> CleanHTML["Remove HTML Tags"]
CleanHTML --> CleanControl["Strip Control Characters"]
CleanControl --> CollapseWS["Collapse Whitespace"]
CollapseWS --> LengthCheck["Length Validation"]
LengthCheck --> BlockedTerms["Blocked Terms Check"]
BlockedTerms --> InjectionPatterns["Injection Pattern Check"]
InjectionPatterns --> Result["Return Guard Result"]
```

**Diagram sources**
- [input_guard.py:47-71](file://safe4ai-pilot/app/security/input_guard.py#L47-L71)
- [oidc.py:78-149](file://safe4ai-pilot/app/auth/oidc.py#L78-L149)

**Section sources**
- [SettingsPage.tsx:455-486](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L455-L486)
- [oidc.py:78-149](file://safe4ai-pilot/app/auth/oidc.py#L78-L149)
- [input_guard.py:39-71](file://safe4ai-pilot/app/security/input_guard.py#L39-L71)

### New Design Components

#### AdminAudit - Detailed Activity Monitoring
The AdminAudit component provides comprehensive activity monitoring with timeline visualization and filtering capabilities.

**Key Features**:
- Timeline-based activity stream with visual indicators
- Multi-level filtering (kind, user, date range)
- Live activity monitoring with status indicators
- Comprehensive event categorization (queries, uploads, feedback, auth)
- Export functionality for audit compliance

```mermaid
flowchart TD
AdminAudit["AdminAudit Component"] --> Shell["AdminShell Wrapper"]
Shell --> FilterRail["Filter Rail"]
FilterRail --> KindFilter["Kind Filter"]
FilterRail --> UserFilter["User Filter"]
FilterRail --> RangeFilter["Date Range Filter"]
AdminAudit --> Stream["Activity Stream"]
Stream --> Timeline["Timeline Visualization"]
Timeline --> EventNodes["Event Nodes"]
EventNodes --> QueryEvents["Query Events"]
EventNodes --> UploadEvents["Upload Events"]
EventNodes --> FeedbackEvents["Feedback Events"]
EventNodes --> AuthEvents["Auth Events"]
EventNodes --> FallbackEvents["Fallback Events"]
```

**Diagram sources**
- [AdminAudit.tsx:68-278](file://design/components/AdminAudit.tsx#L68-L278)

**Section sources**
- [AdminAudit.tsx:5-278](file://design/components/AdminAudit.tsx#L5-L278)

#### AdminDocs - Document Inventory Management
The AdminDocs component offers comprehensive document inventory management with status tracking and inspection capabilities.

**Document Management Features**:
- Document listing with status indicators (indexed, embedding, failed, skipped)
- Drag-and-drop upload interface
- Batch operations (reindex, delete)
- Detailed document inspection with indexing statistics
- Retrieval analytics and usage tracking

```mermaid
flowchart TD
AdminDocs["AdminDocs Component"] --> Shell["AdminShell Wrapper"]
Shell --> DropZone["Upload Drop Zone"]
DropZone --> FileUpload["File Upload Interface"]
AdminDocs --> Table["Document Table"]
Table --> StatusChips["Status Chips"]
StatusChips --> Indexed["Indexed Documents"]
StatusChips --> Embedding["Embedding Status"]
StatusChips --> Failed["Failed Documents"]
StatusChips --> Skipped["Skipped Documents"]
AdminDocs --> Inspector["Document Inspector"]
Inspector --> IndexingStats["Indexing Statistics"]
Inspector --> RetrievalAnalytics["Retrieval Analytics"]
Inspector --> TopChunks["Top Retrieved Chunks"]
```

**Diagram sources**
- [AdminDocs.tsx:41-238](file://design/components/AdminDocs.tsx#L41-L238)

**Section sources**
- [AdminDocs.tsx:5-238](file://design/components/AdminDocs.tsx#L5-L238)

#### AdminFeedback - Feedback Analysis
The AdminFeedback component provides detailed feedback analysis with trace information and resolution workflows.

**Feedback Analysis Features**:
- List-detail interface for feedback items
- Rating categorization (thumbs up/down)
- User and role identification
- Trace information with latency and model details
- Resolution suggestions and reindex recommendations

```mermaid
flowchart TD
AdminFeedback["AdminFeedback Component"] --> Shell["AdminShell Wrapper"]
Shell --> List["Feedback List"]
List --> ItemSelection["Item Selection"]
ItemSelection --> RatingFilter["Rating Filter"]
AdminFeedback --> Detail["Feedback Detail"]
Detail --> ReporterInfo["Reporter Information"]
Detail --> Question["Question Analysis"]
Detail --> Answer["Answer Details"]
Detail --> TraceInfo["Trace Information"]
Detail --> Resolution["Resolution Suggestions"]
```

**Diagram sources**
- [AdminFeedback.tsx:39-215](file://design/components/AdminFeedback.tsx#L39-L215)

**Section sources**
- [AdminFeedback.tsx:5-215](file://design/components/AdminFeedback.tsx#L5-L215)

#### AdminStats - System Statistics and Reporting
The AdminStats component delivers comprehensive system statistics with interactive visualizations and trend analysis.

**Statistics Features**:
- Interactive sparkline charts for trend visualization
- Latency analysis with p50/p95 metrics
- Traffic volume and user engagement metrics
- Quality assessment with helpfulness ratios
- Cost analysis and spending trends
- Notable events and actionable insights

```mermaid
flowchart TD
AdminStats["AdminStats Component"] --> Shell["AdminShell Wrapper"]
Shell --> Headline["Executive Summary"]
Headline --> KeyMetrics["Key Metrics Display"]
AdminStats --> Charts["Interactive Charts"]
Charts --> LatencyChart["Latency Chart"]
Charts --> TrafficChart["Traffic Chart"]
Charts --> QualityChart["Quality Chart"]
Charts --> CostChart["Cost Chart"]
AdminStats --> Insights["Actionable Insights"]
Insights --> FallbackAlerts["Fallback Alerts"]
Insights --> FeedbackAlerts["Feedback Alerts"]
Insights --> IndexingAlerts["Indexing Alerts"]
```

**Diagram sources**
- [AdminStats.tsx:53-258](file://design/components/AdminStats.tsx#L53-L258)

**Section sources**
- [AdminStats.tsx:5-258](file://design/components/AdminStats.tsx#L5-L258)

#### AdminShell - Legacy Design Component
The AdminShell component serves as a legacy design component that provides a comprehensive admin shell structure with navigation and content areas.

**Key Features**:
- Fixed 212px wide navigation rail
- Six main navigation items (Overview, Documents, Activity, Feedback, Users, Settings)
- Static index health indicator with "Indexing healthy" status
- User profile section with avatar and logout functionality
- Responsive grid layout with sidebar and main content areas

**Note**: This component appears to be part of the design system and may be superseded by the modern AdminLayout implementation.

```mermaid
flowchart TD
AdminShell["AdminShell Component"] --> Rail["212px Navigation Rail"]
Rail --> NavItems["Six Navigation Items"]
NavItems --> Overview["Overview"]
NavItems --> Documents["Documents"]
NavItems --> Activity["Activity"]
NavItems --> Feedback["Feedback"]
NavItems --> Users["Users"]
NavItems --> Settings["Settings"]
AdminShell --> Main["Main Content Area"]
Main --> Header["Header with Title/Subtitle"]
Main --> Children["Child Components"]
AdminShell --> Footer["Footer with User Profile"]
Footer --> HealthCard["Static Index Health Card"]
HealthCard --> HealthStatus["Indexing Healthy"]
```

**Diagram sources**
- [AdminShell.tsx:12-20](file://design/components/AdminShell.tsx#L12-L20)
- [AdminShell.tsx:66-78](file://design/components/AdminShell.tsx#L66-L78)

**Section sources**
- [AdminShell.tsx:1-119](file://design/components/AdminShell.tsx#L1-L119)

## Dependency Analysis
The enhanced admin system maintains clean dependency relationships with additional components and APIs supporting the expanded functionality, including the new navigation integration and enhanced security features.

```mermaid
graph LR
AL["AdminLayout.tsx"] --> APP["App.tsx"]
AL --> SP["SettingsPage.tsx"]
AL --> UP["UsersPage.tsx"]
AL --> FP["FeedbackPage.tsx"]
AL --> AP["ActivityPage.tsx"]
AL --> DP["DocumentsPage.tsx"]
AL --> OP["OverviewPage.tsx"]
APP --> AL
SP --> SET["settings.ts"]
UP --> CLI["client.ts"]
FP --> FB["feedback.ts"]
AP --> AT["audit.ts"]
DP --> DOC["documents.ts"]
OP --> ST["stats.ts"]
DA["AdminAudit.tsx"] --> AL
DD["AdminDocs.tsx"] --> AL
DF["AdminFeedback.tsx"] --> AL
DS["AdminStats.tsx"] --> AL
AS["AdminShell.tsx"] --> AL
UDM["useDocuments.ts"] --> DOC
UAS["useAuditStream.ts"] --> AT
UA["useAuth.ts"] --> AL
AR["admin_routes.py"] --> SP
AR --> UP
AR --> FP
AR --> AP
AR --> DP
AR --> OP
OIDC["oidc.py"] --> SP
IG["input_guard.py"] --> SP
```

**Diagram sources**
- [AdminLayout.tsx:12-19](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L12-L19)
- [SettingsPage.tsx:16-17](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L16-L17)
- [UsersPage.tsx:14-17](file://safe4ai-pilot/frontend/src/pages/admin/UsersPage.tsx#L14-L17)
- [App.tsx:50-57](file://safe4ai-pilot/frontend/src/App.tsx#L50-L57)
- [admin_routes.py:56-56](file://safe4ai-pilot/app/api/admin_routes.py#L56-L56)
- [oidc.py:78-149](file://safe4ai-pilot/app/auth/oidc.py#L78-L149)
- [input_guard.py:39-71](file://safe4ai-pilot/app/security/input_guard.py#L39-L71)

**Section sources**
- [AdminLayout.tsx:12-19](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L12-L19)
- [SettingsPage.tsx:16-17](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L16-L17)
- [UsersPage.tsx:14-17](file://safe4ai-pilot/frontend/src/pages/admin/UsersPage.tsx#L14-L17)
- [App.tsx:50-57](file://safe4ai-pilot/frontend/src/App.tsx#L50-L57)
- [admin_routes.py:56-56](file://safe4ai-pilot/app/api/admin_routes.py#L56-L56)
- [oidc.py:78-149](file://safe4ai-pilot/app/auth/oidc.py#L78-L149)
- [input_guard.py:39-71](file://safe4ai-pilot/app/security/input_guard.py#L39-L71)

## Performance Considerations
The enhanced admin system implements optimized data fetching strategies and efficient rendering patterns, including the new navigation features and enhanced security measures.

**Optimized Refresh Patterns**:
- SettingsPage: Configuration changes propagate within 30 seconds
- UsersPage: User list refresh every 60 seconds with caching
- FeedbackPage: Negative feedback count updates every 60 seconds
- ActivityPage: Audit logs refresh every 30 seconds with enhanced filtering
- DocumentsPage: Document status polling every 10 seconds with inspector panel
- OverviewPage: Enhanced 14-day sparkline data refresh every 60 seconds
- **New**: Mode selector cards with instant visual feedback
- **New**: Context-specific model dropdowns with cached model lists
- **New**: Back-to-chat navigation with instant routing
- **New**: OIDC configuration validation with debounced requests
- **New**: Blocked terms filtering with efficient pattern matching
- **New**: Document inspector panel with lazy loading for large documents
- **New**: Activity page kind-based filtering with real-time badge updates

**Efficient Rendering**:
- Virtualized scrolling for large datasets
- Lazy loading for detailed views
- Optimized SVG rendering for enhanced charts
- Debounced search and filtering
- Efficient state management with React Query
- **New**: Instant mode card selection without form submission
- **New**: Context-aware model dropdown rendering
- **New**: Seamless navigation without page reloads
- **New**: Real-time security validation feedback
- **New**: Responsive chart rendering with adaptive sizing

**Network Optimization**:
- Shared API client with authentication
- Request deduplication
- Efficient pagination for audit logs
- Conditional revalidation based on user actions
- **New**: Provider connectivity testing with timeout handling
- **New**: Custom model validation with debounce
- **New**: Client-side navigation optimization
- **New**: OIDC endpoint discovery with caching
- **New**: Blocked terms validation with batch processing
- **New**: Timeseries data caching with 14-day rolling window

## Troubleshooting Guide
Enhanced troubleshooting procedures for the expanded admin functionality, including navigation-related issues and new security features.

**Settings Management Issues**:
- Configuration changes not applying: Verify settings API connectivity and authentication
- Model switching failures: Check embedding model availability and reindex requirements
- Source connection issues: Validate S3/GDrive credentials and permissions
- **New**: Mode selector card interaction failures: Check browser compatibility and JavaScript
- **New**: Context-specific model dropdown issues: Verify provider connectivity and model availability
- **New**: OIDC configuration validation errors: Check client credentials and domain restrictions
- **New**: Blocked terms filtering not working: Verify regex patterns and term formatting

**Navigation Issues**:
- **Back to chat not working**: Verify React Router configuration and navigation links
- **Admin navigation failures**: Check RequireAdmin wrapper and authentication state
- **Route redirection problems**: Validate App.tsx routing configuration
- **Navigation state issues**: Ensure proper useLocation hook usage

**Provider Configuration Problems**:
- **API Key Validation Errors**: Verify API key format and provider type compatibility
- **Connectivity Failures**: Check network connectivity and base URL configuration
- **Model Availability Issues**: Ensure selected models are available in the provider
- **Provider Type Mismatch**: Validate provider type selection and configuration
- **Mode Card Selection Issues**: Check for JavaScript errors in console

**User Management Problems**:
- Invitation failures: Verify email domain restrictions and SMTP configuration
- Status update errors: Check user role permissions and audit trail requirements
- Scope assignment issues: Validate document access permissions

**Audit and Monitoring Issues**:
- Missing audit events: Verify audit retention settings and storage configuration
- Performance degradation: Check database indexes and query optimization
- Export failures: Validate file system permissions and storage quotas
- **New**: Activity page filtering not working: Check kind-based filter configuration
- **New**: Badge counts not updating: Verify real-time data streaming

**Document Management Issues**:
- Upload failures: Check file size limits and supported formats
- Indexing errors: Verify document preprocessing and embedding model availability
- Search performance: Monitor Elasticsearch indices and query optimization
- **New**: Document inspector panel not loading: Check document metadata availability
- **New**: Chunk preview errors: Verify document chunking and retrieval configuration

**OverviewPage Issues**:
- **Timeseries data not loading**: Check stats API endpoint and authentication
- **Sparkline charts not rendering**: Verify chart library integration and data formatting
- **14-day period errors**: Check date calculations and timezone handling

**Security and Authentication Issues**:
- **OIDC Login Failures**: Verify issuer URL, client credentials, and redirect URI configuration
- **Domain Restriction Errors**: Check allowed domains list format and email verification
- **Auto-Provisioning Issues**: Verify user creation permissions and database connectivity
- **Input Guard False Positives**: Adjust blocked terms list and injection pattern rules
- **SSRF Protection Errors**: Check network connectivity and URL validation configuration

**Section sources**
- [SettingsPage.tsx:360-366](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L360-L366)
- [UsersPage.tsx:430-436](file://safe4ai-pilot/frontend/src/pages/admin/UsersPage.tsx#L430-L436)
- [AdminLayout.tsx:81-89](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L81-L89)
- [App.tsx:29-34](file://safe4ai-pilot/frontend/src/App.tsx#L29-L34)
- [admin_routes.py:1074-1080](file://safe4ai-pilot/app/api/admin_routes.py#L1074-L1080)
- [oidc.py:78-149](file://safe4ai-pilot/app/auth/oidc.py#L78-L149)
- [input_guard.py:39-71](file://safe4ai-pilot/app/security/input_guard.py#L39-L71)

## Security Considerations
The enhanced admin system implements comprehensive security measures across all administrative functions, including navigation security and advanced authentication and content filtering capabilities.

**Access Control**:
- Role-based permissions (admin, pilot_user)
- Session management with configurable expiration
- Two-factor authentication support
- IP whitelisting and device trust
- **New**: Navigation security with RequireAdmin wrapper preventing unauthorized access
- **New**: OIDC domain restriction for email-based access control
- **New**: Auto-provisioning control for user creation management

**Data Protection**:
- Audit logging for all administrative actions
- Encrypted storage for sensitive configuration data
- PII redaction in audit trails
- Secure password generation and transmission
- **New**: API key masking and secure handling in UI
- **New**: Provider configuration validation without exposing secrets
- **New**: Secure navigation between admin and chat interfaces
- **New**: Blocked terms configuration with secure storage

**API Security**:
- JWT token authentication with refresh cycles
- CORS configuration for admin domain
- Rate limiting for administrative endpoints
- Input validation and sanitization
- **New**: Provider API key validation and secure transmission
- **New**: Custom model validation and sanitization
- **New**: Navigation endpoint security validation
- **New**: OIDC endpoint discovery with SSRF protection
- **New**: Blocked terms validation with regex sanitization
- **New**: Timeseries data endpoint with appropriate access controls

**Compliance**:
- Audit retention policies (30-365 days configurable)
- Data residency and export capabilities
- Security incident response procedures
- Regular security assessments and penetration testing

**Enhanced Provider Security**:
- **New**: Secure API key handling with masking
- **New**: Real-time validation without exposing secrets
- **New**: Provider connectivity testing with controlled requests
- **New**: Configuration change audit logging
- **New**: Custom model identifier validation
- **New**: Navigation security enforcement
- **New**: OIDC authentication with domain restriction
- **New**: Input guard with blocked terms filtering
- **New**: Prompt injection detection and prevention
- **New**: Enhanced timeseries data access controls

## Practical Extensions
The enhanced admin system provides numerous opportunities for customization and extension, including navigation enhancements and advanced security features.

**Adding New Administrative Pages**:
- Create new page component following AdminLayout pattern
- Implement dedicated API endpoints for data management
- Add navigation items to AdminLayout NAV array
- Integrate with existing authentication and authorization

**Enhancing Navigation Features**:
- **New**: Add additional navigation shortcuts between admin and chat
- **New**: Implement breadcrumb navigation for complex admin workflows
- **New**: Add keyboard shortcuts for quick navigation
- **New**: Create navigation history and favorites functionality

**Enhancing Configuration Management**:
- Add new configuration categories to SettingsPage
- Implement configuration validation and rollback
- Add import/export functionality for settings
- Create configuration templates and presets
- **New**: Extend mode selector cards with additional provider types
- **New**: Implement advanced model validation and compatibility checking
- **New**: Add OIDC provider configuration for multiple identity providers
- **New**: Implement advanced blocked terms management with regex support

**Extending Monitoring Capabilities**:
- Add custom metrics and KPIs to OverviewPage
- Implement real-time alerting and notifications
- Create custom dashboard widgets with enhanced Sparkline integration
- Add historical trend analysis and forecasting
- **New**: Extend timeseries data with additional metrics (uptime, error rates)
- **New**: Implement custom chart types for specialized monitoring needs

**Improving User Experience**:
- Implement user preference management
- Add bulk operations for user management
- Create user onboarding workflows
- Add team collaboration features
- **New**: Enhance navigation UX with progress indicators and tooltips
- **New**: Implement user session management with activity monitoring
- **New**: Add document search and filtering capabilities

**Enhancing Provider Management**:
- **New**: Add support for additional provider types (Azure, Anthropic, etc.)
- **New**: Implement provider health monitoring and status indicators
- **New**: Add provider-specific configuration templates
- **New**: Implement provider failover and redundancy mechanisms
- **New**: Extend custom model management with validation rules
- **New**: Implement advanced OIDC configuration management
- **New**: Add security policy configuration for content filtering

**Advanced Security Features**:
- **New**: Implement advanced threat detection and prevention
- **New**: Add security audit trail for all security-related actions
- **New**: Implement rate limiting for authentication attempts
- **New**: Add IP-based access control and monitoring
- **New**: Implement advanced input validation and sanitization
- **New**: Add document access logging and monitoring

## Conclusion
The enhanced admin dashboard provides comprehensive administrative capabilities through six specialized pages, each designed for specific management tasks. The system combines modern React patterns with robust backend integration, offering real-time monitoring, detailed analytics, and complete configuration management. With enhanced security measures, efficient data management, and extensible architecture, the admin system supports both current operational needs and future growth requirements. The modular design ensures maintainability while the comprehensive feature set addresses all aspects of system administration and monitoring.

**Updated** The addition of the 'Back to chat' navigation option creates seamless navigation between the admin interface and the main chat interface, improving user workflow efficiency and reducing context switching overhead. The enhanced admin layout with improved navigation patterns and real-time data visualization provides administrators with reliable and actionable insights into system performance and document indexing status. The integration of OIDC authentication and blocked terms filtering significantly enhances security while maintaining usability. The new 14-day sparkline charts, document inspector panel, and enhanced activity filtering represent significant improvements in monitoring and analysis capabilities. These enhancements demonstrate the system's commitment to providing both powerful administrative capabilities and strong security protections.