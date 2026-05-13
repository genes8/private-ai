import type { ReactNode } from "react";

type Tone    = "neutral" | "success" | "warn" | "danger" | "accent";
type Variant = "default" | "solid";

const toneCls: Record<Tone, { default: string; solid: string }> = {
  neutral: { default: "bg-surface-2 text-text-3 border border-line",          solid: "bg-ink-4 text-paper" },
  success: { default: "bg-success-soft text-success border border-success/20", solid: "bg-success text-white" },
  warn:    { default: "bg-warn-soft text-warn border border-warn/20",          solid: "bg-warn text-white" },
  danger:  { default: "bg-danger-soft text-danger border border-danger/20",    solid: "bg-danger text-white" },
  accent:  { default: "bg-accent-soft text-accent border border-accent/20",    solid: "bg-accent text-white" },
};

const dotColor: Record<Tone, string> = {
  neutral: "#7c8aa0",
  success: "#2f8f5e",
  warn:    "#b87a1a",
  danger:  "#c0392b",
  accent:  "#3b6cf2",
};

interface Props { variant?: Variant; tone?: Tone; children?: ReactNode; }

export default function Chip({ variant = "default", tone = "neutral", children }: Props) {
  return (
    <span className={["inline-flex items-center rounded-full h-[22px] px-2 gap-1.5 text-[11.5px] font-medium", toneCls[tone][variant]].join(" ")}>
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: dotColor[tone] }} />
      {children}
    </span>
  );
}
