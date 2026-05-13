interface Props {
  latencyMs: number;
  cacheHit: boolean;
  model: string;
  kRetrieved: number;
  onOpenTrace?: () => void;
}

export default function TrustSignal({ latencyMs, cacheHit, model, kRetrieved, onOpenTrace }: Props) {
  return (
    <button
      onClick={onOpenTrace}
      className="inline-flex items-center gap-2.5 font-mono text-[11px] text-text-3 hover:text-text-2 transition-colors"
    >
      <b className="font-medium text-text-2">{latencyMs}</b>
      <span className="text-text-mute">ms</span>
      <span className="text-line-3">·</span>
      <span style={{ color: cacheHit ? "var(--green)" : undefined }}>{cacheHit ? "cache hit" : "fresh"}</span>
      <span className="text-line-3">·</span>
      <b className="font-medium text-text-2">{kRetrieved}</b>
      <span className="text-text-mute">retrievals</span>
      <span className="text-line-3">·</span>
      <span>{model}</span>
    </button>
  );
}
