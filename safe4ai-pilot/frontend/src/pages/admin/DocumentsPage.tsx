import { Loader2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Button from "../../components/Button";
import Chip from "../../components/Chip";
import DocumentRow from "../../components/admin/DocumentRow";
import { inspectDocument } from "../../api/documents";
import { useDocuments } from "../../hooks/useDocuments";
import AdminLayout from "./AdminLayout";

const statusTone = {
  indexed:   "success",
  embedding: "accent",
  queued:    "neutral",
  failed:    "danger",
  skipped:   "warn",
} as const;

export default function DocumentsPage() {
  const { docs, isLoading, isUploading, upload, remove, reindex, uploadError, clearUploadError } = useDocuments();
  const [selected, setSelected] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedDoc = docs.find((d) => d.id === selected) ?? null;
  const isReindexing = selectedDoc !== null &&
    (selectedDoc.status === "queued" || selectedDoc.status === "embedding");

  const { data: inspection } = useQuery({
    queryKey: ["document-inspect", selected],
    queryFn: () => inspectDocument(selected as string),
    enabled: selected !== null,
    staleTime: 15_000,
  });

  async function handleFiles(files: FileList | null) {
    if (!files) return;
    await Promise.allSettled(Array.from(files).map((file) => upload(file)));
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  }

  return (
    <AdminLayout>
      {uploadError && (
        <div className="mx-6 mt-4 rounded-lg border border-danger/30 bg-danger-soft px-4 py-2.5 text-[12.5px] text-danger flex items-center justify-between gap-3">
          <span>{uploadError}</span>
          <button
            type="button"
            onClick={clearUploadError}
            className="shrink-0 text-danger/60 hover:text-danger transition-colors leading-none"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-line bg-surface shrink-0">
        <div>
          <h1 className="text-[19px] font-medium text-ink">Documents</h1>
          <p className="text-[12px] text-text-3 mt-0.5">{docs.length} document{docs.length !== 1 ? "s" : ""} in index</p>
        </div>
        <Button
          variant="primary"
          size="sm"
          iconLeft={<Upload size={13} />}
          onClick={() => inputRef.current?.click()}
          disabled={isUploading}>
          {isUploading ? "Uploading…" : "Upload"}
        </Button>
        <input
          ref={inputRef}
          type="file"
          aria-label="Upload documents"
          className="hidden"
          multiple
          accept=".pdf,.docx,.xlsx,.txt"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Left: list */}
        <div className="flex-1 overflow-y-auto">
          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={[
              "mx-6 my-4 rounded-xl border-2 border-dashed flex items-center gap-4 px-5 py-4 transition-colors",
              dragging ? "border-accent bg-accent/5" : "border-line",
            ].join(" ")}
          >
            <div className="size-[38px] rounded-[9px] bg-[#eaf0ff] flex items-center justify-center shrink-0">
              <Upload size={16} className="text-[#1d3fa6]" />
            </div>
            <div className="flex-1">
              <p className="text-[13px] font-medium text-ink mb-0.5">Drop PDFs, DOCX or TXT here</p>
              <p className="text-[12px] text-text-2">
                Files are chunked, embedded and indexed within ~30s.{" "}
                <button
                  type="button"
                  className="text-[#3b6cf2]"
                  onClick={() => inputRef.current?.click()}
                  aria-label="Browse files to upload"
                >
                  Browse
                </button>
              </p>
            </div>
          </div>

          {isLoading ? (
            <div className="px-6 py-8 text-center text-[13px] text-text-mute">Loading…</div>
          ) : docs.length === 0 ? (
            <div className="px-6 py-8 text-center text-[13px] text-text-mute">No documents yet. Upload one above.</div>
          ) : (
            <div className="mx-6 mb-6 border border-line rounded-xl overflow-hidden">
              {/* Table header */}
              <div
                className="grid px-3 py-2 border-b border-line bg-surface-2 font-mono text-[10.5px] font-medium text-text-3 uppercase"
                style={{ gridTemplateColumns: "minmax(0,2fr) 80px 90px 90px 1fr 60px", gap: 12 }}
              >
                <span>Name</span>
                <span>Type</span>
                <span>Chunks</span>
                <span>Size</span>
                <span>Status · added by</span>
                <span />
              </div>
              {docs.map((doc) => (
                <DocumentRow
                  key={doc.id}
                  doc={doc}
                  selected={selected === doc.id}
                  onSelect={() => setSelected(doc.id === selected ? null : doc.id)}
                  onReindex={() => reindex(doc.id)}
                  onDelete={() => setConfirmDelete(doc.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Right: inspector */}
        {selectedDoc && (
          <aside className="w-[320px] shrink-0 border-l border-line bg-surface-2 flex flex-col">
            <div className="px-[18px] py-4">
              <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-1">selected</p>
              <p className="text-[13.5px] font-medium text-ink mb-1 break-all leading-snug">{selectedDoc.name}</p>
              <p className="font-mono text-[11.5px] text-text-3">
                {selectedDoc.chunks.toLocaleString()} chunks · {selectedDoc.size}
              </p>
            </div>
            <hr className="border-line" />

            <div className="px-[18px] py-4">
              <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-2">indexing</p>
              <div className="grid grid-cols-2 gap-2">
                {[
                  ["chunks",   selectedDoc.chunks.toLocaleString()],
                  ["size",     selectedDoc.size],
                  ["type",     selectedDoc.type],
                  ["status",   selectedDoc.status],
                ].map(([k, v]) => (
                  <div key={k} className="bg-surface rounded-md p-2.5">
                    <p className="font-mono text-[10px] uppercase tracking-[0.06em] text-text-3 mb-1">{k}</p>
                    <p className="font-mono text-[13px] font-medium text-ink">{v}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="px-[18px] pb-4">
              <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-2">added</p>
              <p className="font-mono text-[11.5px] text-text-3">
                {new Date(selectedDoc.addedAt).toLocaleString()} · {selectedDoc.addedBy}
              </p>
            </div>

            {inspection && inspection.chunks.length > 0 && (
              <div className="px-[18px] pb-4">
                <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-2">
                  chunk sample · {inspection.chunk_count} total
                </p>
                <div className="flex flex-col gap-1.5 max-h-[180px] overflow-y-auto">
                  {inspection.chunks.map((c) => (
                    <div key={c.chunk_index} className="bg-surface rounded-md p-2">
                      <p className="font-mono text-[10px] text-text-3 mb-0.5">
                        #{c.chunk_index} · v{c.chunk_version} · {c.indexed ? "indexed" : "not indexed"}
                      </p>
                      <p className="text-[11px] text-text-2 leading-snug line-clamp-2">
                        {c.content_preview ?? "—"}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {inspection && inspection.jobs.length > 0 && (
              <div className="px-[18px] pb-4">
                <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-2">
                  ingestion history
                </p>
                <div className="flex flex-col gap-1">
                  {inspection.jobs.map((j, i) => (
                    <p key={i} className="font-mono text-[10.5px] text-text-3 leading-relaxed">
                      {j.created_at ? new Date(j.created_at).toLocaleString() : "—"} · {j.status}
                      {j.error ? ` · ${j.error}` : ""}
                    </p>
                  ))}
                </div>
              </div>
            )}

            <div className="px-[18px] pb-4">
              <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-1.5">status</p>
              {selectedDoc.status === "embedding" ? (
                <div className="flex items-center gap-1.5">
                  <Loader2 size={11} className="animate-spin text-accent shrink-0" />
                  <span className="font-mono text-[11px] text-accent">indexing…</span>
                </div>
              ) : selectedDoc.status === "queued" ? (
                <div className="flex items-center gap-1.5">
                  <Loader2 size={11} className="animate-spin text-text-3 shrink-0" />
                  <span className="font-mono text-[11px] text-text-3">queued…</span>
                </div>
              ) : (
                <Chip tone={statusTone[selectedDoc.status] ?? "neutral"} variant="default">
                  {selectedDoc.status}
                </Chip>
              )}
            </div>

            <div className="flex-1" />

            <div className="border-t border-line px-[14px] py-2.5 flex gap-1.5">
              <button
                type="button"
                onClick={() => reindex(selectedDoc.id)}
                disabled={isReindexing}
                className="flex-1 h-[26px] px-[9px] text-[12px] font-medium text-text-2 border border-line bg-surface rounded-[5px] hover:bg-surface-2 transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isReindexing && <Loader2 size={11} className="animate-spin shrink-0" />}
                {isReindexing ? "Working…" : "Reindex"}
              </button>
              <button
                type="button"
                onClick={() => setConfirmDelete(selectedDoc.id)}
                className="flex-1 h-[26px] px-[9px] text-[12px] font-medium text-[#c0392b] border border-line bg-surface rounded-[5px] hover:bg-[#fbe9e6] transition-colors"
              >
                Delete
              </button>
            </div>
          </aside>
        )}
      </div>

      {confirmDelete && (() => {
        const target = docs.find((d) => d.id === confirmDelete);
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30">
            <div className="bg-paper rounded-xl border border-line shadow-lg p-6 max-w-[360px] w-full mx-4">
              <p className="text-[14px] font-medium text-ink mb-1">Delete document?</p>
              <p className="text-[12.5px] text-text-2 mb-5">
                <b>{target?.name}</b> will be removed from the index and cannot be recovered.
              </p>
              <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setConfirmDelete(null)}
                className="h-[30px] px-3.5 text-[12.5px] rounded border border-line text-text-2 hover:bg-surface-2 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  remove(confirmDelete);
                  if (selected === confirmDelete) setSelected(null);
                  setConfirmDelete(null);
                }}
                  className="h-[30px] px-3.5 text-[12.5px] rounded bg-danger text-white hover:bg-danger/90 transition-colors"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </AdminLayout>
  );
}
