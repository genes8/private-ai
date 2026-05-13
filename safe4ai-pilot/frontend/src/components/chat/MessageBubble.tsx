import type { ReactNode } from "react";

interface Props { role: "user" | "assistant"; children: ReactNode }

export default function MessageBubble({ role, children }: Props) {
  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] bg-paper-2 px-3.5 py-[10px] text-[13.5px] text-text border border-line" style={{ borderRadius: "14px 14px 4px 14px" }}>
          {children}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[80%]">{children}</div>
    </div>
  );
}
