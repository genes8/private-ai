interface Props {
  id: string;
  active?: boolean;
  onOpen?: (id: string) => void;
}

export default function CitationChip({ id, active, onOpen }: Props) {
  return (
    <button
      type="button"
      onClick={() => onOpen?.(id)}
      className={[
        "inline-flex items-center justify-center min-w-[18px] h-[17px] px-1 rounded text-[10.5px] font-mono font-medium",
        "border border-accent/20 align-super mx-0.5 transition-colors hover:shadow-[0_0_0_3px_rgba(59,108,242,.18)]",
        active
          ? "bg-accent text-white"
          : "bg-accent-soft text-accent hover:bg-accent hover:text-white",
      ].join(" ")}
    >
      {id}
    </button>
  );
}
