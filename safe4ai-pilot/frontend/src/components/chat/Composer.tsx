import { Send } from "lucide-react";
import { useRef } from "react";

interface Scope { name: string; chunkCount: number }

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  scope?: Scope;
  disabled?: boolean;
  placeholder?: string;
}

export default function Composer({ value, onChange, onSubmit, scope, disabled, placeholder }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (value.trim()) onSubmit();
    }
  }

  function autoGrow() {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }

  return (
    <div className="relative rounded-xl border border-line bg-surface shadow-sm focus-within:border-accent/40 focus-within:shadow-[0_0_0_3px_rgba(59,108,242,0.08)] transition-all">
      {scope && (
        <div className="flex items-center gap-2 px-4 pt-3 pb-0">
          <span className="text-[10.5px] tracking-kicker uppercase text-text-mute">Scope</span>
          <span className="text-[11.5px] font-medium text-text-2">{scope.name}</span>
          <span className="text-text-mute text-[10.5px]">· {scope.chunkCount} chunks</span>
        </div>
      )}
      <textarea
        aria-label="Message"
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => { onChange(e.target.value); autoGrow(); }}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={placeholder ?? "Ask anything about your documents…"}
        className={[
          "w-full resize-none bg-transparent px-4 py-3 text-[14px] leading-relaxed text-text",
          "placeholder:text-text-mute focus:outline-none",
          "disabled:opacity-50",
        ].join(" ")}
        style={{ minHeight: 48 }}
      />
      <div className="flex items-end justify-between px-3 pb-3">
        <p className="text-[10.5px] text-text-mute">Enter to send</p>
        <button
          type="button"
          onClick={() => value.trim() && onSubmit()}
          disabled={disabled || !value.trim()}
          aria-label="Send message"
          className="flex size-7 items-center justify-center rounded-lg bg-ink text-paper hover:bg-ink-2 disabled:opacity-30 transition-colors"
        >
          <Send size={13} />
        </button>
      </div>
    </div>
  );
}
