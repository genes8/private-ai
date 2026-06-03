import { useState } from "react";

// ── Section ───────────────────────────────────────────────────────────────────

export function Section({
  id,
  title,
  subtitle,
  children,
}: {
  id: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-4 mb-10">
      <div className="mb-5">
        <div className="text-[10.5px] font-mono uppercase tracking-[.06em] text-text-3 mb-1.5">
          {id}
        </div>
        <h2 className="text-[20px] italic font-serif text-ink tracking-tight">{title}</h2>
        {subtitle && (
          <p className="text-[13px] text-text-2 mt-1 max-w-[60ch]">{subtitle}</p>
        )}
      </div>
      <div className="bg-surface border border-line rounded-lg divide-y divide-line">
        {children}
      </div>
    </section>
  );
}

// ── Row ───────────────────────────────────────────────────────────────────────

export function Row({
  label,
  hint,
  saving = false,
  children,
}: {
  label: string;
  hint?: string;
  saving?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[1fr_auto] gap-6 items-start px-5 py-4">
      <div className="min-w-0 pt-0.5">
        <div className="flex items-center gap-2">
          <div className="text-[13.5px] font-medium text-ink">{label}</div>
          {saving && (
            <span className="inline-flex items-center gap-1 text-[11px] font-mono text-accent">
              <span className="size-1.5 rounded-full bg-accent animate-pulse" />
              Saving
            </span>
          )}
        </div>
        {hint && (
          <div className="text-[12px] text-text-2 mt-0.5 leading-relaxed max-w-[52ch]">
            {hint}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  );
}

// ── Toggle ────────────────────────────────────────────────────────────────────

export function Toggle({
  value,
  onChange,
}: {
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      aria-label="Toggle setting"
      onClick={() => onChange(!value)}
      className={`relative h-5 w-9 rounded-full transition-colors ${
        value ? "bg-ink" : "bg-line-3"
      }`}>
      <span
        className={`absolute left-0.5 top-0.5 size-4 rounded-full bg-paper-2 transition-transform ${
          value ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}

// ── Select ────────────────────────────────────────────────────────────────────

export function Select<T extends string>({
  value,
  options,
  onChange,
  className,
}: {
  value: T;
  options: readonly T[];
  onChange: (v: T) => void;
  className?: string;
}) {
  return (
    <select
      aria-label="Select setting"
      value={value}
      onChange={(e) => onChange(e.target.value as T)}
      className={`h-8 px-2.5 pr-7 rounded border border-line bg-surface text-[12.5px] font-medium text-text outline-none focus:border-accent ${className ?? ""}`}>
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

// ── NumberInput ───────────────────────────────────────────────────────────────

export function NumberInput({
  value,
  onChange,
  unit,
  min,
  max,
  step = 1,
}: {
  value: number;
  onChange: (v: number) => void;
  unit?: string;
  min?: number;
  max?: number;
  step?: number;
}) {
  function commit(nextRaw: string) {
    const next = Number(nextRaw);
    if (Number.isFinite(next)) {
      const clamped = Math.min(max ?? next, Math.max(min ?? next, next));
      if (clamped !== value) onChange(clamped);
    }
  }

  return (
    <div className="inline-flex items-center gap-1.5">
      <input
        type="number"
        aria-label="Numeric setting"
        key={value}
        min={min}
        max={max}
        step={step}
        defaultValue={value}
        onBlur={(e) => commit(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            commit((e.currentTarget as HTMLInputElement).value);
            e.currentTarget.blur();
          }
        }}
        className="h-8 w-20 px-2.5 rounded border border-line bg-surface text-[12.5px] font-mono text-right outline-none focus:border-accent"
      />
      {unit && (
        <span className="text-[11.5px] font-mono text-text-3">{unit}</span>
      )}
    </div>
  );
}

// ── TextInput ─────────────────────────────────────────────────────────────────

export function TextInput({
  value,
  onCommit,
}: {
  value: string;
  onCommit: (v: string) => void;
}) {
  return (
    <input
      type="text"
      aria-label="Text setting"
      key={value}
      defaultValue={value}
      onBlur={(e) => onCommit(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          onCommit(e.currentTarget.value);
          e.currentTarget.blur();
        }
      }}
      className="h-8 w-64 px-2.5 rounded border border-line bg-surface text-[12.5px] font-mono outline-none focus:border-accent"
    />
  );
}

// ── PasswordInput ─────────────────────────────────────────────────────────────

export function PasswordInput({
  placeholder,
  onCommit,
  onChange,
}: {
  placeholder: string;
  onCommit: (v: string) => void;
  onChange?: (v: string) => void;
}) {
  const [draft, setDraft] = useState("");
  function commit(v: string) {
    if (v) onCommit(v);
    setDraft("");
    onChange?.("");
  }
  return (
    <input
      type="password"
      aria-label="Password setting"
      value={draft}
      placeholder={placeholder}
      onChange={(e) => {
        setDraft(e.target.value);
        onChange?.(e.target.value);
      }}
      onBlur={(e) => commit(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          commit(e.currentTarget.value);
          e.currentTarget.blur();
        }
      }}
      className="h-8 w-64 px-2.5 rounded border border-line bg-surface text-[12.5px] font-mono outline-none focus:border-accent"
    />
  );
}

// ── ModelSelect ───────────────────────────────────────────────────────────────

export function ModelSelect({
  value,
  options,
  onChange,
  placeholder = "Select model",
}: {
  value: string;
  options: string[];
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const allOptions = Array.from(new Set([...options, value].filter(Boolean)));
  return (
    <select
      aria-label="Model setting"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-8 px-2.5 pr-7 rounded border border-line bg-surface text-[12.5px] font-medium text-text outline-none focus:border-accent w-64">
      {allOptions.length === 0 && <option value="">{placeholder}</option>}
      {allOptions.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}
