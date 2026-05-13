// private-ai · Component contracts
// TypeScript prop signatures for every component in the prototype.
// Use this as the spec when reimplementing in your React+TS codebase.
// Nothing here imports React on purpose — it's a pure type spec.

import type { ReactNode } from "react";

// ─── Domain types ───────────────────────────────────────────────────────────

export type DocStatus = "indexed" | "embedding" | "skipped" | "failed" | "queued";
export type DocType   = "PDF" | "DOCX" | "MD" | "TXT" | "CSV" | "HTML";

export interface DocumentRecord {
  id: string;
  name: string;
  type: DocType;
  size: string;          // human-readable, e.g. "1.2 MB"
  bytes: number;
  chunks: number;
  status: DocStatus;
  progress?: number;     // 0..1, when status === 'embedding'
  addedAt: string;       // ISO
  addedBy: string;       // display name or "Auto · S3 watch"
  note?: string;         // failure / skip reason
  sha256?: string;
  pages?: number;
}

export interface SourceChunk {
  id: string;            // citation id, e.g. "1", "2"
  file: string;
  page: number;
  loc: string;           // human ref, e.g. "§ 9.1 — Liability cap"
  excerpt: string;
  score: number;         // 0..1
  used: boolean;         // whether the chunk was passed to the model
  documentId: string;
  chunkIndex: number;
}

export interface AuditEvent {
  id: string;
  ts: string;            // ISO timestamp
  kind: "query" | "upload" | "feedback" | "login" | "fallback";
  who: string;           // user identifier or system
  role?: string;
  query?: string;
  doc?: string;
  rating?: "up" | "down";
  note?: string;
  latencyMs?: number;
  cacheHit?: boolean;
  model?: string;
  kRetrieved?: number;
  topScore?: number;
  fallbackReason?: string;
  ip?: string;
  traceId?: string;
}

export interface FeedbackItem {
  id: string;
  traceId: string;
  ts: string;
  user: { name: string; email: string; role: string };
  rating: "up" | "down";
  query: string;
  answer: string;
  note?: string;
  retrievedChunks: SourceChunk[];
  latencyMs: number;
  cacheHit: boolean;
  model: string;
}

export interface TrustSignalData {
  latencyMs: number;
  cacheHit: boolean;
  model: string;
  kRetrieved: number;
}

export interface StatsToday {
  generatedAt: string;
  queries:   { total: number; trendPct: number; series: number[] };
  users:     { total: number; trendAbs: number; series: number[] };
  cost:      { totalUsd: number; embeddingsUsd: number; generationUsd: number; rerankerUsd: number; ceilingUsd: number };
  latency:   { p50: number; p95: number; series: { t: string; p50: number; p95: number }[] };
  cacheHitPct: number;
  fallbackPct: number;
  feedback:  { up: number; down: number };
  notable:   Array<{ kind: "fallback" | "feedback" | "index"; head: string; body: string; cta?: string; link?: string }>;
}

// ─── Atoms ──────────────────────────────────────────────────────────────────

export interface ButtonProps {
  variant?: "default" | "primary" | "accent" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  iconLeft?: ReactNode;
  iconRight?: ReactNode;
  loading?: boolean;
  disabled?: boolean;
  children?: ReactNode;
  onClick?: () => void;
}

export interface ChipProps {
  variant?: "default" | "solid";
  tone?: "neutral" | "success" | "warn" | "danger" | "accent";
  children?: ReactNode;
}

export interface AvatarProps {
  name: string;        // initials derived from name
  size?: number;
  color?: string;      // bg override
}

export interface FieldProps {
  label?: string;
  hint?: string;
  error?: string;
  iconLeft?: ReactNode;
  /* + all standard input props */
}

export interface KbdProps { children: string; }

// ─── Chat ───────────────────────────────────────────────────────────────────

export interface CitationChipProps {
  id: string;
  /** Triggers the hover popover; data fetched from `GET /chunks/:id` */
  onOpen?: (id: string) => void;
  active?: boolean;
}

export interface CitationPopoverProps {
  source: SourceChunk;
  anchorRef: React.RefObject<HTMLElement>;
  onClose: () => void;
  onOpenDoc: (documentId: string, page: number) => void;
}

export interface TrustSignalProps extends TrustSignalData {
  /** Click → open the trace in audit view */
  onOpenTrace?: () => void;
}

export interface SourceRowProps {
  source: SourceChunk;
  compact?: boolean;
  onOpen?: () => void;
}

export interface AnswerBlockProps {
  /** Markdown-ish body, with `[n]` placeholders that render as <CitationChip>. */
  body: string;
  sources: SourceChunk[];
  trust: TrustSignalData;
  onCopy?: () => void;
  onRegenerate?: () => void;
  onRate?: (rating: "up" | "down") => void;
  isStreaming?: boolean;
}

export interface ComposerProps {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  scope?: { name: string; chunkCount: number };
  onScopeChange?: () => void;
  disabled?: boolean;
  placeholder?: string;
}

export interface MessageBubbleProps {
  role: "user" | "assistant";
  children: ReactNode;
}

export interface SuggestedPromptProps {
  tag: string;          // e.g. "freshly indexed"
  icon?: ReactNode;
  question: string;
  source: string;
  onSelect: () => void;
}

export interface StreamingPipelineProps {
  steps: Array<{
    name: "embed" | "retrieve" | "rerank" | "generate";
    label: string;
    detail?: string;     // e.g. "1536-d · 18ms"
    state: "pending" | "active" | "done";
  }>;
}

// ─── Admin ──────────────────────────────────────────────────────────────────

export type AdminRoute = "overview" | "documents" | "audit" | "feedback" | "users" | "settings";

export interface AdminLayoutProps {
  active: AdminRoute;
  user: { name: string; role: string };
  indexHealth: { ok: boolean; chunks: number; docs: number; lastIndexedAt: string };
  children: ReactNode;
}

export interface DocumentRowProps {
  doc: DocumentRecord;
  selected?: boolean;
  onSelect?: () => void;
  onReindex?: () => void;
  onDelete?: () => void;
}

export interface DocumentInspectorProps {
  doc: DocumentRecord;
  retrievalSeries: number[];      // last 14 days
  topChunks: Array<{ page: number; label: string; hits: number }>;
  onReindex: () => void;
  onDelete: () => void;
}

export interface ActivityEventProps {
  event: AuditEvent;
  onOpenTrace?: (traceId: string) => void;
}

export interface SparklineProps {
  data: number[];
  color?: string;
  height?: number;
  fill?: boolean;
}

export interface FeedbackListItemProps {
  item: FeedbackItem;
  active?: boolean;
  onSelect?: () => void;
}

export interface FeedbackDetailProps {
  item: FeedbackItem;
  onReindex?: (documentId: string) => void;
  onPrev?: () => void;
  onNext?: () => void;
}

// ─── Pages (smart components — wire React Query here) ───────────────────────

export interface ChatPageProps {
  sessionId: string;
  /** Layout pick; map to ChatA vs ChatB from the prototype */
  layout?: "centered" | "workbench";
}

export interface DocumentsPageProps { /* uses useDocuments() internally */ }
export interface AuditPageProps     { /* uses useAuditStream() internally */ }
export interface OverviewPageProps  { /* uses useStats() */ }
export interface FeedbackPageProps  { /* uses useFeedback() */ }
