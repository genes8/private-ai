import type { ReactNode } from "react";

interface Props {
  tag: string;
  icon?: ReactNode;
  question: string;
  source: string;
  onSelect: () => void;
}

export default function SuggestedPrompt({ tag, icon, question, source, onSelect }: Props) {
  return (
    <button
      onClick={onSelect}
      className="flex flex-col gap-1.5 rounded-xl border border-line bg-surface p-4 text-left hover:border-accent/30 transition-[border-color] duration-[120ms]"
    >
      <div className="flex items-center gap-2">
        {icon && <span className="text-text-mute">{icon}</span>}
        <span className="text-[10.5px] font-medium tracking-kicker uppercase text-text-mute">
          {tag}
        </span>
      </div>
      <p className="text-[13px] font-medium text-text leading-snug">{question}</p>
      <p className="text-[11px] text-text-3 truncate">{source}</p>
    </button>
  );
}
