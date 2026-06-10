import { ApiError, apiFetch, apiUrl, csrfHeaders } from "./client";

export type AuditKind = "query" | "upload" | "feedback" | "login" | "fallback" | "admin" | "other";

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
  user_email?: string | null;
  action_type: string;
  kind: AuditKind;
  query_text: string | null;
  latency_ms: number | null;
  trace_id: string | null;
}

export interface AuditKindCounts {
  total: number;
  kinds: Record<AuditKind, number>;
}

export const listAuditLogs = (offset = 0, limit = 50, start?: string, kind?: AuditKind) => {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  if (start) params.set("start", start);
  if (kind) params.set("kind", kind);
  return apiFetch<RawAudit[]>(`/admin/audit-logs?${params}`).then((rows) =>
    rows.map(
      (r): AuditEvent => ({
        id: r.id,
        ts: r.timestamp,
        kind: r.kind,
        who: r.user_email ?? r.user_id,
        query: r.query_text ?? undefined,
        latencyMs: r.latency_ms ?? undefined,
        traceId: r.trace_id ?? undefined,
      }),
    ),
  );
};

export const getAuditKindCounts = (start?: string) => {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  const qs = params.toString();
  return apiFetch<AuditKindCounts>(`/admin/audit-logs/kind-counts${qs ? `?${qs}` : ""}`);
};

export const exportAuditCsv = () =>
  fetch(apiUrl("/admin/audit-logs/export.csv"), {
    credentials: "include",
    headers: csrfHeaders(),
  }).then(async (r) => {
    if (!r.ok) {
      const message = await r.text().catch(() => String(r.status));
      throw new ApiError(r.status, message || "Audit export failed");
    }
    const contentType = r.headers.get("content-type") ?? "";
    if (!contentType.includes("text/csv")) {
      throw new ApiError(r.status, "Audit export did not return CSV");
    }
    return r.blob();
  });
