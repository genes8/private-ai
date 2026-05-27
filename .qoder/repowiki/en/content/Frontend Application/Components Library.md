# Components Library

<cite>
**Referenced Files in This Document**
- [Button.tsx](file://safe4ai-pilot/frontend/src/components/Button.tsx)
- [Chip.tsx](file://safe4ai-pilot/frontend/src/components/Chip.tsx)
- [Avatar.tsx](file://safe4ai-pilot/frontend/src/components/Avatar.tsx)
- [AdminLayout.tsx](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx)
- [useAuth.ts](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts)
- [useChat.ts](file://safe4ai-pilot/frontend/src/hooks/useChat.ts)
- [useDocuments.ts](file://safe4ai-pilot/frontend/src/hooks/useDocuments.ts)
- [useAuditStream.ts](file://safe4ai-pilot/frontend/src/hooks/useAuditStream.ts)
- [App.tsx](file://safe4ai-pilot/frontend/src/App.tsx)
- [main.tsx](file://safe4ai-pilot/frontend/src/main.tsx)
- [tokens.css](file://safe4ai-pilot/frontend/src/styles/tokens.css)
- [tailwind.config.ts](file://safe4ai-pilot/frontend/tailwind.config.ts)
- [index.css](file://safe4ai-pilot/frontend/src/index.css)
- [package.json](file://safe4ai-pilot/frontend/package.json)
</cite>

## Update Summary
**Changes Made**
- Added documentation for Avatar component usage in navigation contexts
- Enhanced AdminLayout documentation to show Avatar integration in sidebar
- Updated component integration patterns to reflect Avatar usage in navigation components
- Expanded navigation component documentation with concrete examples

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Navigation Components](#navigation-components)
7. [Dependency Analysis](#dependency-analysis)
8. [Performance Considerations](#performance-considerations)
9. [Troubleshooting Guide](#troubleshooting-guide)
10. [Conclusion](#conclusion)
11. [Appendices](#appendices)

## Introduction
This document describes the React component library and utility hooks that power the Private AI web frontend. It focuses on reusable UI components (Button, Chip, Avatar) and shared hooks (useAuth, useChat, useDocuments, useAuditStream). It explains component organization, props, styling via design tokens and Tailwind, integration patterns, and TypeScript usage. Practical guidance is included for creating new components, extending existing ones, and building custom hooks aligned with the design system.

**Updated** Enhanced documentation to include Avatar component usage patterns in navigation contexts and AdminLayout integration.

## Project Structure
The frontend is organized around a small set of core UI components and hooks, with a cohesive design system built on CSS custom properties and Tailwind configuration. The application bootstraps a React Query provider, routes protected pages, and applies global styles.

```mermaid
graph TB
subgraph "Bootstrapping"
MAIN["main.tsx"]
APP["App.tsx"]
end
subgraph "Core UI"
BTN["Button.tsx"]
CHIP["Chip.tsx"]
AVA["Avatar.tsx"]
END
subgraph "Navigation"
ADMIN_LAYOUT["AdminLayout.tsx"]
END
subgraph "Hooks"
H_AUTH["useAuth.ts"]
H_CHAT["useChat.ts"]
H_DOCS["useDocuments.ts"]
H_AUDIT["useAuditStream.ts"]
end
subgraph "Design System"
TOKENS["styles/tokens.css"]
TW_CFG["tailwind.config.ts"]
INDEX_CSS["index.css"]
end
MAIN --> APP
APP --> H_AUTH
APP --> H_CHAT
APP --> H_DOCS
APP --> H_AUDIT
BTN --> TOKENS
CHIP --> TOKENS
AVA --> TOKENS
ADMIN_LAYOUT --> AVA
BTN -. uses .-> TW_CFG
CHIP -. uses .-> TW_CFG
AVA -. uses .-> TW_CFG
ADMIN_LAYOUT -. uses .-> TOKENS
INDEX_CSS --> TOKENS
INDEX_CSS --> TW_CFG
```

**Diagram sources**
- [main.tsx:1-24](file://safe4ai-pilot/frontend/src/main.tsx#L1-L24)
- [App.tsx:1-100](file://safe4ai-pilot/frontend/src/App.tsx#L1-L100)
- [Button.tsx:1-56](file://safe4ai-pilot/frontend/src/components/Button.tsx#L1-L56)
- [Chip.tsx:1-32](file://safe4ai-pilot/frontend/src/components/Chip.tsx#L1-L32)
- [Avatar.tsx:1-15](file://safe4ai-pilot/frontend/src/components/Avatar.tsx#L1-L15)
- [AdminLayout.tsx:1-144](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L1-L144)
- [useAuth.ts:1-36](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts#L1-L36)
- [useChat.ts:1-106](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L1-L106)
- [useDocuments.ts:1-61](file://safe4ai-pilot/frontend/src/hooks/useDocuments.ts#L1-L61)
- [useAuditStream.ts:1-17](file://safe4ai-pilot/frontend/src/hooks/useAuditStream.ts#L1-L17)
- [tokens.css:1-69](file://safe4ai-pilot/frontend/src/styles/tokens.css#L1-L69)
- [tailwind.config.ts:1-44](file://safe4ai-pilot/frontend/tailwind.config.ts#L1-L44)
- [index.css:1-16](file://safe4ai-pilot/frontend/src/index.css#L1-L16)

**Section sources**
- [main.tsx:1-24](file://safe4ai-pilot/frontend/src/main.tsx#L1-L24)
- [App.tsx:1-100](file://safe4ai-pilot/frontend/src/App.tsx#L1-L100)
- [tokens.css:1-69](file://safe4ai-pilot/frontend/src/styles/tokens.css#L1-L69)
- [tailwind.config.ts:1-44](file://safe4ai-pilot/frontend/tailwind.config.ts#L1-L44)
- [index.css:1-16](file://safe4ai-pilot/frontend/src/index.css#L1-L16)

## Core Components
This section documents the three primary UI primitives and their props, variants, and styling approach.

- Button
  - Purpose: Standard interactive control with multiple variants and sizes, optional icons, and loading/disabled states.
  - Key props: variant, size, iconLeft, iconRight, loading, disabled, children, onClick, type, className.
  - Variants: default, primary, accent, ghost, danger.
  - Sizes: sm, md, lg.
  - Styling: Uses CSS custom properties from tokens and Tailwind utility classes for layout and transitions.

- Chip
  - Purpose: Lightweight status or tag indicator with tone and variant options.
  - Key props: variant, tone, children.
  - Tones: neutral, success, warn, danger, accent.
  - Variants: default, solid.
  - Styling: Uses CSS custom properties and inline dot styling mapped per tone.

- Avatar
  - Purpose: Initials-based user or entity avatar with configurable size and color.
  - Key props: name, size, color.
  - Styling: Computes initials, sets background and font size based on props.
  - Navigation integration: Used extensively in AdminLayout sidebar for user identification.

**Section sources**
- [Button.tsx:1-56](file://safe4ai-pilot/frontend/src/components/Button.tsx#L1-L56)
- [Chip.tsx:1-32](file://safe4ai-pilot/frontend/src/components/Chip.tsx#L1-L32)
- [Avatar.tsx:1-15](file://safe4ai-pilot/frontend/src/components/Avatar.tsx#L1-L15)

## Architecture Overview
The application initializes React Query and wraps the routing tree with providers. Protected routes enforce authentication and admin roles using the useAuth hook. Components consume design tokens and Tailwind utilities for consistent styling.

```mermaid
sequenceDiagram
participant Browser as "Browser"
participant Root as "main.tsx"
participant Router as "React Router"
participant App as "App.tsx"
participant Hook as "useAuth.ts"
participant API as "auth API"
Browser->>Root : Load app
Root->>Router : Render with QueryClientProvider and BrowserRouter
Router->>App : Render routes
App->>Hook : useAuth()
Hook->>API : getMe()
API-->>Hook : { me, role }
Hook-->>App : { isAuthenticated, isAdmin, isLoading }
App->>Router : Navigate based on auth state
```

**Diagram sources**
- [main.tsx:1-24](file://safe4ai-pilot/frontend/src/main.tsx#L1-L24)
- [App.tsx:19-31](file://safe4ai-pilot/frontend/src/App.tsx#L19-L31)
- [useAuth.ts:5-27](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts#L5-L27)

## Detailed Component Analysis

### Button Component
- Props and behavior
  - variant controls background, text, and border styles.
  - size controls height, padding, text size, and spacing.
  - loading toggles a spinner and disables interaction.
  - disabled prevents interaction and reduces opacity.
  - type aligns with HTML button semantics.
  - className allows additive customization.
- Styling approach
  - Base layout and focus ring classes are combined with variant and size maps.
  - CSS custom properties define semantic color tokens.
- Composition patterns
  - Combine iconLeft/iconRight with children to express actions succinctly.
  - Use variant primary for main actions, danger for destructive actions, ghost for secondary actions.

```mermaid
flowchart TD
Start(["Button render"]) --> ComputeClasses["Compute variant + size classes"]
ComputeClasses --> Merge["Merge base + variant + size + className"]
Merge --> StateCheck{"loading or disabled?"}
StateCheck --> |Yes| Disable["Disable interaction<br/>Apply disabled styles"]
StateCheck --> |No| Clickable["Enable interaction"]
Clickable --> Render["Render button with children/icons"]
Disable --> Render
```

**Diagram sources**
- [Button.tsx:34-55](file://safe4ai-pilot/frontend/src/components/Button.tsx#L34-L55)

**Section sources**
- [Button.tsx:1-56](file://safe4ai-pilot/frontend/src/components/Button.tsx#L1-L56)
- [tokens.css:1-69](file://safe4ai-pilot/frontend/src/styles/tokens.css#L1-L69)
- [tailwind.config.ts:3-38](file://safe4ai-pilot/frontend/tailwind.config.ts#L3-L38)

### Chip Component
- Props and behavior
  - tone selects semantic color mapping (default vs solid).
  - variant switches between light/default and solid palettes.
  - children holds the label text.
- Styling approach
  - Uses tone-specific background/text/border combinations.
  - Inline dot color is derived from a tone-to-color map for visual accent.
- Composition patterns
  - Use neutral for informational tags, success/warn/danger for status, accent for highlights.

```mermaid
flowchart TD
Start(["Chip render"]) --> SelectTone["Select tone palette"]
SelectTone --> ChooseVariant{"solid?"}
ChooseVariant --> |Yes| Solid["Use solid variant classes"]
ChooseVariant --> |No| Default["Use default variant classes"]
Solid --> Dot["Render colored dot"]
Default --> Dot
Dot --> Children["Render children"]
```

**Diagram sources**
- [Chip.tsx:24-31](file://safe4ai-pilot/frontend/src/components/Chip.tsx#L24-L31)

**Section sources**
- [Chip.tsx:1-32](file://safe4ai-pilot/frontend/src/components/Chip.tsx#L1-L32)
- [tokens.css:1-69](file://safe4ai-pilot/frontend/src/styles/tokens.css#L1-L69)
- [tailwind.config.ts:3-38](file://safe4ai-pilot/frontend/tailwind.config.ts#L3-L38)

### Avatar Component
- Props and behavior
  - name generates two-letter initials.
  - size controls width/height and font size.
  - color optionally overrides the default background.
- Styling approach
  - Computes initials and sets inline styles for size and background.
  - Uses a consistent rounded-circle presentation.
- Composition patterns
  - Pair with labels or in lists to represent users or entities.
  - Integrated into navigation components for user identification.

**Updated** Enhanced to include navigation integration patterns.

```mermaid
flowchart TD
Start(["Avatar render"]) --> Split["Split name into words"]
Split --> Initials["Take first char of each word<br/>Join first two chars uppercase"]
Initials --> BG["Resolve background color"]
BG --> Style["Set inline width/height/font-size"]
Style --> Render["Render initials"]
```

**Diagram sources**
- [Avatar.tsx:3-14](file://safe4ai-pilot/frontend/src/components/Avatar.tsx#L3-L14)

**Section sources**
- [Avatar.tsx:1-15](file://safe4ai-pilot/frontend/src/components/Avatar.tsx#L1-L15)
- [tokens.css:1-69](file://safe4ai-pilot/frontend/src/styles/tokens.css#L1-L69)

### Utility Hooks

#### useAuth
- Responsibilities
  - Fetches current user profile via React Query.
  - Provides authentication and admin checks.
  - Handles sign-out by clearing cache and navigating to login.
- Returns
  - me, isLoading, isAuthenticated, isAdmin, signOut.
- Integration
  - Consumed by route guards in App.tsx to protect routes.
  - Used by navigation components for user identification.

```mermaid
sequenceDiagram
participant Comp as "Component"
participant Hook as "useAuth.ts"
participant QC as "QueryClient"
participant API as "auth API"
Comp->>Hook : useAuth()
Hook->>QC : useQuery(["me"], getMe)
QC->>API : GET /me
API-->>QC : { user }
QC-->>Hook : data : user
Hook-->>Comp : { isAuthenticated, isAdmin, signOut }
Comp->>Hook : signOut()
Hook->>API : POST /logout
Hook->>QC : clear()
Hook-->>Comp : navigate to "/login"
```

**Diagram sources**
- [useAuth.ts:5-27](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts#L5-L27)
- [App.tsx:19-31](file://safe4ai-pilot/frontend/src/App.tsx#L19-L31)

**Section sources**
- [useAuth.ts:1-36](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts#L1-L36)
- [App.tsx:1-100](file://safe4ai-pilot/frontend/src/App.tsx#L1-L100)

#### useChat
- Responsibilities
  - Manages chat message history, streaming steps, and streaming state.
  - Streams assistant responses, citations, and completion metadata.
  - Supports stopping the stream and rating messages.
- Returns
  - messages, steps, streaming, sendMessage, rate, stop.
- Integration
  - Used by chat UI components to orchestrate the conversation lifecycle.

```mermaid
sequenceDiagram
participant UI as "Chat UI"
participant Hook as "useChat.ts"
participant API as "chat API"
UI->>Hook : sendMessage(question)
Hook->>Hook : append user message
Hook->>Hook : initialize steps
Hook->>Hook : set streaming=true
Hook->>API : streamChat(question, sessionId)
API-->>Hook : step events
API-->>Hook : token deltas
API-->>Hook : cite updates
API-->>Hook : done (sessionId, traceId, metrics)
Hook->>Hook : update messages/steps/streaming
UI->>Hook : rate(msgId, rating)
Hook->>API : submitFeedback(sessionId, traceId, rating)
```

**Diagram sources**
- [useChat.ts:17-105](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L17-L105)

**Section sources**
- [useChat.ts:1-106](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L1-L106)

#### useDocuments
- Responsibilities
  - Lists documents with periodic refetch.
  - Uploads new documents and polls ingestion status.
  - Deletes and reindexes documents.
- Returns
  - docs (with polling-aware status), isLoading, upload, uploadError, remove, reindex.

```mermaid
flowchart TD
Start(["useDocuments"]) --> Query["Query documents with refetch"]
Query --> Upload["upload(file)"]
Upload --> Invalidate["invalidate 'documents'"]
Invalidate --> Poll["pollStatus(id) loop"]
Poll --> Done["invalidate 'documents'"]
Query --> MutDelete["delete mutation"]
MutDelete --> Invalidate
Query --> MutReindex["reindex mutation"]
MutReindex --> Poll
```

**Diagram sources**
- [useDocuments.ts:5-60](file://safe4ai-pilot/frontend/src/hooks/useDocuments.ts#L5-L60)

**Section sources**
- [useDocuments.ts:1-61](file://safe4ai-pilot/frontend/src/hooks/useDocuments.ts#L1-L61)

#### useAuditStream
- Responsibilities
  - Paginates audit log events with a fixed page size.
  - Auto-refreshes periodically.
- Returns
  - events, isLoading, page, setPage, limit.

```mermaid
sequenceDiagram
participant UI as "Audit UI"
participant Hook as "useAuditStream.ts"
participant API as "audit API"
UI->>Hook : useAuditStream(start?)
Hook->>Hook : setPage(0)
Hook->>API : listAuditLogs(page*limit, limit, start)
API-->>Hook : events[]
Hook-->>UI : { events, isLoading, page, setPage }
Hook->>Hook : refetch every 30s
```

**Diagram sources**
- [useAuditStream.ts:5-16](file://safe4ai-pilot/frontend/src/hooks/useAuditStream.ts#L5-L16)

**Section sources**
- [useAuditStream.ts:1-17](file://safe4ai-pilot/frontend/src/hooks/useAuditStream.ts#L1-L17)

## Navigation Components

### AdminLayout Component
The AdminLayout serves as the primary navigation container for the admin interface, featuring a sidebar navigation system with integrated user avatar functionality.

- Navigation structure
  - Static navigation items: Overview, Documents, Activity, Feedback, Users, Settings
  - Dynamic feedback badge showing negative feedback count
  - Back-to-chat navigation link
  - User profile section with Avatar integration
- Avatar integration patterns
  - Used in sidebar footer for user identification
  - Name prop derived from authenticated user email
  - Size adjusted for sidebar context (24px)
- Styling approach
  - Responsive sidebar with fixed width (w-52)
  - Active state highlighting for current route
  - Hover states and transitions for interactive elements
  - Integration with design tokens for consistent theming

```mermaid
flowchart TD
Start(["AdminLayout render"]) --> NavItems["Render NAV items"]
NavItems --> ActiveCheck{"Check active route"}
ActiveCheck --> Highlight["Apply active state classes"]
Highlight --> FeedbackBadge["Show negative feedback count"]
FeedbackBadge --> UserSection["Render user section"]
UserSection --> Avatar["Render Avatar with user email"]
Avatar --> SignOut["Render sign out button"]
SignOut --> End(["Complete"])
```

**Diagram sources**
- [AdminLayout.tsx:59-133](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L59-L133)

**Section sources**
- [AdminLayout.tsx:1-144](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L1-L144)

### Navigation Integration Patterns
- Route-based active state management
- Dynamic badge indicators for feedback counts
- User avatar placement in navigation footers
- Consistent spacing and typography scales
- Responsive design considerations for sidebar navigation

**Section sources**
- [AdminLayout.tsx:12-19](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L12-L19)
- [AdminLayout.tsx:25-43](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L25-L43)

## Dependency Analysis
The design system is centralized in CSS custom properties and extended into Tailwind. Components rely on these tokens for consistent colors, typography, and spacing. The hooks depend on React Query for caching and server synchronization. Navigation components integrate Avatar components for user identification.

```mermaid
graph LR
Tokens["tokens.css"] --> TW["tailwind.config.ts"]
Tokens --> CSS["index.css"]
TW --> BTN["Button.tsx"]
TW --> CHIP["Chip.tsx"]
TW --> AVA["Avatar.tsx"]
TW --> ADMIN["AdminLayout.tsx"]
QC["@tanstack/react-query"] --> H_AUTH["useAuth.ts"]
QC --> H_CHAT["useChat.ts"]
QC --> H_DOCS["useDocuments.ts"]
QC --> H_AUDIT["useAuditStream.ts"]
AVA --> ADMIN
H_AUTH --> ADMIN
```

**Diagram sources**
- [tokens.css:1-69](file://safe4ai-pilot/frontend/src/styles/tokens.css#L1-L69)
- [tailwind.config.ts:1-44](file://safe4ai-pilot/frontend/tailwind.config.ts#L1-L44)
- [index.css:1-16](file://safe4ai-pilot/frontend/src/index.css#L1-L16)
- [Button.tsx:1-56](file://safe4ai-pilot/frontend/src/components/Button.tsx#L1-L56)
- [Chip.tsx:1-32](file://safe4ai-pilot/frontend/src/components/Chip.tsx#L1-L32)
- [Avatar.tsx:1-15](file://safe4ai-pilot/frontend/src/components/Avatar.tsx#L1-L15)
- [AdminLayout.tsx:1-144](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L1-L144)
- [useAuth.ts:1-36](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts#L1-L36)
- [useChat.ts:1-106](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L1-L106)
- [useDocuments.ts:1-61](file://safe4ai-pilot/frontend/src/hooks/useDocuments.ts#L1-L61)
- [useAuditStream.ts:1-17](file://safe4ai-pilot/frontend/src/hooks/useAuditStream.ts#L1-L17)

**Section sources**
- [package.json:11-30](file://safe4ai-pilot/frontend/package.json#L11-L30)
- [tokens.css:1-69](file://safe4ai-pilot/frontend/src/styles/tokens.css#L1-L69)
- [tailwind.config.ts:1-44](file://safe4ai-pilot/frontend/tailwind.config.ts#L1-L44)

## Performance Considerations
- React Query defaults
  - Stale time and refetch intervals are configured to balance freshness and network load.
- Streaming
  - useChat streams incremental updates; avoid unnecessary re-renders by updating only affected parts of state.
- Polling
  - useDocuments polls ingestion status with bounded retries; keep polling duration reasonable to prevent excessive requests.
- CSS custom properties
  - Using tokens ensures efficient style updates and avoids duplication across components.
- Navigation performance
  - Avatar components are lightweight and cached through React's component system.
  - AdminLayout uses efficient route-based active state detection.

## Troubleshooting Guide
- Authentication redirects
  - If navigation to protected routes fails, verify useAuth returns a valid user and that App route guards are applied.
- Chat streaming errors
  - On stream error events, messages are updated with an error message; ensure UI surfaces this state to users.
- Document uploads
  - Upload failures surface an error message; confirm file type and size constraints and retry.
- Audit pagination
  - If events do not refresh, check the refetch interval and page boundaries.
- Navigation issues
  - If Avatar appears incorrectly sized, verify size prop is appropriate for the context (24px for sidebar, default for other contexts).
  - If navigation active states don't work, check route matching logic in AdminLayout.

**Section sources**
- [App.tsx:19-31](file://safe4ai-pilot/frontend/src/App.tsx#L19-L31)
- [useChat.ts:83-87](file://safe4ai-pilot/frontend/src/hooks/useChat.ts#L83-L87)
- [useDocuments.ts:34-36](file://safe4ai-pilot/frontend/src/hooks/useDocuments.ts#L34-L36)
- [useAuditStream.ts:9-13](file://safe4ai-pilot/frontend/src/hooks/useAuditStream.ts#L9-L13)
- [AdminLayout.tsx:43](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L43)

## Conclusion
The component library centers on three lightweight, theme-driven primitives—Button, Chip, and Avatar—combined with four focused hooks for auth, chat, documents, and audit. The design system is defined via CSS custom properties and Tailwind, ensuring consistent visuals and scalable maintenance. The hooks integrate with React Query to manage server state and caching, enabling robust UI flows with minimal boilerplate. Navigation components like AdminLayout demonstrate effective integration patterns for Avatar components and provide a comprehensive framework for user interface navigation experiences.

## Appendices

### Design System and Theme Support
- Tokens
  - Semantic colors (ink, paper, surface, line, text), status colors (success, warn, danger), and accents.
  - Typography scales and spacing scales.
- Tailwind extension
  - Colors, fonts, border radii, shadows, and letter spacing are exposed as Tailwind theme keys.
- Global styles
  - index.css imports tokens and enables Tailwind layers, setting base font family and body styles.

**Section sources**
- [tokens.css:1-69](file://safe4ai-pilot/frontend/src/styles/tokens.css#L1-L69)
- [tailwind.config.ts:3-38](file://safe4ai-pilot/frontend/tailwind.config.ts#L3-L38)
- [index.css:1-16](file://safe4ai-pilot/frontend/src/index.css#L1-L16)

### Responsive Design Principles
- Typography and spacing scales are defined in tokens to maintain readability across breakpoints.
- Components use relative sizing and padding to adapt to container widths.
- Tailwind utilities enable responsive variants where needed.
- Navigation components adapt to different screen sizes while maintaining consistent user experience.

**Section sources**
- [tokens.css:53-68](file://safe4ai-pilot/frontend/src/styles/tokens.css#L53-L68)
- [index.css:7-15](file://safe4ai-pilot/frontend/src/index.css#L7-L15)

### Creating New Components
- Follow the existing pattern:
  - Define a functional component with a clear prop interface.
  - Use tokens and Tailwind utilities for styling.
  - Keep variants and sizes explicit and documented.
  - Export a default component and reuse design tokens.
- Consider navigation integration patterns for components that might appear in sidebar or footer contexts.

**Section sources**
- [Button.tsx:21-32](file://safe4ai-pilot/frontend/src/components/Button.tsx#L21-L32)
- [Chip.tsx:22](file://safe4ai-pilot/frontend/src/components/Chip.tsx#L22)
- [Avatar.tsx:1](file://safe4ai-pilot/frontend/src/components/Avatar.tsx#L1)

### Extending Existing Components
- Add new variants or sizes by expanding the variant/scale maps and adding corresponding Tailwind classes.
- Introduce new props with sensible defaults and derive styles from tokens.
- Maintain backward compatibility by keeping default props unchanged.
- Consider navigation-specific adaptations when extending components for sidebar usage.

**Section sources**
- [Button.tsx:7-19](file://safe4ai-pilot/frontend/src/components/Button.tsx#L7-L19)
- [Chip.tsx:6-12](file://safe4ai-pilot/frontend/src/components/Chip.tsx#L6-L12)

### Implementing Custom Hooks
- Use React Query for data fetching and caching.
- Encapsulate state updates and side effects in callbacks returned by the hook.
- Expose a minimal, predictable interface and handle loading/error states gracefully.
- Invalidate queries appropriately after mutations.
- Integrate with navigation components for user state management.

**Section sources**
- [useAuth.ts:8-18](file://safe4ai-pilot/frontend/src/hooks/useAuth.ts#L8-L18)
- [useDocuments.ts:10-26](file://safe4ai-pilot/frontend/src/hooks/useDocuments.ts#L10-L26)
- [useAuditStream.ts:9-13](file://safe4ai-pilot/frontend/src/hooks/useAuditStream.ts#L9-L13)

### Navigation Component Best Practices
- Use Avatar components consistently for user identification in navigation contexts.
- Implement route-based active state management for navigation items.
- Provide clear visual hierarchy with proper spacing and typography.
- Consider accessibility with proper ARIA labels and keyboard navigation.
- Test navigation components across different screen sizes and user contexts.

**Section sources**
- [AdminLayout.tsx:120-133](file://safe4ai-pilot/frontend/src/pages/admin/AdminLayout.tsx#L120-L133)
- [Avatar.tsx:3-14](file://safe4ai-pilot/frontend/src/components/Avatar.tsx#L3-L14)