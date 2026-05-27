# Frontend Architecture

<cite>
**Referenced Files in This Document**
- [main.tsx](file://safe4ai-pilot/frontend/src/main.tsx)
- [App.tsx](file://safe4ai-pilot/frontend/src/App.tsx)
- [ChatPage.tsx](file://safe4ai-pilot/frontend/src/pages/ChatPage.tsx)
- [AdminLayout.tsx](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx)
- [useChat.ts](file://safe4ai-pilot/frontend/src/hooks/useChat.ts)
- [useAuth.ts](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts)
- [useSettings.ts](file://safe4ai-pilot/frontend/src/hooks/useSettings.ts)
- [ErrorBoundary.tsx](file://safe4ai-pilot/frontend/src/components/ErrorBoundary.tsx)
- [client.ts](file://safe4ai-pilot/frontend/src/api/client.ts)
- [chat.ts](file://safe4ai-pilot/frontend/src/api/chat.ts)
- [settings.ts](file://safe4ai-pilot/frontend/src/api/settings.ts)
- [tailwind.config.ts](file://safe4ai-pilot/frontend/tailwind.config.ts)
- [package.json](file://safe4ai-pilot/frontend/package.json)
- [vite.config.ts](file://safe4ai-pilot/frontend/vite.config.ts)
- [AnswerBlock.tsx](file://safe4ai-pilot/frontend/src/components/chat/AnswerBlock.tsx)
- [OverviewPage.tsx](file://safe4ai-pilot/frontend/src/pages/admin/OverviewPage.tsx)
- [ActivityPage.tsx](file://safe4ai-pilot/frontend/src/pages/admin/ActivityPage.tsx)
- [SettingsPage.tsx](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx)
- [SettingsPage.tsx](file://safe4ai-pilot/frontend/src/pages/SettingsPage.tsx)
</cite>

## Update Summary
**Changes Made**
- Added documentation for the new `useSettings()` React hook and its role in settings management
- Updated routing documentation to reflect the separation between admin and user settings pages
- Enhanced component analysis to include the new settings architecture
- Updated diagrams to show the new settings management flow

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
This document describes the frontend architecture of the React-based Private AI interface. It covers component hierarchy, state management with React hooks and React Query, routing with React Router, design system and styling via Tailwind CSS, API integration patterns, error boundaries, real-time chat streaming, admin dashboard layout and pages, responsive design, and the relationship between frontend components and backend endpoints.

## Project Structure
The frontend is a Vite-powered React application with TypeScript. It organizes code by feature and domain:
- Pages: top-level routes and page-level components
- Hooks: reusable state/logic abstractions
- Components: shared UI building blocks
- API: typed client and endpoint modules
- Styles: Tailwind configuration and design tokens

```mermaid
graph TB
subgraph "Entry"
M["main.tsx"]
A["App.tsx"]
end
subgraph "Routing"
R1["/chat"]
R2["/admin/*"]
R3["/login"]
R4["/settings"]
end
subgraph "Pages"
CP["ChatPage.tsx"]
AL["AdminLayout.tsx"]
OP["OverviewPage.tsx"]
AP["ActivityPage.tsx"]
ASP["Admin SettingsPage.tsx"]
USP["User SettingsPage.tsx"]
end
subgraph "Hooks"
HC["useChat.ts"]
HA["useAuth.ts"]
HS["useSettings.ts"]
end
subgraph "Components"
EB["ErrorBoundary.tsx"]
AB["AnswerBlock.tsx"]
end
subgraph "API"
AC["api/client.ts"]
AS["api/chat.ts"]
SS["api/settings.ts"]
end
subgraph "Styling"
TW["tailwind.config.ts"]
end
M --> A
A --> R1
A --> R2
A --> R3
A --> R4
R1 --> CP
R2 --> AL
AL --> OP
AL --> AP
AL --> ASP
R4 --> USP
CP --> HC
CP --> HA
CP --> AB
ASP --> HS
USP --> HA
CP --> AS
AS --> AC
SS --> AC
M --> EB
M --> TW
```

**Diagram sources**
- [main.tsx:1-33](file://safe4ai-pilot/frontend/src/main.tsx#L1-L33)
- [App.tsx:1-121](file://safe4ai-pilot/frontend/src/App.tsx#L1-L121)
- [ChatPage.tsx:29-191](file://safe4ai-pilot/frontend/src/pages/ChatPage.tsx#L29-L191)
- [AdminLayout.tsx:23-97](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L23-L97)
- [OverviewPage.tsx:43-213](file://safe4ai-pilot/frontend/src/pages/admin/OverviewPage.tsx#L43-L213)
- [ActivityPage.tsx:21-136](file://safe4ai-pilot/frontend/src/pages/admin/ActivityPage.tsx#L21-L136)
- [SettingsPage.tsx:46-352](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L46-L352)
- [SettingsPage.tsx:53-274](file://safe4ai-pilot/frontend/src/pages/SettingsPage.tsx#L53-L274)
- [useChat.ts:17-104](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L17-L104)
- [useAuth.ts:5-28](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts#L5-L28)
- [useSettings.ts:146-285](file://safe4ai-pilot/frontend/src/hooks/useSettings.ts#L146-L285)
- [ErrorBoundary.tsx:13-43](file://safe4ai-pilot/frontend/src/components/ErrorBoundary.tsx#L13-L43)
- [AnswerBlock.tsx:36-114](file://safe4ai-pilot/frontend/src/components/chat/AnswerBlock.tsx#L36-L114)
- [client.ts:1-20](file://safe4ai-pilot/frontend/src/api/client.ts#L1-L20)
- [chat.ts:21-76](file://safe4ai-pilot/frontend/src/api/chat.ts#L21-L76)
- [settings.ts:90-103](file://safe4ai-pilot/frontend/src/api/settings.ts#L90-L103)
- [tailwind.config.ts:1-44](file://safe4ai-pilot/frontend/tailwind.config.ts#L1-L44)

**Section sources**
- [main.tsx:1-33](file://safe4ai-pilot/frontend/src/main.tsx#L1-L33)
- [App.tsx:1-121](file://safe4ai-pilot/frontend/src/App.tsx#L1-L121)
- [package.json:1-32](file://safe4ai-pilot/frontend/package.json#L1-L32)
- [vite.config.ts:1-17](file://safe4ai-pilot/frontend/vite.config.ts#L1-L17)

## Core Components
- Application bootstrap initializes React Query, routing, and global error boundary.
- Routing enforces authentication and admin-only access via route guards.
- Chat page composes messaging UI, streaming pipeline, and citation drawer.
- Admin layout provides sidebar navigation and content area for admin pages.
- Shared hooks encapsulate chat state, authentication state, and settings management.
- Design system is driven by Tailwind tokens and consistent component primitives.

**Section sources**
- [main.tsx:9-23](file://safe4ai-pilot/frontend/src/main.tsx#L9-L23)
- [App.tsx:11-23](file://safe4ai-pilot/frontend/src/App.tsx#L11-L23)
- [ChatPage.tsx:29-191](file://safe4ai-pilot/frontend/src/pages/ChatPage.tsx#L29-L191)
- [AdminLayout.tsx:23-97](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L23-L97)
- [useChat.ts:17-104](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L17-L104)
- [useAuth.ts:5-28](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts#L5-L28)
- [useSettings.ts:146-285](file://safe4ai-pilot/frontend/src/hooks/useSettings.ts#L146-L285)
- [tailwind.config.ts:3-43](file://safe4ai-pilot/frontend/tailwind.config.ts#L3-L43)

## Architecture Overview
The frontend follows a layered architecture:
- Entry layer: Vite + React + React Router + React Query
- UI layer: Pages, Layouts, and Components
- State layer: Hooks for chat, auth, and settings
- API layer: Typed client and SSE streaming
- Styling layer: Tailwind tokens and theme

```mermaid
graph TB
E["Entry<br/>main.tsx"] --> Q["React Query Provider"]
E --> BR["BrowserRouter"]
E --> EB["ErrorBoundary"]
BR --> APP["App Routes<br/>App.tsx"]
APP --> CHAT["ChatPage"]
APP --> ADMIN["AdminLayout"]
APP --> USERSET["User SettingsPage"]
ADMIN --> OVER["OverviewPage"]
ADMIN --> ACT["ActivityPage"]
ADMIN --> ADMSET["Admin SettingsPage"]
CHAT --> HC["useChat"]
CHAT --> HA["useAuth"]
CHAT --> AB["AnswerBlock"]
USERSET --> HA
ADMSET --> HS["useSettings"]
HS --> SS["api/settings.ts"]
SS --> AC["api/client.ts"]
HC --> API["api/chat.ts"]
API --> AC
E --> TW["Tailwind Theme<br/>tailwind.config.ts"]
```

**Diagram sources**
- [main.tsx:13-23](file://safe4ai-pilot/frontend/src/main.tsx#L13-L23)
- [App.tsx:25-121](file://safe4ai-pilot/frontend/src/App.tsx#L25-L121)
- [ChatPage.tsx:29-191](file://safe4ai-pilot/frontend/src/pages/ChatPage.tsx#L29-L191)
- [AdminLayout.tsx:23-97](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L23-L97)
- [OverviewPage.tsx:43-213](file://safe4ai-pilot/frontend/src/pages/admin/OverviewPage.tsx#L43-L213)
- [ActivityPage.tsx:21-136](file://safe4ai-pilot/frontend/src/pages/admin/ActivityPage.tsx#L21-L136)
- [SettingsPage.tsx:46-352](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L46-L352)
- [SettingsPage.tsx:53-274](file://safe4ai-pilot/frontend/src/pages/SettingsPage.tsx#L53-L274)
- [useChat.ts:17-104](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L17-L104)
- [useAuth.ts:5-28](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts#L5-L28)
- [useSettings.ts:146-285](file://safe4ai-pilot/frontend/src/hooks/useSettings.ts#L146-L285)
- [AnswerBlock.tsx:36-114](file://safe4ai-pilot/frontend/src/components/chat/AnswerBlock.tsx#L36-L114)
- [chat.ts:21-76](file://safe4ai-pilot/frontend/src/api/chat.ts#L21-L76)
- [settings.ts:90-103](file://safe4ai-pilot/frontend/src/api/settings.ts#L90-L103)
- [client.ts:1-20](file://safe4ai-pilot/frontend/src/api/client.ts#L1-L20)
- [tailwind.config.ts:1-44](file://safe4ai-pilot/frontend/tailwind.config.ts#L1-L44)

## Detailed Component Analysis

### Routing and Guards
- Authentication guard redirects unauthenticated users to login.
- Admin guard restricts admin routes to admin users.
- Separate routes for admin settings (`/admin/settings`) and user settings (`/settings`).
- Catch-all route navigates to chat.

```mermaid
sequenceDiagram
participant U as "User"
participant BR as "BrowserRouter"
participant APP as "App.tsx"
participant GA as "RequireAuth"
participant GI as "RequireAdmin"
participant P as "Page"
U->>BR : Navigate to "/chat"
BR->>APP : Match route
APP->>GA : Wrap page
GA->>GA : Check useAuth()
alt Authenticated
GA->>P : Render ChatPage
else Not authenticated
GA->>APP : Redirect to "/login"
end
U->>BR : Navigate to "/admin/settings"
BR->>APP : Match route
APP->>GI : Wrap page
GI->>GI : Check useAuth()
alt Admin
GI->>P : Render Admin SettingsPage
else Not admin
GI->>APP : Redirect to "/chat"
end
U->>BR : Navigate to "/settings"
BR->>APP : Match route
APP->>GA : Wrap page
GA->>GA : Check useAuth()
alt Authenticated
GA->>P : Render User SettingsPage
else Not authenticated
GA->>APP : Redirect to "/login"
end
```

**Diagram sources**
- [App.tsx:11-23](file://safe4ai-pilot/frontend/src/App.tsx#L11-L23)
- [useAuth.ts:5-28](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts#L5-L28)

**Section sources**
- [App.tsx:11-23](file://safe4ai-pilot/frontend/src/App.tsx#L11-L23)
- [useAuth.ts:5-28](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts#L5-L28)

### Settings Management Architecture
**Updated** The settings system has been refactored to use a dedicated `useSettings()` hook that encapsulates all settings-related logic.

- `useSettings()` hook manages settings query, mutations, optimistic updates, and save queuing
- Admin SettingsPage uses the hook for centralized settings management
- User SettingsPage handles account-specific settings (password changes, profile info)
- Optimistic updates provide immediate UI feedback during saves
- Save queue prevents conflicts when multiple settings changes occur rapidly
- Automatic reindex warnings when embedding configurations change

```mermaid
sequenceDiagram
participant UI as "Admin SettingsPage"
participant HS as "useSettings Hook"
participant QC as "React Query Client"
participant API as "api/settings.ts"
participant AC as "api/client.ts"
UI->>HS : set(key, value)
HS->>HS : Create diff object
HS->>QC : Optimistically update cache
HS->>HS : Queue save operation
HS->>API : patchSettings(diff)
API->>AC : fetch("/settings", PATCH)
API-->>HS : Updated settings
HS->>QC : Update cache with real data
HS->>UI : Update UI state
```

**Diagram sources**
- [SettingsPage.tsx:46-352](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L46-L352)
- [useSettings.ts:146-285](file://safe4ai-pilot/frontend/src/hooks/useSettings.ts#L146-L285)
- [settings.ts:90-103](file://safe4ai-pilot/frontend/src/api/settings.ts#L90-L103)
- [client.ts:1-20](file://safe4ai-pilot/frontend/src/api/client.ts#L1-L20)

**Section sources**
- [useSettings.ts:146-285](file://safe4ai-pilot/frontend/src/hooks/useSettings.ts#L146-L285)
- [SettingsPage.tsx:46-352](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L46-L352)
- [settings.ts:90-103](file://safe4ai-pilot/frontend/src/api/settings.ts#L90-L103)

### Chat State Management and Streaming
- useChat manages messages, streaming steps, and lifecycle.
- sendMessage creates user and assistant messages, streams tokens, citations, and completion metadata.
- stop cancels the current stream via AbortController.
- rate submits feedback asynchronously.

```mermaid
sequenceDiagram
participant UI as "ChatPage"
participant HC as "useChat"
participant API as "api/chat.ts"
participant AC as "api/client.ts"
UI->>HC : sendMessage(question)
HC->>HC : Add user message
HC->>HC : Initialize steps, set streaming=true
HC->>HC : Create assistant message
HC->>API : streamChat(question, sessionId)
API->>AC : fetch("/chat/stream")
loop SSE stream
API-->>HC : "token" delta
HC->>HC : Append delta to assistant content
API-->>HC : "cite" source
HC->>HC : Append source to assistant sources
API-->>HC : "step" state
HC->>HC : Update step state
end
API-->>HC : "done" metadata
HC->>HC : Set trust, traceId, session
HC->>HC : Set streaming=false, reset steps
UI->>HC : rate(msgId, rating)
HC->>AC : submitFeedback(session, traceId, rating)
```

**Diagram sources**
- [ChatPage.tsx:39-46](file://safe4ai-pilot/frontend/src/pages/ChatPage.tsx#L39-L46)
- [useChat.ts:28-91](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L28-L91)
- [chat.ts:21-76](file://safe4ai-pilot/frontend/src/api/chat.ts#L21-L76)
- [client.ts:1-20](file://safe4ai-pilot/frontend/src/api/client.ts#L1-L20)

**Section sources**
- [useChat.ts:17-104](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L17-L104)
- [chat.ts:21-76](file://safe4ai-pilot/frontend/src/api/chat.ts#L21-L76)
- [ChatPage.tsx:39-46](file://safe4ai-pilot/frontend/src/pages/ChatPage.tsx#L39-L46)

### Admin Dashboard Layout and Pages
- AdminLayout renders sidebar navigation, active item highlighting, and content area.
- OverviewPage displays statistics, charts, and notable items with periodic refresh.
- ActivityPage shows a live audit stream with filtering and CSV export.
- SettingsPage provides comprehensive configuration management with automatic saving.

```mermaid
flowchart TD
Start(["Admin Route"]) --> AL["AdminLayout"]
AL --> Nav{"Active Nav Item"}
Nav --> |Overview| OP["OverviewPage"]
Nav --> |Activity| AP["ActivityPage"]
Nav --> |Documents| DP["DocumentsPage"]
Nav --> |Feedback| FP["FeedbackPage"]
Nav --> |Users| UP["UsersPage"]
Nav --> |Settings| SP["SettingsPage"]
SP --> HS["useSettings Hook"]
SP --> SS["Settings API"]
OP --> Stats["React Query: getStats"]
AP --> Stream["useAuditStream"]
DP --> List["DocumentRow"]
FP --> ListFB["FeedbackListItem"]
UP --> ListU["User Rows"]
```

**Diagram sources**
- [AdminLayout.tsx:10-17](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L10-L17)
- [AdminLayout.tsx:27-53](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L27-L53)
- [OverviewPage.tsx:43-48](file://safe4ai-pilot/frontend/src/pages/admin/OverviewPage.tsx#L43-L48)
- [ActivityPage.tsx:21-27](file://safe4ai-pilot/frontend/src/pages/admin/ActivityPage.tsx#L21-L27)
- [SettingsPage.tsx:46-352](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L46-L352)
- [useSettings.ts:146-285](file://safe4ai-pilot/frontend/src/hooks/useSettings.ts#L146-L285)

**Section sources**
- [AdminLayout.tsx:23-97](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L23-L97)
- [OverviewPage.tsx:43-213](file://safe4ai-pilot/frontend/src/pages/admin/OverviewPage.tsx#L43-L213)
- [ActivityPage.tsx:21-136](file://safe4ai-pilot/frontend/src/pages/admin/ActivityPage.tsx#L21-L136)

### Design System and Styling
- Tailwind tokens define colors, typography, spacing, shadows, and radii.
- Components use semantic class names and tokens for consistent appearance.
- Responsive layout uses flexbox and grid with constrained widths and scroll regions.

```mermaid
graph LR
TW["tailwind.config.ts"] --> Tokens["Design Tokens"]
Tokens --> Colors["Colors"]
Tokens --> Fonts["Font Families"]
Tokens --> Radius["Border Radius"]
Tokens --> Shadow["Shadows"]
Colors --> C1["ink/paper/surface/line"]
Colors --> C2["text/slate/accent/success/warn/danger"]
Fonts --> F1["sans/mono/serif"]
AnswerBlock["AnswerBlock.tsx"] --> Classes["Semantic Classes"]
Classes --> Tokens
```

**Diagram sources**
- [tailwind.config.ts:3-43](file://safe4ai-pilot/frontend/tailwind.config.ts#L3-L43)
- [AnswerBlock.tsx:44-112](file://safe4ai-pilot/frontend/src/components/chat/AnswerBlock.tsx#L44-L112)

**Section sources**
- [tailwind.config.ts:1-44](file://safe4ai-pilot/frontend/tailwind.config.ts#L1-L44)
- [AnswerBlock.tsx:36-114](file://safe4ai-pilot/frontend/src/components/chat/AnswerBlock.tsx#L36-L114)

### API Integration Layer
- api/client.ts centralizes fetch with credentials and JSON parsing.
- api/chat.ts implements SSE streaming for chat responses.
- api/settings.ts provides typed settings management with optimistic updates.
- Vite proxy forwards routes to backend host.

```mermaid
sequenceDiagram
participant FE as "Frontend"
participant VC as "Vite Proxy"
participant BE as "Backend"
participant AC as "api/client.ts"
participant AT as "api/chat.ts"
participant AS as "api/settings.ts"
FE->>VC : POST /chat/stream
VC->>BE : Forward to VITE_API_URL
BE-->>FE : SSE stream
FE->>AT : streamChat(...)
AT->>AC : fetch("/chat/stream")
AC-->>AT : Response Reader
AT-->>FE : Async events (step/token/cite/done/error)
FE->>VC : PATCH /settings
VC->>BE : Forward to VITE_API_URL
BE-->>FE : Updated settings
FE->>AS : patchSettings(...)
AS->>AC : fetch("/settings", PATCH)
AC-->>AS : Updated settings
AS-->>FE : Settings response
```

**Diagram sources**
- [vite.config.ts:8-14](file://safe4ai-pilot/frontend/vite.config.ts#L8-L14)
- [client.ts:1-20](file://safe4ai-pilot/frontend/src/api/client.ts#L1-L20)
- [chat.ts:21-76](file://safe4ai-pilot/frontend/src/api/chat.ts#L21-L76)
- [settings.ts:90-103](file://safe4ai-pilot/frontend/src/api/settings.ts#L90-L103)

**Section sources**
- [client.ts:1-20](file://safe4ai-pilot/frontend/src/api/client.ts#L1-L20)
- [chat.ts:21-76](file://safe4ai-pilot/frontend/src/api/chat.ts#L21-L76)
- [settings.ts:90-103](file://safe4ai-pilot/frontend/src/api/settings.ts#L90-L103)
- [vite.config.ts:1-17](file://safe4ai-pilot/frontend/vite.config.ts#L1-L17)

### Error Boundary Implementation
- ErrorBoundary catches rendering errors and presents a friendly recovery UI.
- Logs error and stack to console for diagnostics.

```mermaid
flowchart TD
Try["Render Children"] --> |No Error| OK["Continue Rendering"]
Try --> |Error| Catch["getDerivedStateFromError"]
Catch --> Show["Show Recovery UI"]
Show --> Reload["User clicks Refresh"]
Reload --> Reset["Window reload"]
```

**Diagram sources**
- [ErrorBoundary.tsx:13-43](file://safe4ai-pilot/frontend/src/components/ErrorBoundary.tsx#L13-L43)

**Section sources**
- [ErrorBoundary.tsx:13-43](file://safe4ai-pilot/frontend/src/components/ErrorBoundary.tsx#L13-L43)

## Dependency Analysis
- Runtime dependencies include React, React Router, React Query, and UI icons.
- Dev dependencies include Vite, Tailwind, PostCSS, and TypeScript.
- Vite plugin chain enables React fast-refresh and TypeScript support.
- Proxy configuration routes API traffic to backend during development.

```mermaid
graph TB
Pkg["package.json"]
D1["@tanstack/react-query"]
D2["react-router-dom"]
D3["lucide-react"]
D4["react/react-dom"]
Dev1["@vitejs/plugin-react"]
Dev2["tailwindcss/postcss/typescript"]
Pkg --> D1
Pkg --> D2
Pkg --> D3
Pkg --> D4
Pkg --> Dev1
Pkg --> Dev2
```

**Diagram sources**
- [package.json:11-30](file://safe4ai-pilot/frontend/package.json#L11-L30)

**Section sources**
- [package.json:1-32](file://safe4ai-pilot/frontend/package.json#L1-L32)
- [vite.config.ts:1-17](file://safe4ai-pilot/frontend/vite.config.ts#L1-L17)

## Performance Considerations
- React Query caching: global staleTime configured to reduce redundant requests.
- Streaming rendering: incremental updates to messages and steps improve perceived performance.
- Optimistic updates: immediate UI feedback during settings saves reduces perceived latency.
- Save queuing: prevents conflicts when multiple settings changes occur rapidly.
- Minimal re-renders: callbacks memoized with useCallback keep components stable.
- Lazy loading: code-splitting via dynamic imports can be introduced for heavy admin pages.
- Image and asset optimization: leverage Vite's bundling and Tailwind purging.
- Accessibility: ensure focus management, ARIA attributes, and keyboard navigation in interactive components.

## Troubleshooting Guide
- Authentication issues: verify cookie credentials and session validity; check sign-out flow clears React Query cache.
- Chat streaming failures: confirm SSE endpoint availability and network connectivity; inspect AbortController usage and error events.
- Admin access denied: ensure user role is admin; route guards redirect unauthorized users.
- Settings save failures: check network connectivity and server response; use retry mechanism for unsaved changes.
- Optimistic update conflicts: wait for save queue to complete before making conflicting changes.
- Styling inconsistencies: validate Tailwind token usage and CSS order; rebuild after theme changes.
- Build/runtime errors: use ErrorBoundary recovery; inspect console logs for derived error state.

**Section sources**
- [useAuth.ts:14-18](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts#L14-L18)
- [useChat.ts:24-26](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L24-L26)
- [useSettings.ts:165-200](file://safe4ai-pilot/frontend/src/hooks/useSettings.ts#L165-L200)
- [ErrorBoundary.tsx:20-22](file://safe4ai-pilot/frontend/src/components/ErrorBoundary.tsx#L20-L22)

## Conclusion
The Private AI frontend employs a clean separation of concerns: routing and guards manage access, React Query handles data, hooks encapsulate state, and Tailwind provides a cohesive design system. Real-time chat uses SSE for streaming, while admin pages present dashboards and activity feeds. The new settings management architecture provides centralized, optimistic updates with automatic conflict resolution. The architecture supports scalability, maintainability, and a strong UX through thoughtful component composition and performance-conscious patterns.

## Appendices

### Component Interaction Diagram: Chat Data Flow
```mermaid
graph TB
UI["ChatPage.tsx"] --> HC["useChat.ts"]
HC --> API["api/chat.ts"]
API --> AC["api/client.ts"]
UI --> AB["AnswerBlock.tsx"]
UI --> HA["useAuth.ts"]
```

**Diagram sources**
- [ChatPage.tsx:29-191](file://safe4ai-pilot/frontend/src/pages/ChatPage.tsx#L29-L191)
- [useChat.ts:17-104](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L17-L104)
- [chat.ts:21-76](file://safe4ai-pilot/frontend/src/api/chat.ts#L21-L76)
- [client.ts:1-20](file://safe4ai-pilot/frontend/src/api/client.ts#L1-L20)
- [AnswerBlock.tsx:36-114](file://safe4ai-pilot/frontend/src/components/chat/AnswerBlock.tsx#L36-L114)
- [useAuth.ts:5-28](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts#L5-L28)

### Component Interaction Diagram: Settings Management Flow
```mermaid
graph TB
UI["Admin SettingsPage.tsx"] --> HS["useSettings.ts"]
HS --> QC["React Query Client"]
HS --> API["api/settings.ts"]
API --> AC["api/client.ts"]
UI --> HA["useAuth.ts"]
```

**Diagram sources**
- [SettingsPage.tsx:46-352](file://safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx#L46-L352)
- [useSettings.ts:146-285](file://safe4ai-pilot/frontend/src/hooks/useSettings.ts#L146-L285)
- [settings.ts:90-103](file://safe4ai-pilot/frontend/src/api/settings.ts#L90-L103)
- [client.ts:1-20](file://safe4ai-pilot/frontend/src/api/client.ts#L1-L20)
- [useAuth.ts:5-28](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts#L5-L28)