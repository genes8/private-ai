// private-ai · Settings page
// Drop into src/pages/admin/SettingsPage.tsx
//
// Sections: Models · Retrieval · Document sources · Security · Cost ceiling
// One left-rail nav, scroll-snap sections on the right.

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Brain, Search as SearchIcon, Folder, Lock, Activity,
  Plus, Check, ExternalLink, RefreshCw, Trash2, AlertCircle,
} from "lucide-react";

// ── Domain ────────────────────────────────────────────────────────────────
export interface AppSettings {
  generationModel: string;          // e.g. "claude-haiku-4-5"
  generationFallback: string;       // larger model used on low-confidence retries
  embeddingModel: string;
  reranker: { enabled: boolean; model: string };
  retrieval: {
    k: number;                      // chunks retrieved
    scoreFloor: number;             // 0..1, fallback below this
    chunkSize: number;              // tokens
    chunkOverlap: number;
  };
  sources: Array<{
    id: string;
    kind: "s3" | "gdrive" | "watch";
    label: string;
    detail: string;
    docCount: number;
    syncedAt: string;
    status: "ok" | "syncing" | "error";
  }>;
  security: {
    ssoOnly: boolean;
    sessionHours: number;
    auditRetentionDays: number;
    redactPII: boolean;
  };
  cost: {
    dailyCeilingUsd: number;
    monthlyCeilingUsd: number;
    todayUsd: number;
  };
}

// ── API stubs ─────────────────────────────────────────────────────────────
async function getSettings(): Promise<AppSettings> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/settings`, { credentials: "include" });
  if (!r.ok) throw new Error("failed");
  return r.json();
}
async function patchSettings(diff: Partial<AppSettings>) {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/settings`, {
    method: "PATCH", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(diff),
  });
  if (!r.ok) throw new Error("failed");
  return r.json() as Promise<AppSettings>;
}

// ── Atoms ─────────────────────────────────────────────────────────────────
function Section({ id, title, subtitle, children }: {
  id: string; title: string; subtitle?: string; children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-4 mb-10">
      <div className="mb-5">
        <div className="text-[10.5px] font-mono uppercase tracking-[.06em] text-text-3 mb-1.5">
          {id}
        </div>
        <h2 className="text-[20px] italic font-serif text-ink tracking-tight">{title}</h2>
        {subtitle && <p className="text-[13px] text-text-2 mt-1 max-w-[60ch]">{subtitle}</p>}
      </div>
      <div className="bg-surface border border-line rounded-lg divide-y divide-line">
        {children}
      </div>
    </section>
  );
}

function Row({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[1fr_auto] gap-6 items-center px-5 py-4">
      <div className="min-w-0">
        <div className="text-[13.5px] font-medium text-ink">{label}</div>
        {hint && <div className="text-[12px] text-text-2 mt-0.5 leading-relaxed">{hint}</div>}
      </div>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  );
}

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={`relative w-9 h-5 rounded-full transition-colors ${value ? "bg-ink" : "bg-line-3"}`}>
      <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-paper-2 transition-transform
                        ${value ? "translate-x-4" : "translate-x-0"}`} />
    </button>
  );
}

function Select<T extends string>({ value, options, onChange }: {
  value: T; options: T[]; onChange: (v: T) => void;
}) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value as T)}
      className="h-8 px-2.5 pr-7 rounded border border-line bg-surface text-[12.5px] font-medium text-text outline-none focus:border-accent">
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

function NumberInput({ value, onChange, unit, min, max, step = 1 }: {
  value: number; onChange: (v: number) => void; unit?: string;
  min?: number; max?: number; step?: number;
}) {
  return (
    <div className="inline-flex items-center gap-1.5">
      <input
        type="number" min={min} max={max} step={step}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-20 h-8 px-2.5 rounded border border-line bg-surface text-[12.5px] font-mono text-right outline-none focus:border-accent" />
      {unit && <span className="text-[11.5px] font-mono text-text-3">{unit}</span>}
    </div>
  );
}

function SourceCard({ s, onSync, onRemove }: {
  s: AppSettings["sources"][number];
  onSync: () => void; onRemove: () => void;
}) {
  const tone = {
    ok:      { dot: "bg-success",  label: "synced"  },
    syncing: { dot: "bg-accent animate-pulse", label: "syncing" },
    error:   { dot: "bg-danger",   label: "error"   },
  }[s.status];

  return (
    <div className="px-5 py-4 flex items-center gap-4">
      <div className="w-8 h-8 rounded-md bg-paper-2 flex items-center justify-center text-[10px] font-mono font-semibold text-text-2 uppercase">
        {s.kind === "s3" ? "s3" : s.kind === "gdrive" ? "GD" : "fs"}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-medium text-ink truncate">{s.label}</span>
          <span className="inline-flex items-center gap-1.5 h-[20px] px-2 rounded-full border border-line bg-surface-2 text-[11px] text-text-2">
            <span className={`w-1.5 h-1.5 rounded-full ${tone.dot}`} />
            {tone.label}
          </span>
        </div>
        <div className="text-[11.5px] font-mono text-text-3 truncate">
          {s.detail} · {s.docCount} docs · synced {s.syncedAt}
        </div>
      </div>
      <button onClick={onSync} title="Sync now"
        className="w-7 h-7 rounded hover:bg-surface-2 flex items-center justify-center">
        <RefreshCw className="w-3.5 h-3.5 text-text-3" strokeWidth={1.5} />
      </button>
      <button onClick={onRemove} title="Disconnect"
        className="w-7 h-7 rounded hover:bg-surface-2 flex items-center justify-center">
        <Trash2 className="w-3.5 h-3.5 text-text-3" strokeWidth={1.5} />
      </button>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────
type SectionId = "models" | "retrieval" | "sources" | "security" | "cost";

const NAV: Array<{ id: SectionId; label: string; icon: React.ComponentType<{ className?: string; strokeWidth?: number }> }> = [
  { id: "models",    label: "Models",          icon: Brain },
  { id: "retrieval", label: "Retrieval",       icon: SearchIcon },
  { id: "sources",   label: "Document sources", icon: Folder },
  { id: "security",  label: "Security",        icon: Lock },
  { id: "cost",      label: "Cost ceiling",    icon: Activity },
];

export default function SettingsPage() {
  const [active, setActive] = useState<SectionId>("models");
  const qc = useQueryClient();
  const { data: s } = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const save = useMutation({
    mutationFn: patchSettings,
    onSuccess: (next) => qc.setQueryData(["settings"], next),
  });

  if (!s) return <div className="p-7 text-text-3 font-mono">loading…</div>;

  const set = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) =>
    save.mutate({ [key]: value } as Partial<AppSettings>);

  return (
    <div className="h-full grid grid-cols-[200px_1fr] bg-paper">
      {/* Left nav */}
      <aside className="border-r border-line p-4 sticky top-0 self-start">
        <div className="text-[10.5px] font-mono uppercase tracking-[.06em] text-text-3 mb-2 px-2">
          settings
        </div>
        <nav className="flex flex-col gap-0.5">
          {NAV.map(item => {
            const Ic = item.icon;
            const on = item.id === active;
            return (
              <a
                key={item.id}
                href={`#${item.id}`}
                onClick={() => setActive(item.id)}
                className={`flex items-center gap-2.5 h-7 px-2 rounded text-[12.5px] font-medium transition-colors
                  ${on ? "bg-surface shadow-sm text-ink ring-1 ring-line" : "text-text-2 hover:bg-surface-2"}`}>
                <Ic className={`w-3.5 h-3.5 ${on ? "text-ink" : "text-text-3"}`} strokeWidth={1.5} />
                {item.label}
              </a>
            );
          })}
        </nav>

        <div className="mt-6 p-3 rounded bg-paper-2 text-[11px] font-mono text-text-3 leading-relaxed">
          Saved changes apply to all users within ~30s. No restart needed.
        </div>
      </aside>

      {/* Content */}
      <div className="overflow-auto">
        <div className="max-w-3xl mx-auto px-8 py-8">

          <header className="mb-8">
            <div className="text-[10.5px] font-mono uppercase tracking-[.06em] text-text-3 mb-1.5">configuration</div>
            <h1 className="text-[28px] italic font-serif text-ink tracking-tight">Settings</h1>
            <p className="text-[13.5px] text-text-2 mt-1.5">
              Tune how private·ai retrieves, generates and audits. Every change here is itself audited.
            </p>
          </header>

          {/* MODELS */}
          <Section id="models" title="Models"
            subtitle="The generation model answers queries; the embedding model indexes documents. Reranker is optional but improves precision on noisy corpora.">
            <Row label="Generation model" hint="Used for every answer. Smaller = faster + cheaper.">
              <Select
                value={s.generationModel}
                options={["claude-haiku-4-5", "claude-sonnet-4-5", "claude-opus-4"]}
                onChange={(v) => set("generationModel", v)} />
            </Row>
            <Row label="Fallback model" hint="Tried on low-confidence retries. Set to the same model to disable.">
              <Select
                value={s.generationFallback}
                options={["claude-haiku-4-5", "claude-sonnet-4-5", "claude-opus-4"]}
                onChange={(v) => set("generationFallback", v)} />
            </Row>
            <Row label="Embedding model" hint="Changing this triggers a full reindex of your corpus.">
              <Select
                value={s.embeddingModel}
                options={["voyage-3", "voyage-3-large", "openai-text-embedding-3-large"]}
                onChange={(v) => set("embeddingModel", v)} />
            </Row>
            <Row label="Reranker" hint="bge-reranker-v2 adds ~140ms p50 but lifts top-1 score by ~12% on our corpus.">
              <Toggle value={s.reranker.enabled}
                onChange={(v) => set("reranker", { ...s.reranker, enabled: v })} />
            </Row>
          </Section>

          {/* RETRIEVAL */}
          <Section id="retrieval" title="Retrieval"
            subtitle="How chunks are pulled from the index before the model sees them. Score floor governs when private·ai refuses to answer.">
            <Row label="Chunks retrieved (k)" hint="Higher k = more context, more tokens, more cost.">
              <NumberInput value={s.retrieval.k} min={1} max={32}
                onChange={(v) => set("retrieval", { ...s.retrieval, k: v })} />
            </Row>
            <Row label="Score floor" hint="If the top-1 retrieval scores below this, private·ai falls back to “I don't know.”">
              <NumberInput value={s.retrieval.scoreFloor} min={0} max={1} step={0.05}
                onChange={(v) => set("retrieval", { ...s.retrieval, scoreFloor: v })} />
            </Row>
            <Row label="Chunk size" hint="Tokens per chunk at index time.">
              <NumberInput value={s.retrieval.chunkSize} unit="tokens" min={128} max={2048} step={64}
                onChange={(v) => set("retrieval", { ...s.retrieval, chunkSize: v })} />
            </Row>
            <Row label="Chunk overlap" hint="Tokens shared between adjacent chunks for better recall on boundary text.">
              <NumberInput value={s.retrieval.chunkOverlap} unit="tokens" min={0} max={512} step={16}
                onChange={(v) => set("retrieval", { ...s.retrieval, chunkOverlap: v })} />
            </Row>
          </Section>

          {/* SOURCES */}
          <Section id="sources" title="Document sources"
            subtitle="Indexed locations watched for changes. Drop a file in any of these and it shows up in chat within ~30s.">
            {s.sources.map(src => (
              <SourceCard key={src.id} s={src}
                onSync={() => {/* TODO: trigger sync */}}
                onRemove={() => {/* TODO: confirm + remove */}} />
            ))}
            <div className="px-5 py-3.5 flex items-center justify-between bg-surface-2">
              <span className="text-[12px] text-text-2">Connect another location.</span>
              <div className="flex gap-2">
                <button className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded border border-line bg-surface text-[12px] font-medium text-text hover:bg-paper-2">
                  <Plus className="w-3 h-3" strokeWidth={2} /> S3 bucket
                </button>
                <button className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded border border-line bg-surface text-[12px] font-medium text-text hover:bg-paper-2">
                  <Plus className="w-3 h-3" strokeWidth={2} /> Google Drive
                </button>
                <button className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded border border-line bg-surface text-[12px] font-medium text-text hover:bg-paper-2">
                  <Plus className="w-3 h-3" strokeWidth={2} /> Watch folder
                </button>
              </div>
            </div>
          </Section>

          {/* SECURITY */}
          <Section id="security" title="Security"
            subtitle="Auth, session lifetime and how long the audit log keeps every prompt and retrieval.">
            <Row label="SSO only" hint="When on, password login is disabled and all sign-ins must go through your IdP.">
              <Toggle value={s.security.ssoOnly}
                onChange={(v) => set("security", { ...s.security, ssoOnly: v })} />
            </Row>
            <Row label="Session lifetime" hint="How long a JWT cookie is valid before re-auth.">
              <NumberInput value={s.security.sessionHours} unit="hours" min={1} max={720}
                onChange={(v) => set("security", { ...s.security, sessionHours: v })} />
            </Row>
            <Row label="Audit retention" hint="After this, events are archived to immutable storage.">
              <NumberInput value={s.security.auditRetentionDays} unit="days" min={30} max={3650}
                onChange={(v) => set("security", { ...s.security, auditRetentionDays: v })} />
            </Row>
            <Row label="Redact PII in audit log" hint="Email addresses, phone numbers and names are hashed before being written to the audit stream.">
              <Toggle value={s.security.redactPII}
                onChange={(v) => set("security", { ...s.security, redactPII: v })} />
            </Row>
          </Section>

          {/* COST */}
          <Section id="cost" title="Cost ceiling"
            subtitle="A hard kill-switch on spend. When the daily ceiling is hit, the service falls back to read-only until midnight UTC.">
            <Row label="Today's spend" hint={`${((s.cost.todayUsd / s.cost.dailyCeilingUsd) * 100).toFixed(0)}% of daily ceiling.`}>
              <div className="flex items-center gap-3">
                <span className="font-mono text-[15px] tabular-nums text-ink font-medium">
                  ${s.cost.todayUsd.toFixed(2)}
                </span>
                <div className="w-32 h-1.5 rounded-full bg-paper-2 overflow-hidden">
                  <div
                    className="h-full bg-ink"
                    style={{ width: `${Math.min(100, (s.cost.todayUsd / s.cost.dailyCeilingUsd) * 100)}%` }} />
                </div>
              </div>
            </Row>
            <Row label="Daily ceiling" hint="Service degrades gracefully when hit — answers still served from cache.">
              <NumberInput value={s.cost.dailyCeilingUsd} unit="USD" min={1} max={10000}
                onChange={(v) => set("cost", { ...s.cost, dailyCeilingUsd: v })} />
            </Row>
            <Row label="Monthly ceiling" hint="A second guardrail on top of the daily one.">
              <NumberInput value={s.cost.monthlyCeilingUsd} unit="USD" min={30} max={300000}
                onChange={(v) => set("cost", { ...s.cost, monthlyCeilingUsd: v })} />
            </Row>
          </Section>

          {save.isError && (
            <div className="flex items-center gap-2 p-3 rounded bg-danger-soft text-danger text-[12.5px]">
              <AlertCircle className="w-4 h-4" strokeWidth={1.5} />
              Couldn't save changes. Retrying…
            </div>
          )}

          <footer className="mt-6 mb-4 flex items-center justify-between text-[11px] font-mono text-text-3">
            <span>Settings v0.4.18 · last edited by maya.reyes · 2h ago</span>
            <a className="inline-flex items-center gap-1 text-text-2 hover:text-ink">
              View change history <ExternalLink className="w-3 h-3" strokeWidth={1.5} />
            </a>
          </footer>
        </div>
      </div>
    </div>
  );
}
