import { Copy, ThumbsDown, ThumbsUp } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { SseCite } from "../../api/chat";
import Logo from "../Logo";
import CitationChip from "./CitationChip";
import TrustSignal from "./TrustSignal";

interface Trust { latencyMs: number; cacheHit: boolean; model: string; kRetrieved: number }

interface Props {
  body: string;
  sources: SseCite[];
  trust: Trust;
  onCopy?: () => void;
  onRate?: (rating: "up" | "down") => void;
  onCitationOpen?: (id: string) => void;
  isStreaming?: boolean;
  rated?: "up" | "down";
}

function LiveTimer() {
  const [secs, setSecs] = useState(0);
  const startRef = useRef(Date.now());

  useEffect(() => {
    const id = setInterval(() => {
      setSecs(Math.floor((Date.now() - startRef.current) / 1000));
    }, 250);
    return () => clearInterval(id);
  }, []);

  return (
    <span className="inline-flex items-center gap-2 font-mono text-[11px] text-text-3">
      <span className="font-medium text-text-2">{secs}s</span>
      <span className="text-text-mute">·</span>
      <span className="text-text-mute">thinking…</span>
    </span>
  );
}

function AnswerWithCitations({
  body,
  onOpen,
  activeId,
}: {
  body: string;
  onOpen: (id: string) => void;
  activeId: string | null;
}) {
  const parts = body.split(/(\[\d+\])/g);
  let offset = 0;
  return (
    <>
      {parts.map((part) => {
    const partOffset = offset;
    offset += part.length;
    const m = part.match(/^\[(\d+)\]$/);
    if (m) {
      return <CitationChip key={`cite-${m[1]}-${partOffset}`} id={m[1]} active={activeId === m[1]} onOpen={onOpen} />;
    }
    return <span key={`text-${partOffset}`}>{part}</span>;
  })}
    </>
  );
}

export default function AnswerBlock({ body, sources, trust, onCopy, onRate, onCitationOpen, isStreaming, rated }: Props) {
  const [activeId, setActiveId] = useState<string | null>(null);

  function handleCiteOpen(id: string) {
    setActiveId((prev) => (prev === id ? null : id));
    onCitationOpen?.(id);
  }

  return (
    <div className="grid items-start gap-3" style={{ gridTemplateColumns: "28px 1fr" }}>
      <div className="size-7 rounded-[7px] bg-ink flex items-center justify-center shrink-0 mt-0.5">
        <Logo size={16} />
      </div>
      <div className="space-y-2 min-w-0">
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-semibold text-ink tracking-tight">private·ai</span>
          {isStreaming ? <LiveTimer /> : <TrustSignal {...trust} />}
        </div>

        <p className="text-[14.5px] leading-relaxed tracking-body text-text whitespace-pre-wrap">
          <AnswerWithCitations body={body} onOpen={handleCiteOpen} activeId={activeId} />
          {isStreaming && <span className="inline-block w-0.5 h-3.5 bg-text animate-pulse ml-0.5" />}
        </p>

        {sources.length > 0 && !isStreaming && (
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {sources.map((s) => (
              <button
                type="button"
                key={s.id}
                onClick={() => handleCiteOpen(s.id)}
                className={[
                  "flex items-center gap-1.5 rounded-lg border px-2 py-1 text-[11.5px] transition-colors",
                  activeId === s.id
                    ? "border-accent/40 bg-accent-tint text-accent"
                    : "border-line bg-surface-2 text-text-3 hover:border-accent/30 hover:text-text-2",
                ].join(" ")}
              >
                <span className="font-medium">[{s.id}]</span>
                <span className="truncate max-w-[140px]">{s.file}</span>
                <span className="text-text-mute">p.{s.page}</span>
              </button>
            ))}
          </div>
        )}

        {!isStreaming && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onCopy}
              className="p-1.5 rounded hover:bg-surface-2 text-text-mute hover:text-text-3 transition-colors"
              title="Copy"
            >
              <Copy size={13} />
            </button>
            <button
              type="button"
              onClick={() => onRate?.("up")}
              aria-pressed={rated === "up"}
              className={["p-1.5 rounded transition-colors", rated === "up" ? "text-success" : "text-text-mute hover:text-success hover:bg-success-soft"].join(" ")}
              title="Helpful"
            >
              <ThumbsUp size={13} />
            </button>
            <button
              type="button"
              onClick={() => onRate?.("down")}
              aria-pressed={rated === "down"}
              className={["p-1.5 rounded transition-colors", rated === "down" ? "text-danger" : "text-text-mute hover:text-danger hover:bg-danger-soft"].join(" ")}
              title="Not helpful"
            >
              <ThumbsDown size={13} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
