import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";

type Variant = "default" | "primary" | "accent" | "ghost" | "danger";
type Size    = "sm" | "md" | "lg";

const variantCls: Record<Variant, string> = {
  default: "bg-surface border border-line text-text-2 hover:bg-surface-2",
  primary: "bg-ink text-paper hover:bg-ink-2",
  accent:  "bg-accent text-white hover:bg-accent-2",
  ghost:   "text-text-2 hover:bg-surface-2",
  danger:  "bg-danger-soft text-danger hover:bg-red-100 border border-danger/20",
};

const sizeCls: Record<Size, string> = {
  sm: "h-[26px] px-[9px] text-[12px] gap-1.5 rounded-[5px]",
  md: "h-8 px-3.5 text-[13px] gap-2",
  lg: "h-[38px] px-5 text-[13.5px] gap-2",
};

interface Props {
  variant?: Variant;
  size?: Size;
  iconLeft?: ReactNode;
  iconRight?: ReactNode;
  loading?: boolean;
  disabled?: boolean;
  children?: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit" | "reset";
  className?: string;
}

export default function Button({
  variant = "default", size = "md", iconLeft, iconRight,
  loading, disabled, children, onClick, type = "button", className = "",
}: Props) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={[
        "inline-flex items-center justify-center rounded font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
        "disabled:opacity-40 disabled:pointer-events-none",
        variantCls[variant], sizeCls[size], className,
      ].join(" ")}
    >
      {loading ? <Loader2 size={14} className="animate-spin" /> : iconLeft}
      {children}
      {iconRight}
    </button>
  );
}
