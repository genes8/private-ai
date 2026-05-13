import { Check, Loader2 } from "lucide-react";
import type { StepName, StepState } from "../../api/chat";

const STEP_LABELS: Record<StepName, string> = {
  embed:    "Embedding query",
  retrieve: "Retrieving chunks",
  rerank:   "Reranking",
  generate: "Generating answer",
};

interface Step { name: StepName; state: StepState; detail?: string }

export default function StreamingPipeline({ steps }: { steps: Step[] }) {
  return (
    <div className="space-y-2 py-2 px-1">
      {steps.map((s) => (
        <div key={s.name} className="flex items-center gap-3">
          {s.state === "done"    && <Check size={12} className="text-success shrink-0" />}
          {s.state === "active"  && <Loader2 size={12} className="animate-spin text-accent shrink-0" />}
          {s.state === "pending" && <div className="w-3 h-3 rounded-full border border-line-3 shrink-0" />}
          <span className={["text-[11.5px] w-[110px] shrink-0", s.state === "pending" ? "text-text-mute" : "text-text-2"].join(" ")}>
            {STEP_LABELS[s.name]}
          </span>
          {s.detail && <span className="text-[10.5px] font-mono text-text-3">{s.detail}</span>}
        </div>
      ))}
    </div>
  );
}
