interface Props { data: number[]; color?: string; height?: number; fill?: boolean }

export default function Sparkline({ data, color = "#3b6cf2", height = 32, fill }: Props) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const w = 80, h = height;
  const norm = (v: number) => h - ((v - min) / (max - min || 1)) * (h - 4) - 2;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    return `${x},${norm(v)}`;
  });
  const path = `M${pts.join(" L")}`;
  const fillPath = `${path} L${w},${h} L0,${h} Z`;
  const endX = w;
  const endY = norm(data.at(-1)!);

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} fill="none">
      {fill && <path d={fillPath} fill={color} fillOpacity="0.08" />}
      <path d={path} stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={endX} cy={endY} r="2" fill={color} />
    </svg>
  );
}
