import type { AuditEvent } from "../../api/audit";

const KIND_BADGE: Record<string, { label: string; bg: string; text: string }> = {
  query:    { label: "QUERY",    bg: "var(--paper-2)", text: "var(--text)" },
  upload:   { label: "INDEX",    bg: "#e6f3ec",        text: "#1f6e45" },
  feedback: { label: "FEEDBACK", bg: "#f9efd9",        text: "#8b5a16" },
  login:    { label: "AUTH",     bg: "#e6f3ec",        text: "#1f6e45" },
  fallback: { label: "FALLBACK", bg: "#fbe9e6",        text: "#8c2a20" },
  admin:    { label: "ADMIN",    bg: "#e9ecf7",        text: "#2e3f8f" },
  other:    { label: "OTHER",    bg: "var(--paper-2)", text: "var(--text-2)" },
};

const NODE_COLOR: Record<string, string> = {
  query:    "var(--ink)",
  upload:   "var(--blue, #3b6cf2)",
  feedback: "var(--amber, #b87a1a)",
  fallback: "var(--red, #c0392b)",
  login:    "var(--green, #2f8f5e)",
  admin:    "var(--blue, #3b6cf2)",
  other:    "var(--text-3)",
};

interface Props { event: AuditEvent }

export default function ActivityEvent({ event }: Props) {
  const time = new Date(event.ts).toLocaleTimeString([], {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
  const badge = KIND_BADGE[event.kind] ?? KIND_BADGE.query;
  const nodeColor = NODE_COLOR[event.kind] ?? "var(--ink)";

  return (
    <div className="relative py-4 border-b border-line">
      {/* Timeline node dot */}
      <span
        className="absolute bg-surface border-2 rounded-full"
        style={{
          left: -18, top: 22,
          width: 9, height: 9,
          borderColor: nodeColor,
        }}
        aria-hidden
      />

      <div className="grid gap-[18px]" style={{ gridTemplateColumns: "70px 1fr" }}>
        {/* Time */}
        <span className="font-mono text-[11.5px] text-text-3 pt-0.5 leading-tight">{time}</span>

        <div className="min-w-0">
          {/* Meta line */}
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <span
              className="font-mono text-[9.5px] font-medium tracking-kicker rounded-[3px] px-1.5 py-0.5 shrink-0"
              style={{ background: badge.bg, color: badge.text }}
            >
              {badge.label}
            </span>
            <span className="text-[12.5px] font-medium text-ink">{event.who}</span>
            <span className="flex-1" />
            {event.kind === "query" && event.latencyMs != null && (
              <span className="font-mono text-[10.5px] text-text-3 flex items-center gap-2">
                <b className="text-text-2 font-medium">{event.latencyMs}ms</b>
                <span style={{ color: "var(--line-3)" }}>·</span>
                <span>fresh</span>
              </span>
            )}
          </div>

          {/* Content */}
          {event.query && (
            <div className="text-[13.5px] text-text leading-relaxed line-clamp-2 mb-1" style={{ letterSpacing: "-0.005em" }}>
              "{event.query}"
            </div>
          )}

          {/* Trace footer */}
          {event.traceId && (
            <div className="font-mono text-[10.5px] text-text-3 mt-2">
              trace · {event.traceId}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
