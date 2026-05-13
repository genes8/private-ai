import { ThumbsDown, ThumbsUp } from "lucide-react";
import type { FeedbackItem } from "../../api/feedback";

interface Props { item: FeedbackItem; active?: boolean; onSelect?: () => void }

export default function FeedbackListItem({ item, active, onSelect }: Props) {
  const time = new Date(item.ts).toLocaleString([], { dateStyle: "short", timeStyle: "short" });
  return (
    <button
      type="button"
      onClick={onSelect}
      className={[
        "w-full flex items-start gap-3 py-3 border-b border-line text-left hover:bg-surface-2 transition-colors border-l-2",
        active ? "bg-[#f4f1ea] border-l-[#0b0d10] pl-[14px] pr-4" : "border-l-transparent px-4",
      ].join(" ")}
    >
      <span className={["mt-0.5 shrink-0", item.rating === "up" ? "text-success" : "text-danger"].join(" ")}>
        {item.rating === "up" ? <ThumbsUp size={13} /> : <ThumbsDown size={13} />}
      </span>
      <div className="min-w-0">
        <p className="text-[12.5px] font-medium text-text truncate">{item.userId}</p>
        {item.note
          ? <p className="text-[11px] text-text-3 mt-0.5 truncate">"{item.note}"</p>
          : <p className="text-[11px] text-text-mute mt-0.5">{item.rating === "up" ? "👍 Positive" : "👎 Negative"}</p>
        }
        <p className="text-[10.5px] text-text-mute mt-1">{time}</p>
      </div>
    </button>
  );
}
