import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useState } from "react";
import Avatar from "../../components/Avatar";
import Chip from "../../components/Chip";
import FeedbackListItem from "../../components/admin/FeedbackListItem";
import { listFeedback } from "../../api/feedback";
import AdminLayout from "./AdminLayout";

function displayName(userEmail: string | undefined, userId: string): string {
  if (!userEmail) return `User ${userId.slice(0, 8)}`;
  const [local] = userEmail.split("@");
  return local
    .split(/[._-]/)
    .filter(Boolean)
    .map((part) => part[0]!.toUpperCase() + part.slice(1))
    .join(" ");
}

export default function FeedbackPage() {
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["feedback"],
    queryFn: listFeedback,
    refetchInterval: 30_000,
  });
  const [filter, setFilter] = useState<"all" | "up" | "down">("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const filtered = items.filter((i) => filter === "all" || i.rating === filter);
  const selected = filtered.find((i) => i.id === selectedId) ?? null;
  const selectedIdx = filtered.findIndex((i) => i.id === selectedId);

  function prev() {
    if (selectedIdx > 0) setSelectedId(filtered[selectedIdx - 1].id);
  }
  function next() {
    if (selectedIdx < filtered.length - 1) setSelectedId(filtered[selectedIdx + 1].id);
  }

  return (
    <AdminLayout>
      <div className="flex items-center justify-between px-6 py-4 border-b border-line bg-surface shrink-0">
        <div>
          <h1 className="text-[19px] font-medium text-ink">Feedback</h1>
          <p className="text-[12px] text-text-3 mt-0.5">{items.length} responses</p>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* List */}
        <div className="w-80 shrink-0 border-r border-line flex flex-col">
          <div className="flex gap-1 px-4 py-2 border-b border-line shrink-0">
            {([ ["all", "All"], ["up", "👍"], ["down", "👎"] ] as const).map(([v, label]) => (
              <button
                key={v}
                type="button"
                onClick={() => setFilter(v)}
                className={["px-2 py-0.5 rounded text-[11.5px] transition-colors", filter === v ? "bg-surface-2 text-text font-medium" : "text-text-mute hover:text-text-2"].join(" ")}
              >
                {label}{" "}
                <span className="text-text-mute text-[10.5px]">
                  {v === "all" ? items.length : items.filter((i) => i.rating === v).length}
                </span>
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-y-auto">
            {isLoading ? (
              <div className="px-4 py-8 text-center text-[13px] text-text-mute">Loading…</div>
            ) : filtered.length === 0 ? (
              <div className="px-4 py-8 text-center text-[13px] text-text-mute">No feedback yet.</div>
            ) : (
              filtered.map((item) => (
                <FeedbackListItem
                  key={item.id}
                  item={item}
                  active={selectedId === item.id}
                  onSelect={() => setSelectedId(item.id)}
                />
              ))
            )}
          </div>
        </div>

        {/* Detail */}
        {selected ? (
          <div className="flex-1 overflow-y-auto">
            <div className="px-8 py-6 max-w-[760px]">
              {/* Header row */}
              <div className="flex items-center gap-2.5 mb-5">
                <Chip tone={selected.rating === "up" ? "success" : "danger"} variant="default">
                  {selected.rating === "up" ? "thumbs up" : "thumbs down"}
                </Chip>
                <span className="font-mono text-[11.5px] text-text-3">
                  {selected.traceId ? `trace · ${selected.traceId} · ` : ""}{new Date(selected.ts).toLocaleString()}
                </span>
                <span className="flex-1" />
                <button
                  type="button"
                  onClick={prev}
                  disabled={selectedIdx <= 0}
                  className="p-1 rounded hover:bg-surface-2 disabled:opacity-30"
                  aria-label="Previous feedback"
                >
                  <ChevronLeft size={14} />
                </button>
                <button
                  type="button"
                  onClick={next}
                  disabled={selectedIdx >= filtered.length - 1}
                  className="p-1 rounded hover:bg-surface-2 disabled:opacity-30"
                  aria-label="Next feedback"
                >
                  <ChevronRight size={14} />
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedId(null)}
                  className="p-1 rounded hover:bg-surface-2 ml-1"
                  aria-label="Close details"
                >
                  <X size={14} />
                </button>
              </div>

              {/* Reporter */}
              <div className="flex items-center gap-2.5 mb-5">
                <Avatar name={displayName(selected.userEmail, selected.userId)} size={28} />
                <div>
                  <p className="text-[13.5px] font-medium text-ink">
                    {displayName(selected.userEmail, selected.userId)}
                  </p>
                  <p className="font-mono text-[11.5px] text-text-3">
                    {selected.userEmail ?? selected.userId}
                  </p>
                </div>
              </div>

              {/* User comment */}
              {selected.note && (
                <>
                  <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-1.5">comment</p>
                  <div
                    className={[
                      "rounded-lg p-3.5 mb-5 text-[13.5px] leading-relaxed",
                      selected.rating === "down" ? "bg-[#fbe9e6] text-[#8c2a20]" : "bg-[#e6f3ec] text-[#1f6e45]",
                    ].join(" ")}
                  >
                    "{selected.note}"
                  </div>
                </>
              )}

              {/* Trace grid */}
              <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-2">trace</p>
              <div className="bg-surface border border-line rounded-[10px] p-3.5 mb-3.5">
                <div className="grid grid-cols-4 gap-3.5">
                  {[
                    ["latency",     "—"],
                    ["cache",       "—"],
                    ["model",       "—"],
                    ["k retrieved", "—"],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 mb-1">{k}</p>
                      <p className="font-mono text-[13px] font-medium text-ink">{v}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Suspected cause card */}
              <div
                className="border border-line rounded-[10px] p-3.5 flex gap-3 items-start mb-4"
                style={{ background: "var(--paper-2, #f4f1ea)" }}
              >
                <div className="w-8 h-8 rounded-lg bg-[#f9efd9] text-[#8b5a16] flex items-center justify-center font-medium text-[16px] shrink-0">
                  !
                </div>
                <div className="flex-1">
                  <p className="text-[13px] font-medium text-ink mb-0.5">Suspected cause</p>
                  <p className="text-[12px] text-text-2 leading-relaxed">
                    Review the trace and retrieved chunks above for coverage gaps.
                  </p>
                </div>
              </div>

              {/* Meta */}
              <div className="rounded-lg border border-line bg-surface px-3.5 py-3 grid grid-cols-2 gap-y-1.5 text-[12px]">
                <span className="text-text-mute">User</span>
                <span className="text-text font-mono truncate">{selected.userEmail ?? selected.userId}</span>
                <span className="text-text-mute">Session</span>
                <span className="text-text font-mono truncate">{selected.sessionId || "—"}</span>
                <span className="text-text-mute">Trace ID</span>
                <span className="text-text font-mono truncate">{selected.traceId || "—"}</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-[13px] text-text-mute">
            Select an item to inspect
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
