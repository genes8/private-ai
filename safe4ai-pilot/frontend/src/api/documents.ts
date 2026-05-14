import { apiFetch, apiUrl, csrfHeaders } from "./client";

export type DocStatus = "indexed" | "embedding" | "skipped" | "failed" | "queued";
export type DocType   = "PDF" | "DOCX" | "XLSX" | "TXT";

export interface DocumentRecord {
  id: string;
  name: string;
  type: DocType;
  size: string;
  bytes: number;
  chunks: number;
  status: DocStatus;
  progress?: number;
  addedAt: string;
  addedBy: string;
  note?: string;
}

interface RawDoc {
  id: string;
  filename: string;
  file_type: string;
  ingestion_status: string;
  uploaded_at: string;
  chunk_count: number;
  file_size_bytes: number | null;
}

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === undefined || bytes <= 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let idx = 0;
  let size = bytes;
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024;
    idx++;
  }
  return `${size.toFixed(1)} ${units[idx]}`;
}

function mapDoc(r: RawDoc): DocumentRecord {
  return {
    id: r.id,
    name: r.filename,
    type: (r.file_type?.toUpperCase() as DocType) ?? "PDF",
    size: formatBytes(r.file_size_bytes),
    bytes: r.file_size_bytes ?? 0,
    chunks: r.chunk_count,
    status: r.ingestion_status as DocStatus,
    addedAt: r.uploaded_at,
    addedBy: "—",
  };
}

export const listDocuments = () =>
  apiFetch<RawDoc[]>("/admin/documents").then((rows) => rows.map(mapDoc));

export const getDocumentStatus = (id: string) =>
  apiFetch<{ id: string; ingestion_status: string }>(`/admin/documents/${id}/status`);

export const uploadDocument = async (file: File): Promise<{ id: string }> => {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(apiUrl("/admin/documents/upload"), {
    method: "POST",
    credentials: "include",
    headers: csrfHeaders(),
    body: fd,
  });
  if (!res.ok) throw new Error(await res.text());
  const body = await res.json() as { doc_id: string; job_id: string };
  return { id: body.doc_id };
};

export const deleteDocument = (id: string) =>
  apiFetch<void>(`/admin/documents/${id}`, { method: "DELETE" });

export const reindexDocument = (id: string) =>
  apiFetch<{ job_id: string }>(`/admin/documents/${id}/reindex`, { method: "POST" });
