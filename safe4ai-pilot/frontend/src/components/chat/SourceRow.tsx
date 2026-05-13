import { FileText } from "lucide-react";
import type { SseCite } from "../../api/chat";

interface Props { source: SseCite; compact?: boolean; active?: boolean; onOpen?: () => void }

export default function SourceRow({ source, compact, active, onOpen }: Props) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className={[
        "flex items-start gap-2.5 w-full text-left rounded-lg px-3 py-2.5 hover:bg-surface-2 transition-colors",
        compact ? "py-1.5" : "",
        active ? "bg-accent/8 border border-accent/20" : "",
      ].join(" ")}
    >
      <FileText size={13} className="text-text-3 mt-0.5 shrink-0" />
      <div className="min-w-0">
        <p className="text-[12px] font-medium text-text truncate">{source.file}</p>
        <p className="text-[11px] text-text-3">p. {source.page}</p>
      </div>
      <span className="ml-auto text-[10.5px] font-mono text-text-mute">
        {(source.score * 100).toFixed(0)}%
      </span>
    </button>
  );
}
