import { Loader2, RefreshCw, Trash2 } from "lucide-react";
import type { DocumentRecord } from "../../api/documents";
import Chip from "../Chip";

const DOC_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  PDF:  { bg: "#fef0ec", text: "#c0392b", label: "PDF" },
  DOCX: { bg: "#eaf0ff", text: "#1d3fa6", label: "DOCX" },
  XLSX: { bg: "#e6f3ec", text: "#1f6e45", label: "XLSX" },
  TXT:  { bg: "#f7f5f0", text: "#4a4f57", label: "TXT" },
};

const statusTone = {
  indexed:   "success",
  embedding: "accent",
  queued:    "neutral",
  failed:    "danger",
  skipped:   "warn",
} as const;

interface Props {
  doc: DocumentRecord;
  selected?: boolean;
  onSelect?: () => void;
  onReindex?: () => void;
  onDelete?: () => void;
}

export default function DocumentRow({ doc, selected, onSelect, onReindex, onDelete }: Props) {
  const badge = DOC_BADGE[doc.type] ?? DOC_BADGE.TXT;

  return (
    <div
      onClick={onSelect}
      className={[
        "group grid px-3 py-3 border-b border-line cursor-pointer hover:bg-surface-2 transition-colors items-center",
        selected ? "bg-[rgba(59,108,242,.025)]" : "",
      ].join(" ")}
      style={{ gridTemplateColumns: "minmax(0,2fr) 80px 90px 90px 1fr 60px", gap: 12 }}
    >
      {/* Name + icon */}
      <div className="flex items-center gap-2.5 min-w-0">
        <div
          className="w-[26px] h-8 rounded border border-line flex items-center justify-center shrink-0"
          style={{ background: badge.bg }}
        >
          <span className="text-[9px] font-bold leading-none" style={{ color: badge.text }}>{badge.label}</span>
        </div>
        <div className="min-w-0">
          <p className="text-[13px] font-medium text-text truncate">{doc.name}</p>
          {doc.note && (
            <p className="font-mono text-[11px] text-text-3 mt-0.5 truncate">{doc.note}</p>
          )}
        </div>
      </div>

      {/* Type */}
      <span className="font-mono text-[11.5px] text-text-3">{doc.type}</span>

      {/* Chunks */}
      <span className="font-mono text-[12px] text-text-2 tabular-nums">{doc.chunks.toLocaleString()}</span>

      {/* Size */}
      <span className="font-mono text-[11.5px] text-text-3">{doc.size}</span>

      {/* Status */}
      <div className="flex items-center gap-2 min-w-0">
        {doc.status === "embedding" ? (
          <div className="flex items-center gap-1.5">
            <Loader2 size={11} className="animate-spin text-accent shrink-0" />
            <span className="font-mono text-[11px] text-accent">indexing…</span>
          </div>
        ) : doc.status === "queued" ? (
          <div className="flex items-center gap-1.5">
            <Loader2 size={11} className="animate-spin text-text-3 shrink-0" />
            <span className="font-mono text-[11px] text-text-3">queued…</span>
          </div>
        ) : (
          <Chip tone={statusTone[doc.status] ?? "neutral"} variant="default">
            {doc.status}
          </Chip>
        )}
        <span className="font-mono text-[11px] text-text-3 truncate">
          {new Date(doc.addedAt).toLocaleDateString()} · {doc.addedBy}
        </span>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end gap-1">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onReindex?.();
          }}
          className="p-1 rounded hover:bg-surface-2 text-text-mute opacity-0 group-hover:opacity-100 transition-opacity"
          title="Reindex document"
          aria-label="Reindex document"
        >
          <RefreshCw size={12} />
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete?.();
          }}
          className="p-1 rounded hover:bg-surface-2 text-text-mute opacity-0 group-hover:opacity-100 transition-opacity"
          title="Delete document"
          aria-label="Delete document"
        >
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  );
}
