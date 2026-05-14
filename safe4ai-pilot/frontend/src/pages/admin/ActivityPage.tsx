import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import ActivityEvent from "../../components/admin/ActivityEvent";
import Button from "../../components/Button";
import { exportAuditCsv } from "../../api/audit";
import type { AuditKind } from "../../api/audit";
import { useAuditStream } from "../../hooks/useAuditStream";
import AdminLayout from "./AdminLayout";

const KIND_FILTERS: { label: string; value: AuditKind | "all" }[] = [
  { label: "All",      value: "all" },
  { label: "Query",    value: "query" },
  { label: "Index",    value: "upload" },
  { label: "Feedback", value: "feedback" },
  { label: "Auth",     value: "login" },
  { label: "Fallback", value: "fallback" },
];

const RANGE_FILTERS = ["Last hour", "Today", "Last 7 days", "Last 30 days"];

function rangeToStart(range: string): string | undefined {
  const now = new Date();
  switch (range) {
    case "Last hour":   return new Date(now.getTime() - 60 * 60 * 1000).toISOString();
    case "Today": {
      const startOfDay = new Date(now);
      startOfDay.setHours(0, 0, 0, 0);
      return startOfDay.toISOString();
    }
    case "Last 7 days": return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
    case "Last 30 days":return new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString();
    default:            return undefined;
  }
}

export default function ActivityPage() {
  const [activeKind, setActiveKind] = useState<AuditKind | "all">("all");
  const [activeRange, setActiveRange] = useState("Today");
  const { events, isLoading, page, setPage, limit } = useAuditStream(rangeToStart(activeRange));

  useEffect(() => {
    setPage(0);
  }, [activeRange, setPage]);

  const filtered = activeKind === "all" ? events : events.filter((e) => e.kind === activeKind);

  const todayFormatted = new Date().toLocaleDateString("en-US", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  });

  async function handleExport() {
    const blob = await exportAuditCsv();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <AdminLayout>
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-line bg-surface shrink-0">
        <div>
          <h1 className="text-[19px] font-medium text-ink">Activity</h1>
          <p className="text-[12px] text-text-3 mt-0.5">A continuous record of every query, retrieval and admin action.</p>
        </div>
        <Button variant="ghost" size="sm" iconLeft={<Download size={13} />} onClick={handleExport}>
          Export CSV
        </Button>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Filter rail */}
        <aside className="w-[200px] shrink-0 border-r border-line flex flex-col overflow-y-auto py-4 px-3">
          <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-1.5 px-1">Kind</p>
          <div className="flex flex-col gap-0.5 mb-4">
            {KIND_FILTERS.map(({ label, value }) => {
              const count = value === "all" ? events.length : events.filter((e) => e.kind === value).length;
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => setActiveKind(value)}
                  className={[
                    "flex items-center h-7 px-2 rounded-md text-[13px] w-full transition-colors",
                    activeKind === value
                      ? "bg-[#f4f1ea] text-text font-medium"
                      : "text-text-2 hover:bg-surface",
                  ].join(" ")}
                >
                  <span className="flex-1 text-left">{label}</span>
                  <span className="font-mono text-[11px] text-text-3">{count}</span>
                </button>
              );
            })}
          </div>

          <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-1.5 px-1">Range</p>
          <div className="flex flex-col gap-0.5 mb-4">
            {RANGE_FILTERS.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setActiveRange(r)}
                className={[
                  "flex items-center h-7 px-2 rounded-md text-[13px] w-full text-left transition-colors",
                  activeRange === r
                    ? "bg-[#f4f1ea] text-text font-medium"
                    : "text-text-2 hover:bg-surface",
                ].join(" ")}
              >
                {r}
              </button>
            ))}
          </div>

          <div className="mt-auto bg-[#f4f1ea] rounded-md p-3 font-mono text-[11px] text-text-3 leading-relaxed">
            <p className="font-medium text-ink text-[10.5px] uppercase tracking-[0.06em] mb-1.5">Retention</p>
            All audit events retained <b className="text-text">365 days</b>, then archived to immutable storage.
          </div>
        </aside>

        {/* Event stream */}
        <div className="flex-1 overflow-y-auto">
          <div className="px-7 pb-6">
            {/* Sticky date header */}
            <div className="sticky top-0 z-10 bg-paper flex items-baseline gap-3 py-4 border-b border-line mb-1">
              <h2 className="font-serif text-[22px] italic text-ink">Today</h2>
              <span className="font-mono text-[11.5px] text-text-3">{todayFormatted}</span>
              <span className="flex-1" />
              <span className="font-mono text-[11.5px] text-text-3 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[#3b6cf2] animate-pulse shrink-0" />
                live
              </span>
            </div>

            <div className="flex items-center justify-between py-3 mb-1 font-mono text-[11.5px] text-text-3">
              <span>Page {page + 1}</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="h-7 px-2.5 rounded border border-line bg-surface text-text-2 disabled:opacity-40 hover:bg-surface-2 transition-colors"
                >
                  Newer
                </button>
                <button
                  type="button"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={events.length < limit}
                  className="h-7 px-2.5 rounded border border-line bg-surface text-text-2 disabled:opacity-40 hover:bg-surface-2 transition-colors"
                >
                  Older
                </button>
              </div>
            </div>

            {isLoading ? (
              <div className="py-8 text-center text-[13px] text-text-mute">Loading…</div>
            ) : filtered.length === 0 ? (
              <div className="py-8 text-center text-[13px] text-text-mute">No events yet.</div>
            ) : (
              <div className="relative pl-[18px] mt-1">
                <span className="absolute left-[4px] top-[18px] bottom-3 w-px bg-line" aria-hidden />
                {filtered.map((ev) => (
                  <ActivityEvent key={ev.id} event={ev} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
