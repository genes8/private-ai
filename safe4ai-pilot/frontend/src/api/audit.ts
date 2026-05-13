import { apiFetch, apiUrl } from "./client";

export type AuditKind = "query" | "upload" | "feedback" | "login" | "fallback";

export interface AuditEvent {
  id: string;
  ts: string;
  kind: AuditKind;
  who: string;
  query?: string;
  latencyMs?: number;
  traceId?: string;
}

interface RawAudit {
  id: string;
  timestamp: string;
  user_id: string;
  action_type: string;
  query_text: string | null;
  latency_ms: number | null;
  trace_id: string | null;
}

function mapKind(t: string): AuditKind {
  if (t === "query") return "query";
  if (t === "upload") return "upload";
  if (t === "feedback") return "feedback";
  if (t === "login") return "login";
  if (t === "fallback") return "fallback";
  return "query";
}

export const listAuditLogs = (offset = 0, limit = 50, start?: string) => {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  if (start) params.set("start", start);
  return apiFetch<RawAudit[]>(`/admin/audit-logs?${params}`).then((rows) =>
    rows.map(
      (r): AuditEvent => ({
        id: r.id,
        ts: r.timestamp,
        kind: mapKind(r.action_type),
        who: r.user_id,
        query: r.query_text ?? undefined,
        latencyMs: r.latency_ms ?? undefined,
        traceId: r.trace_id ?? undefined,
      }),
    ),
  );
};

export const exportAuditCsv = () =>
  fetch(apiUrl("/admin/audit-logs/export.csv"), { credentials: "include" }).then((r) => r.blob());
