import { FileText } from "lucide-react";
import { useState } from "react";
import type { SseCite } from "../../api/chat";

interface Props { source: SseCite; compact?: boolean; active?: boolean; onOpen?: () => void }

export default function SourceRow({ source, compact, active, onOpen }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={[
        "rounded-lg transition-colors",
        active ? "bg-accent/8 border border-accent/20" : "",
      ].join(" ")}
    >
      <button
        type="button"
        onClick={() => {
          onOpen?.();
          if (source.excerpt) setExpanded((v) => !v);
        }}
        className={[
          "flex items-start gap-2.5 w-full text-left px-3 py-2.5 hover:bg-surface-2 rounded-lg transition-colors",
          compact ? "py-1.5" : "",
          active ? "rounded-b-none" : "",
        ].join(" ")}
      >
        <FileText size={13} className="text-text-3 mt-0.5 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-[12px] font-medium text-text truncate">{source.file}</p>
          <p className="text-[11px] text-text-3">p. {source.page}</p>
        </div>
        <span className="ml-auto text-[10.5px] font-mono text-text-mute shrink-0">
          {(source.score * 100).toFixed(0)}%
        </span>
      </button>
      {expanded && source.excerpt && (
        <div className="px-3 pb-2.5 pt-0">
          <p className="text-[11px] text-text-2 leading-relaxed border-t border-line pt-2 italic">
            "{source.excerpt}"
          </p>
        </div>
      )}
    </div>
  );
}
