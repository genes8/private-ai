interface Props { name: string; size?: number; color?: string }

export default function Avatar({ name, size = 28, color }: Props) {
  const initials = name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  const bg = color ?? "#0b0d10";
  return (
    <div
      style={{ width: size, height: size, background: bg, borderRadius: "50%", fontSize: size * 0.38 }}
      className="flex items-center justify-center font-medium text-paper shrink-0"
    >
      {initials}
    </div>
  );
}
