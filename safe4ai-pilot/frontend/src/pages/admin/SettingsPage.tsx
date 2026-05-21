import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Brain,
  Search as SearchIcon,
  Folder,
  Lock,
  Activity,
  AlertCircle,
  Plug,
  Plus,
  X,
} from "lucide-react";
import { getSettings, patchSettings, testProviderConnection, type AppSettings, type PatchableSettings } from "../../api/settings";
import AdminLayout from "./AdminLayout";

type SaveField =
  | "generationModel"
  | "generationFallback"
  | "embeddingModel"
  | "visionModel"
  | "rerankerEnabled"
  | "rerankerModel"
  | "retrievalK"
  | "scoreFloor"
  | "chunkSize"
  | "chunkOverlap"
  | "ssoOnly"
  | "sessionHours"
  | "auditRetentionDays"
  | "redactPII"
  | "dailyCeilingUsd"
  | "monthlyCeilingUsd"
  | "providerType"
  | "providerBaseUrl"
  | "providerApiKey"
  | "providerChatModel"
  | "providerEmbeddingModel"
  | "providerVisionModel"
  | "sseDoneMode";

const DEFAULT_PROVIDER: AppSettings["provider"] = {
  type: "ollama",
  baseUrl: "http://localhost:11434",
  apiKeyConfigured: false,
  chatModel: "",
  embeddingModel: "",
  visionModel: "",
};

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

function Row({
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
    <div className="grid grid-cols-[1fr_auto] gap-6 items-center px-5 py-4">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <div className="text-[13.5px] font-medium text-ink">{label}</div>
          {saving && (
            <span className="inline-flex items-center gap-1 text-[11px] font-mono text-accent">
              <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
              Saving
            </span>
          )}
        </div>
        {hint && <div className="text-[12px] text-text-2 mt-0.5 leading-relaxed">{hint}</div>}
      </div>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  );
}

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
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
  const [draft, setDraft] = useState(String(value));
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    if (!isEditing) {
      setDraft(String(value));
    }
  }, [isEditing, value]);

  function commit(nextRaw: string) {
    setIsEditing(false);
    const next = Number(nextRaw);
    if (Number.isFinite(next)) {
      const clamped = Math.min(max ?? next, Math.max(min ?? next, next));
      setDraft(String(clamped));
      if (clamped !== value) {
        onChange(clamped);
      }
    } else {
      setDraft(String(value));
    }
  }

  return (
    <div className="inline-flex items-center gap-1.5">
      <input
        type="number" min={min} max={max} step={step}
        value={draft}
        onFocus={() => setIsEditing(true)}
        onChange={(e) => {
          setIsEditing(true);
          setDraft(e.target.value);
        }}
        onBlur={e => commit(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            commit((e.currentTarget as HTMLInputElement).value);
            e.currentTarget.blur();
          }
        }}
        className="w-20 h-8 px-2.5 rounded border border-line bg-surface text-[12.5px] font-mono text-right outline-none focus:border-accent" />
      {unit && <span className="text-[11.5px] font-mono text-text-3">{unit}</span>}
    </div>
  );
}

function TextInput({ value, onCommit }: { value: string; onCommit: (v: string) => void }) {
  const [draft, setDraft] = useState(value);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!editing) setDraft(value);
  }, [editing, value]);

  function commit(v: string) {
    setEditing(false);
    if (v.trim() !== value.trim()) onCommit(v.trim());
    else setDraft(value);
  }

  return (
    <input
      type="text"
      value={draft}
      onFocus={() => setEditing(true)}
      onChange={(e) => { setEditing(true); setDraft(e.target.value); }}
      onBlur={(e) => commit(e.target.value)}
      onKeyDown={(e) => { if (e.key === "Enter") { commit(e.currentTarget.value); e.currentTarget.blur(); } }}
      className="w-64 h-8 px-2.5 rounded border border-line bg-surface text-[12.5px] font-mono outline-none focus:border-accent" />
  );
}

function PasswordInput({ placeholder, onCommit, onChange }: {
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
      value={draft}
      placeholder={placeholder}
      onChange={(e) => { setDraft(e.target.value); onChange?.(e.target.value); }}
      onBlur={(e) => commit(e.target.value)}
      onKeyDown={(e) => { if (e.key === "Enter") { commit(e.currentTarget.value); e.currentTarget.blur(); } }}
      className="w-64 h-8 px-2.5 rounded border border-line bg-surface text-[12.5px] font-mono outline-none focus:border-accent" />
  );
}

function ModelSelect({ value, options, onChange, placeholder = "Select model" }: {
  value: string;
  options: string[];
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const allOptions = Array.from(new Set([...options, value].filter(Boolean)));
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="h-8 px-2.5 pr-7 rounded border border-line bg-surface text-[12.5px] font-medium text-text outline-none focus:border-accent w-64">
      {allOptions.length === 0 && <option value="">{placeholder}</option>}
      {allOptions.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

function SourceCard({ s }: { s: AppSettings["sources"][number] }) {
  const tone = {
    ok:      { dot: "bg-success",  label: "ok"      },
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
          {s.detail} · {s.docCount} docs{s.syncedAt ? ` · synced ${s.syncedAt}` : ""}
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────
type SectionId = "provider" | "models" | "retrieval" | "sources" | "security" | "cost";

const NAV: Array<{ id: SectionId; label: string; icon: React.ComponentType<{ className?: string; strokeWidth?: string | number }> }> = [
  { id: "provider",  label: "Provider",        icon: Plug },
  { id: "models",    label: "Models",          icon: Brain },
  { id: "retrieval", label: "Retrieval",       icon: SearchIcon },
  { id: "sources",   label: "Document sources", icon: Folder },
  { id: "security",  label: "Security",        icon: Lock },
  { id: "cost",      label: "Cost ceiling",    icon: Activity },
];

function mergeDiffs(base: PatchableSettings, next: PatchableSettings): PatchableSettings {
  return { ...base, ...next };
}

function diffFieldKeys(diff: PatchableSettings): SaveField[] {
  return Object.keys(diff) as SaveField[];
}


export default function SettingsPage() {
  const [active, setActive] = useState<SectionId>("models");
  const [saveErrorText, setSaveErrorText] = useState<string | null>(null);
  const [savingFields, setSavingFields] = useState<SaveField[]>([]);
  const [testConnectionState, setTestConnectionState] = useState<"idle" | "testing" | "ok" | "error">("idle");
  const [testConnectionMsg, setTestConnectionMsg] = useState<string>("");
  const [pendingApiKey, setPendingApiKey] = useState<string>("");
  const [customModelInput, setCustomModelInput] = useState<string>("");
  const [savingCustomModels, setSavingCustomModels] = useState(false);
  const qc = useQueryClient();
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());
  const unsavedDiffRef = useRef<PatchableSettings>({});

  const { data: s, isLoading, isError, error } = useQuery({
    queryKey: ["settings"],
    queryFn: getSettings,
    staleTime: 30_000,
    retry: 1,
  });

  const save = useMutation({
    mutationFn: patchSettings,
  });

  const provider = s?.provider ?? DEFAULT_PROVIDER;

  const applyDiff = (current: AppSettings, diff: PatchableSettings): AppSettings => ({
    ...current,
    generationModel: diff.generationModel ?? current.generationModel,
    generationFallback: diff.generationFallback ?? current.generationFallback,
    embeddingModel: diff.embeddingModel ?? current.embeddingModel,
    visionModel: diff.visionModel ?? current.visionModel,
    sseDoneMode: diff.sseDoneMode ?? current.sseDoneMode,
    provider: {
      ...(current.provider ?? DEFAULT_PROVIDER),
      type: diff.providerType ?? (current.provider?.type ?? DEFAULT_PROVIDER.type),
      baseUrl: diff.providerBaseUrl ?? (current.provider?.baseUrl ?? DEFAULT_PROVIDER.baseUrl),
      chatModel: diff.providerChatModel ?? (current.provider?.chatModel ?? DEFAULT_PROVIDER.chatModel),
      embeddingModel: diff.providerEmbeddingModel ?? (current.provider?.embeddingModel ?? DEFAULT_PROVIDER.embeddingModel),
      visionModel: diff.providerVisionModel ?? (current.provider?.visionModel ?? DEFAULT_PROVIDER.visionModel),
    },
    reranker: {
      enabled: diff.rerankerEnabled ?? current.reranker.enabled,
      model: diff.rerankerModel ?? current.reranker.model,
    },
    retrieval: {
      k: diff.retrievalK ?? current.retrieval.k,
      scoreFloor: diff.scoreFloor ?? current.retrieval.scoreFloor,
      chunkSize: diff.chunkSize ?? current.retrieval.chunkSize,
      chunkOverlap: diff.chunkOverlap ?? current.retrieval.chunkOverlap,
    },
    security: {
      ssoOnly: diff.ssoOnly ?? current.security.ssoOnly,
      sessionHours: diff.sessionHours ?? current.security.sessionHours,
      auditRetentionDays: diff.auditRetentionDays ?? current.security.auditRetentionDays,
      redactPII: diff.redactPII ?? current.security.redactPII,
    },
    cost: {
      ...current.cost,
      dailyCeilingUsd: diff.dailyCeilingUsd ?? current.cost.dailyCeilingUsd,
      monthlyCeilingUsd: diff.monthlyCeilingUsd ?? current.cost.monthlyCeilingUsd,
    },
  });

  const isSavingField = (field: SaveField) => savingFields.includes(field);

  const queueSave = (diff: PatchableSettings) => {
    const nextUnsaved = mergeDiffs(unsavedDiffRef.current, diff);
    unsavedDiffRef.current = nextUnsaved;
    setSaveErrorText(null);
    setSavingFields((prev) => Array.from(new Set([...prev, ...diffFieldKeys(diff)])));
    qc.setQueryData<AppSettings>(["settings"], (current) => {
      if (!current) return current;
      return applyDiff(current, diff);
    });
    saveQueueRef.current = saveQueueRef.current
      .catch(() => undefined)
      .then(async () => {
        // Snapshot and clear the pending diff atomically so concurrent queueSave
        // calls after this point accumulate into a fresh batch rather than being
        // re-sent by this handler.
        const diffToSave = unsavedDiffRef.current;
        unsavedDiffRef.current = {};
        if (Object.keys(diffToSave).length === 0) {
          return;
        }
        try {
          const nextSettings = await save.mutateAsync(diffToSave);
          qc.setQueryData<AppSettings>(["settings"], nextSettings);
          setSavingFields(diffFieldKeys(unsavedDiffRef.current));
        } catch (err) {
          // Restore the failed diff so it can be retried
          unsavedDiffRef.current = mergeDiffs(diffToSave, unsavedDiffRef.current);
          console.error("settings_save_failed", err);
          setSaveErrorText(err instanceof Error ? err.message : "Failed to save changes");
          await qc.invalidateQueries({ queryKey: ["settings"] });
          qc.setQueryData<AppSettings>(["settings"], (current) => {
            if (!current) return current;
            return applyDiff(current, unsavedDiffRef.current);
          });
          setSavingFields([]);
          throw err;
        }
      });
  };

  const set = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    if (!s) return;
    const diff: PatchableSettings = {};
    if (key === "generationModel" && value !== s.generationModel) {
      diff.generationModel = value as string;
    }
    if (key === "generationFallback" && value !== s.generationFallback) {
      diff.generationFallback = value as string;
    }
    if (key === "embeddingModel" && value !== s.embeddingModel) {
      diff.embeddingModel = value as string;
    }
    if (key === "visionModel" && value !== s.visionModel) {
      diff.visionModel = value as string;
    }
    if (key === "reranker") {
      const reranker = value as AppSettings["reranker"];
      if (reranker.enabled !== s.reranker.enabled) diff.rerankerEnabled = reranker.enabled;
      if (reranker.model !== s.reranker.model) diff.rerankerModel = reranker.model;
    }
    if (key === "retrieval") {
      const retrieval = value as AppSettings["retrieval"];
      if (retrieval.k !== s.retrieval.k) diff.retrievalK = retrieval.k;
      if (retrieval.scoreFloor !== s.retrieval.scoreFloor) diff.scoreFloor = retrieval.scoreFloor;
      if (retrieval.chunkSize !== s.retrieval.chunkSize) diff.chunkSize = retrieval.chunkSize;
      if (retrieval.chunkOverlap !== s.retrieval.chunkOverlap) diff.chunkOverlap = retrieval.chunkOverlap;
    }
    if (key === "security") {
      const sec = value as AppSettings["security"];
      if (sec.ssoOnly !== s.security.ssoOnly) diff.ssoOnly = sec.ssoOnly;
      if (sec.sessionHours !== s.security.sessionHours) diff.sessionHours = sec.sessionHours;
      if (sec.auditRetentionDays !== s.security.auditRetentionDays) diff.auditRetentionDays = sec.auditRetentionDays;
      if (sec.redactPII !== s.security.redactPII) diff.redactPII = sec.redactPII;
    }
    if (key === "cost") {
      const cost = value as AppSettings["cost"];
      if (cost.dailyCeilingUsd !== s.cost.dailyCeilingUsd) diff.dailyCeilingUsd = cost.dailyCeilingUsd;
      if (cost.monthlyCeilingUsd !== s.cost.monthlyCeilingUsd) diff.monthlyCeilingUsd = cost.monthlyCeilingUsd;
    }
    if (key === "provider") {
      const provider = value as AppSettings["provider"];
      if (provider.type !== (s.provider?.type ?? DEFAULT_PROVIDER.type)) diff.providerType = provider.type;
      if (provider.baseUrl !== (s.provider?.baseUrl ?? DEFAULT_PROVIDER.baseUrl)) diff.providerBaseUrl = provider.baseUrl;
      if (provider.chatModel !== (s.provider?.chatModel ?? DEFAULT_PROVIDER.chatModel)) diff.providerChatModel = provider.chatModel;
      if (provider.embeddingModel !== (s.provider?.embeddingModel ?? DEFAULT_PROVIDER.embeddingModel)) diff.providerEmbeddingModel = provider.embeddingModel;
      if (provider.visionModel !== (s.provider?.visionModel ?? DEFAULT_PROVIDER.visionModel)) diff.providerVisionModel = provider.visionModel;
    }
    if (key === "sseDoneMode" && value !== s.sseDoneMode) {
      diff.sseDoneMode = value as AppSettings["sseDoneMode"];
    }
    if (Object.keys(diff).length > 0) {
      queueSave(diff);
    }
  };

  if (isLoading) {
    return (
      <AdminLayout>
        <div className="h-full flex items-center justify-center bg-paper">
          <span className="text-[13px] text-text-mute font-mono">Loading settings…</span>
        </div>
      </AdminLayout>
    );
  }

  if (isError || !s) {
    return (
      <AdminLayout>
        <div className="h-full flex items-center justify-center bg-paper">
          <div className="text-center">
            <AlertCircle className="w-6 h-6 text-danger mx-auto mb-2" strokeWidth={1.5} />
            <p className="text-[13px] text-danger font-mono mb-1">Failed to load settings</p>
            <p className="text-[12px] text-text-3 font-mono max-w-sm">
              {error?.message || "The server returned an error. Please try again later."}
            </p>
          </div>
        </div>
      </AdminLayout>
    );
  }

  const allOllamaModels = s.availableModels?.ollama ?? [];
  const allProviderModels = s.availableModels?.provider ?? [];
  const baseModels = s.provider?.type === "openai_compatible" && allProviderModels.length > 0
    ? allProviderModels
    : allOllamaModels;
  const chatModelOptions = Array.from(new Set([...baseModels, s.generationModel, s.generationFallback].filter(Boolean)));
  const embeddingModelOptions = Array.from(new Set([...baseModels, s.embeddingModel].filter(Boolean)));
  const visionModelOptions = Array.from(new Set([...baseModels, s.visionModel].filter(Boolean)));

  return (
    <AdminLayout>
      <div className="h-full flex flex-col md:grid md:grid-cols-[200px_1fr] bg-paper">
        {/* Left nav */}
        <aside className="border-b border-line md:border-b-0 md:border-r p-4 md:sticky md:top-0 md:self-start overflow-x-auto">
          <div className="text-[10.5px] font-mono uppercase tracking-[.06em] text-text-3 mb-2 px-2">
            settings
          </div>
          <nav className="flex flex-row md:flex-col gap-0.5 overflow-x-auto pb-1 md:pb-0">
            {NAV.map(item => {
              const Ic = item.icon;
              const on = item.id === active;
              return (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  onClick={(e) => {
                    e.preventDefault();
                    setActive(item.id);
                    document.getElementById(item.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
                  }}
                  className={`flex items-center gap-2.5 h-7 px-2 rounded text-[12.5px] font-medium transition-colors
                    ${on ? "bg-surface shadow-sm text-ink ring-1 ring-line" : "text-text-2 hover:bg-surface-2"}`}>
                  <Ic className={`w-3.5 h-3.5 ${on ? "text-ink" : "text-text-3"}`} strokeWidth={1.5} />
                  {item.label}
                </a>
              );
            })}
          </nav>

          <div className="mt-6 p-3 rounded bg-paper-2 text-[11px] font-mono text-text-3 leading-relaxed">
            Changes save automatically. Applied to all users within ~30s. No restart needed.
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

            {/* PROVIDER */}
            {(() => {
              const providerModels = s.availableModels?.provider ?? [];
              const ollamaModels = s.availableModels?.ollama ?? [];
              const customProviderModels = s.availableModels?.customProvider ?? [];
              const modelOptions = provider.type === "openai_compatible" ? providerModels : ollamaModels;

              const saveCustomModels = async (models: string[]) => {
                setSavingCustomModels(true);
                try {
                  const next = await save.mutateAsync({ providerCustomModels: models });
                  qc.setQueryData<AppSettings>(["settings"], next);
                } catch (err) {
                  console.error("custom_models_save_failed", err);
                  setSaveErrorText(err instanceof Error ? err.message : "Failed to save custom models");
                } finally {
                  setSavingCustomModels(false);
                }
              };

              return (
                <Section id="provider" title="Inference provider"
                  subtitle="Choose the runtime that handles chat, embeddings and OCR. Use local Ollama or an OpenAI-compatible API (DeepSeek, OpenAI, Qwen, GLM, etc.).">
                  <Row label="Mode" hint="Local Ollama runs entirely on your server. OpenAI-compatible sends requests to an external API." saving={isSavingField("providerType")}>
                    <Select
                      value={provider.type}
                      options={["ollama", "openai_compatible"] as const}
                      onChange={(v) => set("provider", { ...provider, type: v })} />
                  </Row>
                  <Row label="Base URL" hint={provider.type === "ollama" ? "Default: http://localhost:11434" : "e.g. https://api.openai.com/v1 or https://api.deepseek.com/v1"} saving={isSavingField("providerBaseUrl")}>
                    <TextInput
                      value={provider.baseUrl}
                      onCommit={(v) => set("provider", { ...provider, baseUrl: v })} />
                  </Row>
                  {provider.type === "openai_compatible" && (
                    <Row label="API key" hint={provider.apiKeyConfigured ? "A key is configured. Enter a new key to rotate it." : "Required for API mode."} saving={isSavingField("providerApiKey")}>
                      <PasswordInput
                        placeholder={provider.apiKeyConfigured ? "Configured — enter to rotate" : "Paste API key"}
                        onCommit={(v) => { if (v) { queueSave({ providerApiKey: v }); setPendingApiKey(""); } }}
                        onChange={setPendingApiKey} />
                    </Row>
                  )}
                  <Row label="Chat model" hint="Used for query rewriting, grading, generation, and routing." saving={isSavingField("providerChatModel")}>
                    <ModelSelect
                      value={provider.chatModel}
                      options={modelOptions}
                      onChange={(v) => set("provider", { ...provider, chatModel: v })}
                      placeholder={provider.type === "ollama" ? "No Ollama models found" : "Select or add a model"} />
                  </Row>
                  <Row label="Embedding model" hint="Changing this requires reindexing the entire document corpus." saving={isSavingField("providerEmbeddingModel")}>
                    <ModelSelect
                      value={provider.embeddingModel}
                      options={modelOptions}
                      onChange={(v) => set("provider", { ...provider, embeddingModel: v })}
                      placeholder={provider.type === "ollama" ? "No Ollama models found" : "Select or add a model"} />
                  </Row>
                  <Row label="Vision model" hint="Used for OCR on PDF pages with insufficient text." saving={isSavingField("providerVisionModel")}>
                    <ModelSelect
                      value={provider.visionModel}
                      options={modelOptions}
                      onChange={(v) => set("provider", { ...provider, visionModel: v })}
                      placeholder={provider.type === "ollama" ? "No Ollama models found" : "Select or add a model"} />
                  </Row>

                  {/* Custom model management — only for OpenAI-compatible */}
                  {provider.type === "openai_compatible" && (
                    <div className="px-5 py-4 border-t border-line">
                      <div className="text-[12px] font-medium text-ink mb-1">Custom model names</div>
                      <div className="text-[11.5px] text-text-2 mb-3 max-w-[55ch]">
                        Add model IDs that aren't in the dropdown above — e.g. <span className="font-mono">deepseek-chat</span>, <span className="font-mono">qwen-plus</span>, <span className="font-mono">glm-4</span>. These are saved and appear in every model selector.
                      </div>
                      {customProviderModels.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mb-3">
                          {customProviderModels.map(m => (
                            <span key={m} className="inline-flex items-center gap-1 h-6 px-2 rounded-full bg-surface border border-line text-[11.5px] font-mono text-text">
                              {m}
                              <button
                                disabled={savingCustomModels}
                                onClick={() => saveCustomModels(customProviderModels.filter(x => x !== m))}
                                className="text-text-3 hover:text-danger disabled:opacity-40 ml-0.5"
                                aria-label={`Remove ${m}`}>
                                <X className="w-3 h-3" />
                              </button>
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={customModelInput}
                          onChange={e => setCustomModelInput(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === "Enter" && customModelInput.trim()) {
                              const name = customModelInput.trim();
                              setCustomModelInput("");
                              if (!customProviderModels.includes(name)) {
                                saveCustomModels([...customProviderModels, name]);
                              }
                            }
                          }}
                          placeholder="e.g. deepseek-chat"
                          className="w-52 h-8 px-2.5 rounded border border-line bg-surface text-[12.5px] font-mono outline-none focus:border-accent" />
                        <button
                          disabled={!customModelInput.trim() || savingCustomModels}
                          onClick={() => {
                            const name = customModelInput.trim();
                            if (!name) return;
                            setCustomModelInput("");
                            if (!customProviderModels.includes(name)) {
                              saveCustomModels([...customProviderModels, name]);
                            }
                          }}
                          className="inline-flex items-center gap-1.5 h-8 px-3 rounded border border-line bg-surface text-[12px] font-medium text-text hover:bg-paper-2 disabled:opacity-40">
                          <Plus className="w-3.5 h-3.5" />
                          Add
                        </button>
                        {savingCustomModels && (
                          <span className="text-[11px] font-mono text-accent animate-pulse">Saving…</span>
                        )}
                      </div>
                    </div>
                  )}

                  <Row label="SSE completion mode" hint="Strict waits for persistence before sending done; async returns done immediately for lower p99 latency." saving={isSavingField("sseDoneMode")}>
                    <Select
                      value={s.sseDoneMode}
                      options={["strict", "async"] as const}
                      onChange={(v) => set("sseDoneMode", v)} />
                  </Row>
                  <div className="px-5 py-3.5 flex items-center gap-3">
                    <button
                      disabled={testConnectionState === "testing"}
                      onClick={async () => {
                        setTestConnectionState("testing");
                        setTestConnectionMsg("");
                        try {
                          await testProviderConnection({
                            providerType: provider.type,
                            providerBaseUrl: provider.baseUrl,
                            ...(pendingApiKey ? { providerApiKey: pendingApiKey } : {}),
                          });
                          setTestConnectionState("ok");
                          setTestConnectionMsg("Connection successful");
                        } catch (err) {
                          setTestConnectionState("error");
                          setTestConnectionMsg(err instanceof Error ? err.message : "Connection failed");
                        }
                      }}
                      className="inline-flex items-center gap-1.5 h-7 px-3 rounded border border-line bg-surface text-[12px] font-medium text-text hover:bg-paper-2 disabled:opacity-50"
                    >
                      {testConnectionState === "testing" ? "Testing…" : "Test connection"}
                    </button>
                    {testConnectionState === "ok" && (
                      <span className="text-[12px] text-success font-mono">{testConnectionMsg}</span>
                    )}
                    {testConnectionState === "error" && (
                      <span className="text-[12px] text-danger font-mono">{testConnectionMsg}</span>
                    )}
                  </div>
                </Section>
              );
            })()}

            {/* MODELS */}
            <Section id="models" title="Models"
              subtitle="The generation model answers queries; the embedding model indexes documents. Reranker is optional but improves precision on noisy corpora.">
              <Row label="Generation model" hint="Used for every answer. Smaller = faster + cheaper." saving={isSavingField("generationModel")}>
                <Select
                  value={s.generationModel}
                  options={chatModelOptions}
                  onChange={(v) => set("generationModel", v)} />
              </Row>
              <Row label="Fallback model" hint="Tried on low-confidence retries. Set to the same model to disable." saving={isSavingField("generationFallback")}>
                <Select
                  value={s.generationFallback}
                  options={chatModelOptions}
                  onChange={(v) => set("generationFallback", v)} />
              </Row>
              <Row label="Embedding model" hint="Changing this triggers a full reindex of your corpus." saving={isSavingField("embeddingModel")}>
                <Select
                  value={s.embeddingModel}
                  options={embeddingModelOptions}
                  onChange={(v) => set("embeddingModel", v)} />
              </Row>
              <Row label="OCR model" hint="Used only for PDF pages that need vision fallback." saving={isSavingField("visionModel")}>
                <Select
                  value={s.visionModel}
                  options={visionModelOptions}
                  onChange={(v) => set("visionModel", v)} />
              </Row>
              <Row
                label="Reranker"
                hint="bge-reranker-v2 adds ~140ms p50 but lifts top-1 score by ~12% on our corpus."
                saving={isSavingField("rerankerEnabled") || isSavingField("rerankerModel")}
              >
                <div className="flex items-center gap-3">
                  <Toggle value={s.reranker.enabled}
                    onChange={(v) => set("reranker", { ...s.reranker, enabled: v })} />
                  <Select
                    value={s.reranker.model}
                    options={s.availableModels?.reranker ?? []}
                    onChange={(v) => set("reranker", { ...s.reranker, model: v })} />
                </div>
              </Row>
            </Section>

            {/* RETRIEVAL */}
            <Section id="retrieval" title="Retrieval"
              subtitle="How chunks are pulled from the index before the model sees them. Score floor governs when private·ai refuses to answer.">
              <Row label="Chunks retrieved (k)" hint="Higher k = more context, more tokens, more cost." saving={isSavingField("retrievalK")}>
                <NumberInput value={s.retrieval.k} min={1} max={32}
                  onChange={(v) => set("retrieval", { ...s.retrieval, k: v })} />
              </Row>
              <Row label="Score floor" hint="If the top-1 retrieval scores below this, private·ai falls back to “I don't know.”" saving={isSavingField("scoreFloor")}>
                <NumberInput value={s.retrieval.scoreFloor} min={0} max={1} step={0.05}
                  onChange={(v) => set("retrieval", { ...s.retrieval, scoreFloor: v })} />
              </Row>
              <Row label="Chunk size" hint="Tokens per chunk at index time." saving={isSavingField("chunkSize")}>
                <NumberInput value={s.retrieval.chunkSize} unit="tokens" min={128} max={2048} step={64}
                  onChange={(v) => set("retrieval", { ...s.retrieval, chunkSize: v })} />
              </Row>
              <Row label="Chunk overlap" hint="Tokens shared between adjacent chunks for better recall on boundary text." saving={isSavingField("chunkOverlap")}>
                <NumberInput value={s.retrieval.chunkOverlap} unit="tokens" min={0} max={512} step={16}
                  onChange={(v) => set("retrieval", { ...s.retrieval, chunkOverlap: v })} />
              </Row>
            </Section>

            {/* SOURCES */}
            <Section id="sources" title="Document sources"
              subtitle="Indexed locations watched for changes. Drop a file in any of these and it shows up in chat within ~30s.">
              {s.sources.map(src => (
                <SourceCard key={src.id} s={src} />
              ))}
            </Section>

            {/* SECURITY */}
            <Section id="security" title="Security"
              subtitle="Auth, session lifetime and how long the audit log keeps every prompt and retrieval.">
              <Row label="SSO only" hint="When on, password login is disabled and all sign-ins must go through your IdP." saving={isSavingField("ssoOnly")}>
                <Toggle value={s.security.ssoOnly}
                  onChange={(v) => set("security", { ...s.security, ssoOnly: v })} />
              </Row>
              <Row label="Session lifetime" hint="How long a JWT cookie is valid before re-auth." saving={isSavingField("sessionHours")}>
                <NumberInput value={s.security.sessionHours} unit="hours" min={1} max={720}
                  onChange={(v) => set("security", { ...s.security, sessionHours: v })} />
              </Row>
              <Row label="Audit retention" hint="After this, events are archived to immutable storage." saving={isSavingField("auditRetentionDays")}>
                <NumberInput value={s.security.auditRetentionDays} unit="days" min={30} max={3650}
                  onChange={(v) => set("security", { ...s.security, auditRetentionDays: v })} />
              </Row>
              <Row label="Redact PII in audit log" hint="Email addresses, phone numbers and names are hashed before being written to the audit stream." saving={isSavingField("redactPII")}>
                <Toggle value={s.security.redactPII}
                  onChange={(v) => set("security", { ...s.security, redactPII: v })} />
              </Row>
            </Section>

            {/* COST */}
            <Section id="cost" title="Cost ceiling"
              subtitle="A hard kill-switch on spend. When the daily ceiling is hit, the service falls back to read-only until midnight UTC.">
              <Row
                label="Today's spend"
                hint={`${s.cost.dailyCeilingUsd > 0
                  ? ((s.cost.todayUsd / s.cost.dailyCeilingUsd) * 100).toFixed(0)
                  : "0"}% of daily ceiling.`}
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[15px] tabular-nums text-ink font-medium">
                    ${s.cost.todayUsd.toFixed(2)}
                  </span>
                  <div className="w-32 h-1.5 rounded-full bg-paper-2 overflow-hidden">
                    <div
                      className="h-full bg-ink"
                      style={{
                        width: `${s.cost.dailyCeilingUsd > 0
                          ? Math.min(100, (s.cost.todayUsd / s.cost.dailyCeilingUsd) * 100)
                          : 0}%`,
                      }} />
                  </div>
                </div>
              </Row>
              <Row label="Daily ceiling" hint="Service degrades gracefully when hit — answers still served from cache." saving={isSavingField("dailyCeilingUsd")}>
                <NumberInput value={s.cost.dailyCeilingUsd} unit="USD" min={1} max={10000}
                  onChange={(v) => set("cost", { ...s.cost, dailyCeilingUsd: v })} />
              </Row>
              <Row label="Monthly ceiling" hint="A second guardrail on top of the daily one." saving={isSavingField("monthlyCeilingUsd")}>
                <NumberInput value={s.cost.monthlyCeilingUsd} unit="USD" min={30} max={300000}
                  onChange={(v) => set("cost", { ...s.cost, monthlyCeilingUsd: v })} />
              </Row>
            </Section>

            {saveErrorText && (
              <div className="flex items-center gap-2 p-3 rounded bg-danger-soft text-danger text-[12.5px]">
                <AlertCircle className="w-4 h-4 shrink-0" strokeWidth={1.5} />
                <span className="flex-1">{saveErrorText}</span>
                <button
                  className="text-[12px] underline hover:no-underline shrink-0"
                  onClick={() => {
                    setSaveErrorText(null);
                    if (Object.keys(unsavedDiffRef.current).length > 0) {
                      queueSave(unsavedDiffRef.current);
                    }
                  }}
                >
                  Retry
                </button>
              </div>
            )}

            {save.isPending && (
              <div className="flex items-center gap-2 p-3 rounded bg-accent-soft text-accent text-[12.5px]">
                Saving changes…
              </div>
            )}

            <footer className="mt-6 mb-4 flex items-center justify-between text-[11px] font-mono text-text-3">
              <span>loaded from server</span>
            </footer>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
