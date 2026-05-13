import { ThumbsUp } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
import { getStats } from "../../api/stats";
import { listFeedback } from "../../api/feedback";
import AdminLayout from "./AdminLayout";

function Stat({ value, unit, color }: { value: string | number; unit?: string; color?: string }) {
  return (
    <span className="inline-flex items-baseline gap-1 bg-paper-2 rounded px-2 py-0.5 mx-0.5 align-[1px]">
      <b className="font-mono font-medium text-[16px] leading-none tabular-nums" style={{ color: color ?? "var(--ink)" }}>
        {value}
      </b>
      {unit && <span className="font-mono text-[11px] text-text-3">{unit}</span>}
    </span>
  );
}

export default function OverviewPage() {
  const { data: stats, isLoading, isError, error } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
    refetchInterval: 60_000,
  });

  const { data: feedbackItems = [] } = useQuery({
    queryKey: ["feedback"],
    queryFn: listFeedback,
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return (
      <AdminLayout>
        <div className="flex-1 flex items-center justify-center text-[13px] text-text-mute">Loading…</div>
      </AdminLayout>
    );
  }

  if (isError || !stats) {
    return (
      <AdminLayout>
        <div className="flex-1 flex items-center justify-center bg-paper">
          <div className="text-center">
            <AlertCircle className="w-6 h-6 text-danger mx-auto mb-2" strokeWidth={1.5} />
            <p className="text-[13px] text-danger font-mono mb-1">Failed to load overview</p>
            <p className="text-[12px] text-text-3 font-mono max-w-sm">
              {error instanceof Error ? error.message : "The dashboard could not fetch stats."}
            </p>
          </div>
        </div>
      </AdminLayout>
    );
  }

  const generatedAt = new Date(stats.generatedAt);
  const displayAt = Number.isNaN(generatedAt.getTime()) ? new Date() : generatedAt;
  const dateStr = displayAt.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
  const timeStr = displayAt.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
  const avgLatency =
    stats.latency.avgMs == null ? (
      <span className="font-mono text-[12px] text-text-3">not available</span>
    ) : (
      <Stat value={stats.latency.avgMs} unit="ms" />
    );

  const up = feedbackItems.filter((i) => i.rating === "up").length;
  const down = feedbackItems.filter((i) => i.rating === "down").length;
  const total = up + down;
  const pct = total > 0 ? Math.round((up / total) * 100) : 0;
  const ratio = down > 0 ? (up / down).toFixed(1) : "—";

  const avgCostPerQuery =
    stats.queries.total > 0 ? `$${(stats.cost.totalUsd / stats.queries.total).toFixed(4)}` : "—";

  const recentNegative = feedbackItems
    .filter((i) => i.rating === "down")
    .slice(0, 3);

  return (
    <AdminLayout>
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[760px] mx-auto px-7 py-8 pb-12">

          {/* Header */}
          <div className="mb-6">
            <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-1.5">summary</p>
            <h1 className="font-serif text-[19px] text-ink" style={{ letterSpacing: "-0.005em" }}>Today's briefing</h1>
            <p className="text-[12px] text-text-3 mt-0.5 font-mono">
              {dateStr} — generated at {timeStr}, refreshes every minute.
            </p>
          </div>

          {/* Narrative */}
          <p className="text-[14.5px] leading-[1.7] text-text mb-7" style={{ letterSpacing: "-0.005em" }}>
            The pilot processed{" "}
            <Stat value={stats.queries.total.toLocaleString()} />{" "}
            queries this period, with an average latency of{" "}
            {avgLatency}.
            The semantic cache absorbed{" "}
            <Stat value={stats.cacheTotalHits} />{" "}
            LLM calls. Total infrastructure cost:{" "}
            <Stat value={"$" + stats.cost.totalUsd.toFixed(4)} />.
          </p>

          {/* Traffic section */}
          <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-2.5">traffic</p>
          <div className="grid grid-cols-3 gap-3 mb-8">
            {[
              { label: "Total queries",    value: stats.queries.total.toLocaleString() },
              { label: "Active users",     value: stats.uniqueUsers.toString() },
              { label: "Avg cost / query", value: avgCostPerQuery },
            ].map((s) => (
              <div key={s.label} className="bg-surface border border-line rounded-lg p-3.5">
                <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-1.5">{s.label}</p>
                <span className="font-mono text-[22px] font-medium text-ink leading-none tabular-nums">{s.value}</span>
              </div>
            ))}
          </div>

          {/* Quality section */}
          <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-2.5">quality</p>
          <div className="bg-surface border border-line rounded-lg p-3.5 mb-8">
            <div className="flex items-center gap-2.5 mb-2.5">
              <ThumbsUp size={12} className="text-text-3 shrink-0" />
              <span className="text-[12px] font-medium text-ink flex-1">{up} helpful · {down} not helpful</span>
              <span className="font-mono text-[11px] text-text-3">{ratio} : 1</span>
            </div>
            <div className="h-2 rounded-full overflow-hidden flex" style={{ background: "var(--paper-2, #f4f1ea)" }}>
              <div style={{ width: `${pct}%`, background: "#2f8f5e" }} />
              <div style={{ width: `${100 - pct}%`, background: "#c0392b" }} />
            </div>
          </div>

          {/* Notable items — driven by real negative feedback */}
          <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-2.5">worth a look</p>
          <div className="flex flex-col gap-2.5 mb-8">
            {recentNegative.length === 0 ? (
              <div className="bg-surface border border-line rounded-lg p-3.5 text-center">
                <p className="text-[12.5px] text-text-mute">No negative feedback in this period.</p>
              </div>
            ) : (
              recentNegative.map((item) => (
                <div key={item.id} className="bg-surface border border-line rounded-lg p-3.5 grid gap-3.5 items-start"
                  style={{ gridTemplateColumns: "70px 1fr" }}>
                  <span className="font-mono text-[9.5px] font-medium pt-0.5 leading-tight"
                    style={{ color: "#c0392b", letterSpacing: "0.06em" }}>
                    FEEDBACK
                  </span>
                  <div>
                    <p className="text-[13.5px] font-medium text-ink mb-1 leading-snug" style={{ letterSpacing: "-0.005em" }}>
                      Negative feedback received
                    </p>
                    {item.note && (
                      <p className="text-[12.5px] text-text-2 leading-relaxed truncate">"{item.note}"</p>
                    )}
                    {!item.note && (
                      <p className="text-[12.5px] text-text-2 leading-relaxed truncate">
                        Trace {item.traceId || "unavailable"} · user {item.userId}
                      </p>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Cost section */}
          <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-2.5">cost</p>
          <p className="text-[14.5px] leading-[1.7] text-text" style={{ letterSpacing: "-0.005em" }}>
            Total infrastructure spend this period:{" "}
            <Stat value={"$" + stats.cost.totalUsd.toFixed(4)} />.
          </p>
        </div>
      </div>
    </AdminLayout>
  );
}
