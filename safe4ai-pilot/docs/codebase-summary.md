Here is a comprehensive structured summary.

---

# Safe4AI Pilot — Complete Codebase Analysis

## 1. How to Start the Application

### Quick Dev Start (no Docker)
```bash
# 1. Start infrastructure services via Docker
docker compose up -d postgres qdrant ollama ollama-init jaeger

# 2. Copy and configure environment
cp .env.example .env
# Edit .env — at minimum set a strong SECRET_KEY

# 3. Install backend Python dependencies
uv sync   # or: pip install -e .

# 4. Seed database (creates admin user + 3 sample policy docs)
python -m scripts.seed

# 5. Start backend dev server (auto-reload)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
# Serves at: http://localhost:8000
# Health check: http://localhost:8000/health

# 6. Install frontend dependencies (separate terminal)
cd frontend
npm install

# 7. Start frontend dev server
npm run dev
# Serves at: http://localhost:3000
```

### Full Docker Compose (one command)
```bash
docker compose up -d
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# Jaeger UI: http://localhost:16686 (tracing)
# Qdrant: http://localhost:6333 (vector DB)
```

### Ports Summary
| Service | Port |
|---|---|
| Frontend (Vite dev) | `3000` |
| Backend (FastAPI) | `8000` |
| PostgreSQL (pgvector) | `5432` |
| Qdrant (vector DB) | `6333` |
| Ollama (LLM) | `11434` |
| Jaeger (tracing) | `16686` (UI), `4317` (OTLP) |

---

## 2. Authentication & Login

### How Auth Works
- Backend sets an **HTTP-Only JWT cookie** (`access_token`) on successful login
- Token expiry: **8 hours** (`JWT_EXPIRY_HOURS`)
- JWT signed with `SECRET_KEY` (HS256 algorithm)
- Rate-limited: **5 login attempts per minute** per IP
- Brute-force lockout: **20 failed attempts** → account locked **15 minutes**
- Minimum password length: **12 characters** (enforced server-side)

### Seed account
- **Email:** `admin@safe4ai.local`
- **Password:** `ChangeMe!2024Pilot`
- **Role:** `admin` (has access to everything including admin panels)

### Creating Additional Users
- No self-registration or sign-up flow exists
- Admin can create users via `POST /admin/users` (requires admin auth)
- Admin can also use the backend CLI or DB directly
- Only two roles: `admin` and `pilot_user`

### Login Flow (from `LoginPage.tsx`)
1. User visits `/login`
2. Fills **Email** + **Password** fields
3. Form validated with Zod (valid email, non-empty password)
4. Calls `POST /auth/login` with credentials
5. On success: JWT cookie set, redirected to `/chat`
6. On failure: error banner "Invalid credentials. Try again."

### Additional UI Elements on Login Page
- **Google SSO button** — disabled, labeled "not available yet"
- **"Forgot password?"** — disabled, labeled "not available yet"
- **"or with credentials"** divider

### Logout
- **"Sign out"** link in ChatPage header and AdminLayout sidebar footer
- Calls `POST /auth/logout` → clears cookie → redirects to `/login`

### Auth Guards
- `RequireAuth`: checks `me` query → redirects to `/login` if unauthenticated
- `RequireAdmin`: checks `me.role === "admin"` → redirects to `/chat` if not admin
- Protected routes: `/chat` (any authenticated), all `/admin/*` (admin only)

---

## 3. Every User-Facing Route/Page

### 3.1 Public Routes

| Route | Page Component | Description |
|---|---|---|
| `/login` | `LoginPage.tsx` | Split-panel login form with brand panel + credentials form |

### 3.2 Authenticated Routes (any logged-in user)

| Route | Page Component | Description |
|---|---|---|
| `/chat` | `ChatPage.tsx` | Main RAG chat interface — ask questions, get answers with citations |
| `/*` (catch-all) | Redirects to `/chat` | Default redirect |

### 3.3 Admin Routes (admin role required)

| Route | Page Component | Description |
|---|---|---|
| `/admin` | Redirects to `/admin/overview` | Admin section root |
| `/admin/overview` | `OverviewPage.tsx` | Dashboard — queries, costs, latency, cache hits, feedback quality |
| `/admin/documents` | `DocumentsPage.tsx` | Document management — upload, inspect, delete, reindex |
| `/admin/audit` | `ActivityPage.tsx` | Audit trail — filterable event stream with CSV export |
| `/admin/feedback` | `FeedbackPage.tsx` | User feedback — browse up/down ratings with detail inspector |
| `/admin/users` | `UsersPage.tsx` | User management — list users, deactivate non-admin users |
| `/admin/settings` | `SettingsPage.tsx` | Placeholder — "Settings coming soon" |

### 3.4 Admin Layout (`AdminLayout.tsx`)
All admin pages share:
- **Left sidebar navigation** with 6 items: Overview, Documents, Activity, Feedback (with negative count badge), Users, Settings
- **Top bar**: page title + optional action buttons
- **Index health card** in sidebar (always shows "Indexing healthy")
- **User avatar + email + sign out** at sidebar bottom
- **Live feedback badge** on Feedback nav item showing count of negative ratings

---

## 4. Every User Journey

### Journey 1: Authentication & Login
1. User navigates to any protected route → redirected to `/login`
2. **Sees**: Two-panel layout (brand panel left, form right)
3. **Fills**: Email input `you@company.com`, Password input
4. **Clicks**: "Sign in" button (blue, full-width)
5. **If valid**: Redirected to `/chat`
6. **If invalid**: Sees red error banner "Invalid credentials. Try again."
7. **Edge cases**:
   - Empty fields show inline validation: "Enter a valid email" / "Password is required"
   - Rate-limited (10/min) → FastAPI 429 "Too Many Requests"
   - Brute-force lockout → 429 "Account temporarily locked"

### Journey 2: Chatting (Happy Path)
1. User at `/chat` sees **empty state**:
   - Greeting: "Good morning/afternoon/evening, {email_local_part}"
   - Hero text: "What should we look up today?"
   - Stats: "{N} chunks across {M} documents"
   - **4 suggested prompts** in a 2x2 grid (Policy, Finance, IT, Compliance)
2. User **clicks a suggested prompt** → fills composer textarea with that question
   - Or **types** their own question in the composer
3. User **presses Enter** (or clicks send button) to submit
4. **While streaming**:
   - User message appears as a right-aligned bubble (rounded corners)
   - "Generating…" pill appears in header with pulsing blue dot
   - Assistant shows empty bubble with blinking cursor
   - **StreamingPipeline** component shows 4 animated steps: Embedding query → Retrieving chunks → Reranking → Generating answer
   - A "Stop generating" button appears above composer
5. **After streaming completes**:
   - Answer text appears with **clickable citation chips** like `[1]`
   - **Sources** displayed as clickable buttons with `[1] filename p.1`
   - **Trust signal** bar shows: `latency ms · fresh/cache hit · N retrievals · model`
   - **Action buttons**: Copy, Thumbs Up, Thumbs Down
   - **Right sidebar** (360px) opens with full **Sources** panel
6. User can continue asking — session persists across messages
7. User can click a citation chip → highlights in answer + highlights in Sources sidebar
8. User can click **"Sign out"** in header → returns to `/login`

### Journey 3: Rating an Answer
1. After receiving an answer, user clicks **Thumbs Up** (👍) or **Thumbs Down** (👎)
2. Rating sends `POST /feedback` with session_id, trace_id, rating ("positive"/"negative")
3. Thumbs turns green (up) or red (down)
4. Button becomes disabled (one rating per answer)
5. If admin later inspects in Feedback page, they see this rating

### Journey 4: Admin — View Dashboard
1. User is admin → sees **"Admin"** button in chat header
2. Clicks "Admin" → lands on `/admin/overview`
3. **Sees**:
   - "Today's briefing" with date/time
   - **Narrative paragraph**: "The pilot processed {N} queries this period, with an average latency of {X}ms. The semantic cache absorbed {N} LLM calls..."
   - **Traffic cards** (3): Total queries, Active users, Avg cost/query
   - **Quality section**: helpful/not-helpful counts, ratio, green/red bar
   - **"Worth a look"**: up to 3 most recent negative feedback items with comment/trace info
   - **Cost section**: total infrastructure spend
4. Data refreshes every 60 seconds automatically

### Journey 5: Admin — Manage Documents
1. Admin navigates to `/admin/documents`
2. **Sees**:
   - Header: "Documents" with count + "Upload" button
   - **Drop zone**: "Drop PDFs, DOCX, MD or TXT here" (drag & drop enabled)
   - **Document table** with columns: Name, Type, Chunks, Size, Status/added by, Action (⋯)
3. **Upload flow**:
   - Click "Upload" button OR drag files onto drop zone
   - File picker accepts: `.pdf`, `.docx`, `.xlsx`, `.txt`
   - File uploaded via `POST /admin/documents/upload` (multipart form data)
   - Document appears in table with status "queued" → "embedding" (animated spinner) → "indexed"
   - Max upload size: 50MB (configurable)
   - Rate-limited: 10 uploads/hour
4. **Inspect document**:
   - Click a document row → right inspector panel (320px) opens
   - Shows: name, chunk count, size, type, status chip, added date/by
   - Action buttons at bottom: "Reindex" and "Delete"
5. **Reindex**: Clicks "Reindex" → document re-queued for ingestion
6. **Delete**:
   - Clicks "Delete" → confirmation modal appears
   - Modal: "Delete document? {name} will be removed from the index and cannot be recovered."
   - Two buttons: "Cancel" (outlined) and "Delete" (red)
   - On confirm: document removed from filesystem, Qdrant, DB, and semantic cache
7. **Error handling**: If upload fails → dismissible red error banner at top

### Journey 6: Admin — View Activity Log
1. Admin navigates to `/admin/audit`
2. **Sees**:
   - Header: "Activity" with "Export CSV" button
   - **Left filter rail**: Kind filters (All, Query, Index, Feedback, Auth, Fallback) with counts
   - **Range filters**: Last hour, Today, Last 7 days, Last 30 days
   - **Timeline**: events shown with timeline node dots, color-coded by kind
   - Each event shows: time, kind badge (QUERY/INDEX/FEEDBACK/AUTH/FALLBACK), user, query text, latency, trace ID
   - "Live" indicator with pulsing blue dot
3. **Filter**: Click any kind or range to filter events
4. **Export CSV**: Click "Export CSV" → downloads `audit-YYYY-MM-DD.csv`
5. Data refreshes every 30 seconds

### Journey 7: Admin — Review Feedback
1. Admin navigates to `/admin/feedback`
2. **Sees**:
   - Header: "Feedback" with count
   - **Filter tabs**: All (count), 👍 (count), 👎 (count)
   - **List panel** (320px): each item shows thumbs icon (green/red), user ID, comment preview, timestamp
   - Active item highlighted with left blue border
3. **Inspect feedback**:
   - Click item → detail panel opens
   - Shows: thumbs up/down chip, trace ID, timestamp
   - **Navigation**: Previous/next buttons + close (✕) button
   - **Reporter**: Avatar + user ID
   - **Comment** (if any): shown in colored box (green for positive, red for negative)
   - **Trace info**: latency, cache, model, k_retrieved (all placeholder "—" currently)
   - **"Suspected cause" card**: placeholder suggesting review trace/chunks
   - **Metadata grid**: User, Session ID, Trace ID
4. Data refreshes every 30 seconds

### Journey 8: Admin — Manage Users
1. Admin navigates to `/admin/users`
2. **Sees**:
   - Header: "Users" with count
   - **User list**: each row shows Avatar, Email, Join date, Role chip (admin=accent/pilot_user=neutral), Status chip (active=green/inactive=red)
3. **Deactivate a user**:
   - Only available for active, non-admin users
   - Click "Deactivate" button → confirmation modal
   - Modal: "Deactivate user? {email} will lose workspace access immediately."
   - Two buttons: "Cancel" and "Deactivate" (red)
   - On confirm: `DELETE /admin/users/{id}` → user.is_active = false
4. Admin cannot deactivate their own account (API blocks it)

### Journey 9: Admin — Settings (Placeholder)
1. Admin navigates to `/admin/settings`
2. **Sees**: Gear icon + "Settings coming soon" + placeholder text about model selection, retention policies, SMTP

---

## 5. Key UI Components (Interactive Elements Needing Testing)

### Shared/Global Components
| Component | File | Type | Interactions |
|---|---|---|---|
| **Button** | `Button.tsx` | Reusable button | Click, loading state, disabled state, 5 variants (default/primary/accent/ghost/danger), 3 sizes (sm/md/lg), left/right icons |
| **Chip** | `Chip.tsx` | Status badge | Renders with colored dot, 5 tones (neutral/success/warn/danger/accent), 2 variants (default/solid) |
| **Avatar** | `Avatar.tsx` | User avatar | Displays initials in dark circle, configurable size |
| **Logo** | `Logo.tsx` | SVG logo | Configurable size, dark background with triangle + blue square |
| **ErrorBoundary** | `ErrorBoundary.tsx` | Error boundary | Catches render errors, shows "Refresh workspace" button |

### Chat Components
| Component | File | Type | Interactions |
|---|---|---|---|
| **Composer** | `Composer.tsx` | Textarea + send button | Type text, auto-grow (max 160px), Enter to submit, Shift+Enter for newline, disabled during streaming, send button disabled when empty, scope label optional |
| **MessageBubble** | `MessageBubble.tsx` | Message wrapper | Right-aligned for user (special border-radius), left-aligned for assistant |
| **AnswerBlock** | `AnswerBlock.tsx` | Full assistant response | Renders body text with inline citation chips, sources list, copy button, thumbs up/down (disabled after rating), trust signal, blinking cursor during streaming |
| **CitationChip** | `CitationChip.tsx` | Inline citation `[N]` | Click to toggle active state (highlighted blue vs default), two color variants (active=white on blue, default=blue on light blue) |
| **TrustSignal** | `TrustSignal.tsx` | Trust metadata bar | Clickable (placeholder), shows latency ms, cache hit/fresh, N retrievals, model name |
| **StreamingPipeline** | `StreamingPipeline.tsx` | Step indicator | Shows 4 steps (embed → retrieve → rerank → generate) with icons (check=done, spinner=active, circle=pending) |
| **SuggestedPrompt** | `SuggestedPrompt.tsx` | Prompt card | Click to fill composer, shows tag + icon + question + source, hover border color transition |
| **SourceRow** | `SourceRow.tsx` | Source in sidebar | Clickable, shows filename/page/relevance score, highlight when active, compact mode variant |

### Admin Components
| Component | File | Type | Interactions |
|---|---|---|---|
| **AdminLayout** | `AdminLayout.tsx` | Admin shell | 6 nav links with active state, feedback badge count, sign-out button, indexing health card |
| **DocumentRow** | `DocumentRow.tsx` | Document table row | Click to select, hover shows ⋯ button, displays file type badge (color-coded: PDF/DOCX/XLSX/MD/CSV/TXT), chunk count, size, status chip, embedding spinner |
| **ActivityEvent** | `ActivityEvent.tsx` | Timeline event | Timeline node dot (color by kind), kind badge (color-coded), shows time/user/query/latency/trace |
| **FeedbackListItem** | `FeedbackListItem.tsx` | Feedback row | Click to select, active state with blue left border, shows thumbs icon, user, comment preview, timestamp |
| **Sparkline** | `Sparkline.tsx` | Mini line chart | SVG-based, configurable color/height/fill area |

### Forms & Modals
| Element | Page | Type | Interactions |
|---|---|---|---|
| **Login form** | LoginPage | Form with 2 inputs + submit | Email (type=email), Password (type=password), Zod validation, server error display, submit button with loading spinner |
| **Delete document modal** | DocumentsPage | Confirmation dialog | Shows document name, "Cancel" + "Delete" (red) buttons, backdrop overlay |
| **Deactivate user modal** | UsersPage | Confirmation dialog | Shows user email, "Cancel" + "Deactivate" (red) buttons, backdrop overlay |
| **File upload** | DocumentsPage | File input + drag-drop | Hidden `<input type="file" multiple accept=".pdf,.docx,.xlsx,.txt">`, drag-and-drop zone with visual feedback (blue border on drag), "Browse" link in drop zone |
| **Upload error banner** | DocumentsPage | Dismissible alert | Red banner with message + ✕ dismiss button |

### Interactive Filters & Navigation
| Element | Page | Type | Interactions |
|---|---|---|---|
| **Activity kind filter** | ActivityPage | Button group (left rail) | 6 filter buttons with event counts, active state highlight |
| **Activity range filter** | ActivityPage | Button group (left rail) | 4 range buttons: Last hour, Today, Last 7 days, Last 30 days |
| **Feedback filter tabs** | FeedbackPage | Button group | 3 tabs: All, 👍, 👎 with counts |
| **Feedback detail nav** | FeedbackPage | Navigation buttons | Previous (←), Next (→), Close (✕) buttons with disabled states |
| **Admin sidebar nav** | AdminLayout | Link group | 6 nav links with active highlight + negative feedback count badge |
| **Citation source buttons** | AnswerBlock | Source list | Click to toggle citation highlight, shows filename/page, active state styling |
| **Chat scope indicator** | Composer | Optional label | Shows scope name + chunk count (currently not used in ChatPage) |

### State-Driven UI Conditions (Edge Cases)
| State | Where | Behavior |
|---|---|---|
| **Loading** | All pages | "Loading…" centered text |
| **Empty chat** | ChatPage | Hero greeting, suggested prompts grid, doc stats |
| **Empty documents** | DocumentsPage | "No documents yet. Upload one above." |
| **Empty audit events** | ActivityPage | "No events yet." |
| **Empty feedback** | FeedbackPage | "No feedback yet." |
| **Empty users** | UsersPage | "No users found." |
| **No negative feedback** | OverviewPage | "No negative feedback in this period." |
| **No selection** | FeedbackPage detail | "Select an item to inspect" |
| **Streaming in progress** | ChatPage | Generating pill, streaming pipeline, Stop button, disabled composer |
| **Upload in progress** | DocumentsPage | Spinner on document row status "embedding" |
| **Admin-only UI** | ChatPage header | "Admin" button hidden for non-admin users |
| **Non-admin on admin route** | App | Redirect to `/chat` |
| **Unauthenticated** | App | Redirect to `/login` |

---

## API Endpoint Summary (Backend)

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/login` | None (rate-limited) | Login, returns JWT cookie |
| `POST` | `/auth/logout` | None | Clears JWT cookie |
| `GET` | `/me` | Any authenticated | Current user info (id, email, role) |
| `POST` | `/chat` | Any | Blocking chat (for eval/testing) |
| `POST` | `/chat/stream` | Any | SSE streaming chat (for frontend) |
| `POST` | `/feedback` | Any | Submit thumbs up/down feedback |
| `POST` | `/admin/documents/upload` | Admin | Upload document |
| `GET` | `/admin/documents` | Admin | List all documents |
| `GET` | `/admin/documents/{id}/status` | Admin | Poll ingestion status |
| `DELETE` | `/admin/documents/{id}` | Admin | Delete document |
| `POST` | `/admin/documents/{id}/reindex` | Admin | Re-trigger ingestion |
| `GET` | `/admin/users` | Admin | List users |
| `POST` | `/admin/users` | Admin | Create user (email+password+role) |
| `DELETE` | `/admin/users/{id}` | Admin | Deactivate user |
| `GET` | `/admin/audit-logs` | Admin | List audit events (filtered, paginated) |
| `GET` | `/admin/audit-logs/export.csv` | Admin | Download audit CSV |
| `GET` | `/admin/stats` | Admin | Aggregate dashboard stats |
| `GET` | `/admin/feedback` | Admin | List all feedback |
| `GET` | `/admin/stats/cost` | Admin | Cost statistics |
| `GET` | `/admin/review-queue` | Admin | List human review queue |
| `POST` | `/admin/review-queue/{id}/approve` | Admin | Approve review item |
| `POST` | `/admin/review-queue/{id}/reject` | Admin | Reject review item |
| `GET` | `/health` | None | Health check (postgres, qdrant, ollama) |

---

## RAG Pipeline (The "AI Agent" Behind Chat)

The chat uses a **LangGraph** pipeline with these nodes:
1. **intake** → Validate/rewrite the user query
2. **rewrite** → Query rewriting/expansion
3. **retrieve** → Hybrid retrieval from Qdrant (dense + BM25 sparse)
4. **grade** → Rerank + relevance grading
5. **decompose** → Sub-query decomposition if needed
6. **generate** → LLM answer generation (Ollama: qwen3.5:9b)
7. **output_filter** → Filter/censor output
8. **quality_gate** → Quality check (can trigger human review)
9. **respond** → Deliver final answer
10. **fallback** → Graceful degradation if pipeline fails
