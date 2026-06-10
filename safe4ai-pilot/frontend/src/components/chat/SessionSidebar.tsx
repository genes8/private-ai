import { MessageSquarePlus } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { listChatSessions } from "../../api/chat";

interface SessionSidebarProps {
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onNewChat: () => void;
  disabled?: boolean;
}

function relativeDay(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const diffDays = Math.floor((startOfToday.getTime() - d.getTime()) / 86_400_000) + 1;
  if (d >= startOfToday) return "today";
  if (diffDays <= 1) return "yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export default function SessionSidebar({
  activeSessionId,
  onSelect,
  onNewChat,
  disabled,
}: SessionSidebarProps) {
  const { data: sessions = [], isLoading } = useQuery({
    queryKey: ["chat-sessions"],
    queryFn: listChatSessions,
    refetchInterval: 30_000,
  });

  return (
    <aside className="hidden md:flex w-[230px] shrink-0 border-r border-line bg-surface-2 flex-col">
      <div className="p-3">
        <button
          type="button"
          onClick={onNewChat}
          disabled={disabled}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-line bg-surface text-[12.5px] font-medium text-text-2 hover:bg-paper transition-colors disabled:opacity-50"
        >
          <MessageSquarePlus size={14} className="text-text-3 shrink-0" />
          New chat
        </button>
      </div>

      <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3 px-4 mb-1.5">
        Recent
      </p>
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {isLoading ? (
          <p className="px-2 py-2 text-[12px] text-text-mute">Loading…</p>
        ) : sessions.length === 0 ? (
          <p className="px-2 py-2 text-[12px] text-text-mute">No previous sessions.</p>
        ) : (
          sessions.map((s) => (
            <button
              key={s.sessionId}
              type="button"
              onClick={() => onSelect(s.sessionId)}
              disabled={disabled}
              className={[
                "w-full text-left px-2.5 py-2 rounded-md mb-0.5 transition-colors disabled:opacity-50",
                s.sessionId === activeSessionId
                  ? "bg-[#f4f1ea] text-ink"
                  : "text-text-2 hover:bg-surface",
              ].join(" ")}
            >
              <span className="block text-[12.5px] leading-snug truncate">{s.title}</span>
              <span className="block font-mono text-[10.5px] text-text-3 mt-0.5">
                {relativeDay(s.updatedAt)} · {s.messageCount} msg
              </span>
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
