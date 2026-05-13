# private·ai — Frontend handoff

This package translates the visual prototype (`Private AI — Web UI.html`) into
implementation guidance for your React + TypeScript codebase.

## Stack mapping (from your Phase 4 spec)

| Concern        | Implementation                                   |
| -------------- | ------------------------------------------------ |
| Framework      | React 18 + Vite                                  |
| Language       | TypeScript                                       |
| Styling        | Tailwind CSS (use `tokens.css` / `tailwind.config.ts`) |
| Server state   | TanStack Query (React Query)                     |
| Routing        | React Router or TanStack Router                  |
| Icons          | `lucide-react` (the prototype mirrors Lucide 1:1) |
| Forms          | React Hook Form + zod                            |
| Charts         | inline SVG (kept simple) or Recharts             |
| Auth           | JWT in HTTP-only cookie set by `POST /auth/login` — frontend never reads it |
| API base       | `import.meta.env.VITE_API_URL`                   |

## Project layout

```
src/
├─ pages/
│  ├─ LoginPage.tsx              ← prototype: Login.jsx
│  ├─ ChatPage.tsx               ← prototype: ChatA / ChatB (pick one)
│  └─ admin/
│     ├─ AdminLayout.tsx         ← prototype: AdminShell.jsx
│     ├─ DocumentsPage.tsx       ← prototype: AdminDocs.jsx
│     ├─ ActivityPage.tsx        ← prototype: AdminAudit.jsx
│     ├─ OverviewPage.tsx        ← prototype: AdminStats.jsx
│     ├─ FeedbackPage.tsx        ← prototype: AdminFeedback.jsx
│     └─ UsersPage.tsx           ← TBD (not in prototype)
├─ components/
│  ├─ Logo.tsx
│  ├─ Avatar.tsx
│  ├─ Button.tsx
│  ├─ Chip.tsx
│  ├─ Field.tsx
│  ├─ chat/
│  │  ├─ Composer.tsx
│  │  ├─ MessageBubble.tsx
│  │  ├─ AnswerBlock.tsx
│  │  ├─ CitationChip.tsx        ← inline [n] footnote
│  │  ├─ CitationPopover.tsx     ← hover preview
│  │  ├─ TrustSignal.tsx
│  │  ├─ SourceRow.tsx
│  │  ├─ SuggestedPrompt.tsx
│  │  └─ StreamingPipeline.tsx
│  └─ admin/
│     ├─ DocumentRow.tsx
│     ├─ ActivityEvent.tsx
│     ├─ Sparkline.tsx
│     └─ FeedbackListItem.tsx
├─ api/
│  ├─ client.ts                  ← fetch wrapper, sends credentials
│  ├─ auth.ts
│  ├─ chat.ts
│  ├─ documents.ts
│  ├─ feedback.ts
│  ├─ audit.ts
│  └─ stats.ts
├─ hooks/
│  ├─ useAuth.ts
│  ├─ useChat.ts                 ← streaming-aware
│  ├─ useDocuments.ts
│  └─ useAuditStream.ts
└─ styles/
   └─ tokens.css                 ← from this handoff
```

## Endpoint mapping

| UI surface               | API call                                                  | Notes |
| ------------------------ | --------------------------------------------------------- | ----- |
| Login submit             | `POST /auth/login`                                        | Server sets HTTP-only cookie. Don't store a token in JS. |
| Chat send                | `POST /chat/stream` (SSE) or `POST /chat`                 | Stream tokens for the streaming UI. |
| Source on hover          | `GET /chunks/:id` (or include excerpt in /chat response)  | For inline PDF peek. |
| Feedback 👍/👎           | `POST /feedback`                                          | Body: `{ traceId, rating, note? }`. |
| Document upload          | `POST /documents` (multipart) → poll `GET /documents/:id` | Status polling drives the embedding progress chip. |
| Document list            | `GET /documents?cursor=…&q=…&status=…`                    | Cursor-paginated. |
| Reindex / delete         | `POST /documents/:id/reindex` · `DELETE /documents/:id`   |       |
| Audit log                | `GET /audit?cursor=…&kind=…&user=…&from=…&to=…`           | Cursor-paginated; tail-mode for "live". |
| Audit export CSV         | `GET /audit.csv?…`                                        | Triggers download. |
| Stats / overview         | `GET /stats/today`                                        | Returns shape consumed by `OverviewPage`. |
| Stats export JSON        | `GET /stats/today.json`                                   |       |
| Feedback list            | `GET /feedback?rating=…`                                  |       |
| Feedback detail (trace)  | `GET /traces/:traceId`                                    | Drives the trace review screen. |
| Users                    | `GET/POST/DELETE /users`                                  | Admin only. |

## Streaming chat

`StreamingPipeline` shows the four steps (embed → retrieve → rerank → generate)
because each emits a server-sent event the frontend can light up. Suggested SSE
event names:

- `step` — `{ name: "embed"|"retrieve"|"rerank"|"generate", t: ms, meta: {...} }`
- `token` — `{ delta: string }`
- `cite` — `{ id, file, page, score }` (one per retrieved chunk)
- `done` — `{ traceId, latencyMs, cache: bool, model: string, kRetrieved: number }`

## Component contracts

See `component-contracts.ts` for TypeScript prop signatures of every component
in the prototype.

## What's NOT in the prototype

You'll still need to design / build:

- **Users page** (admin) — list, add, deactivate
- **Settings page** (admin) — model selection, retrieval scope, API keys
- **Mobile chat layout** — prototype is desktop-only
- **Dark mode** — tokens support it (`.pa-root.dark`) but only stubbed
- **Empty / error / loading skeletons** for every list (only chat empty exists)

## Quick-start checklist

- [ ] Install fonts: Geist + Geist Mono + Instrument Serif (Google Fonts)
- [ ] Install: `lucide-react`, `@tanstack/react-query`, `react-hook-form`, `zod`
- [ ] Drop `tokens.css` into `src/styles/` and import in entry
- [ ] Merge `tailwind.config.ts` into your config
- [ ] Build atoms first: `Button`, `Chip`, `Field`, `Avatar`, `CitationChip`
- [ ] Then `Composer` + `AnswerBlock` + `MessageBubble`
- [ ] Then `ChatPage` end-to-end with mock data
- [ ] Wire `POST /chat/stream` last — UI should work with a static fixture first
