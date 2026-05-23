import { useRef, useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Brain,
  Search as SearchIcon,
  Folder,
  Lock,
  Activity,
  AlertCircle,
  Plug,
} from "lucide-react";
import { getSettings, patchSettings, type AppSettings, type PatchableSettings, type ProviderMode, type EmbeddingSource } from "../../api/settings";
import AdminLayout from "./AdminLayout";
import ProviderSettingsSection from "../../components/admin/ProviderSettingsSection";
import { Section, Row, Toggle, Select, NumberInput } from "../../components/admin/SettingsAtoms";

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
  | "sseDoneMode"
  | "providerMode"
  | "embeddingSource";

const DEFAULT_PROVIDER: AppSettings["provider"] = {
  type: "ollama",
  baseUrl: "http://localhost:11434",
  apiKeyConfigured: false,
  chatModel: "",
  embeddingModel: "",
  visionModel: "",
  embeddingSource: "ollama" as EmbeddingSource,
  providerMode: "local" as ProviderMode,
};

function SourceCard({ s }: { s: AppSettings["sources"][number] }) {
  return (
    <div className="px-5 py-4 flex items-center gap-4">
      <div className="w-8 h-8 rounded-md bg-paper-2 flex items-center justify-center text-[10px] font-mono font-semibold text-text-2 uppercase">
        fs
      </div>
      <div className="flex-1 min-w-0">
        <span className="text-[13px] font-medium text-ink truncate">{s.label}</span>
        <div className="text-[11.5px] font-mono text-text-3 truncate">
          {s.detail} · {s.docCount} docs indexed
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
  const [reindexRequired, setReindexRequired] = useState(false);
  const qc = useQueryClient();
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());
  const unsavedDiffRef = useRef<PatchableSettings>({});
  const scrollingRef = useRef(false);
  const contentRef = useRef<HTMLDivElement>(null);

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

  const applyDiff = (current: AppSettings, diff: PatchableSettings): AppSettings => {
    const currentMode = current.provider?.providerMode ?? "local";
    return ({
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
      // Local mode: chatModel tracks generationModel so the Provider section reflects changes instantly.
      chatModel: diff.providerChatModel
        ?? (currentMode === "local" && diff.generationModel != null ? diff.generationModel : undefined)
        ?? (current.provider?.chatModel ?? DEFAULT_PROVIDER.chatModel),
      // embeddingModel/visionModel: local mode saves these via top-level keys; keep provider in sync.
      embeddingModel: diff.providerEmbeddingModel
        ?? (diff.embeddingModel != null ? diff.embeddingModel : undefined)
        ?? (current.provider?.embeddingModel ?? DEFAULT_PROVIDER.embeddingModel),
      visionModel: diff.providerVisionModel
        ?? (diff.visionModel != null ? diff.visionModel : undefined)
        ?? (current.provider?.visionModel ?? DEFAULT_PROVIDER.visionModel),
      embeddingSource: (diff.embeddingSource ?? current.provider?.embeddingSource) ?? DEFAULT_PROVIDER.embeddingSource,
      providerMode: diff.providerMode ?? current.provider?.providerMode ?? DEFAULT_PROVIDER.providerMode,
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
  };

  const isSavingField = (field: string) => savingFields.includes(field as SaveField);

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
          if ((nextSettings as AppSettings & { reindexRequired?: boolean }).reindexRequired) {
            setReindexRequired(true);
          }
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
      const cur = s.provider ?? DEFAULT_PROVIDER;
      if (provider.type !== cur.type) diff.providerType = provider.type;
      if (provider.baseUrl !== cur.baseUrl) diff.providerBaseUrl = provider.baseUrl;
      if (provider.chatModel !== cur.chatModel) diff.providerChatModel = provider.chatModel;
      if (provider.embeddingModel !== cur.embeddingModel) diff.providerEmbeddingModel = provider.embeddingModel;
      if (provider.visionModel !== cur.visionModel) diff.providerVisionModel = provider.visionModel;
      if (provider.providerMode !== cur.providerMode) diff.providerMode = provider.providerMode;
    }
    if (key === "sseDoneMode" && value !== s.sseDoneMode) {
      diff.sseDoneMode = value as AppSettings["sseDoneMode"];
    }
    if (Object.keys(diff).length > 0) {
      queueSave(diff);
    }
  };

  // Sync active nav item with scroll position via IntersectionObserver.
  useEffect(() => {
    const root = contentRef.current;
    if (!root) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (scrollingRef.current) return;
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length > 0) {
          setActive(visible[0].target.id as SectionId);
        }
      },
      { root, threshold: 0.15 },
    );
    NAV.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

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
                    scrollingRef.current = true;
                    document.getElementById(item.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
                    // Re-enable observer-based tracking after scroll animation completes.
                    setTimeout(() => { scrollingRef.current = false; }, 800);
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
        <div className="overflow-auto" ref={contentRef}>
          <div className="max-w-3xl mx-auto px-8 py-8">

            <header className="mb-8">
              <div className="text-[10.5px] font-mono uppercase tracking-[.06em] text-text-3 mb-1.5">configuration</div>
              <h1 className="text-[28px] italic font-serif text-ink tracking-tight">Settings</h1>
              <p className="text-[13.5px] text-text-2 mt-1.5">
                Tune how private·ai retrieves, generates and audits. Every change here is itself audited.
              </p>
            </header>

            {/* PROVIDER */}
            <ProviderSettingsSection
              provider={provider}
              availableModels={s.availableModels}
              isSavingField={isSavingField}
              queueSave={queueSave}
              onSaveCustomModels={async (models) => {
                const next = await save.mutateAsync({ providerCustomModels: models });
                qc.setQueryData<AppSettings>(["settings"], next);
              }}
              onSaveError={(msg) => setSaveErrorText(msg)}
            />

            {/* Reindex warning banner */}
            {reindexRequired && (
              <div className="flex items-center gap-3 mb-6 px-4 py-3 rounded-lg bg-amber-50 border border-amber-200 text-[12.5px] text-amber-900">
                <AlertCircle className="w-4 h-4 shrink-0 text-amber-600" strokeWidth={1.5} />
                <span className="flex-1">
                  Embedding configuration changed — reindex all documents to apply the new embedding model.
                </span>
                <button className="shrink-0 text-[12px] underline hover:no-underline" onClick={() => setReindexRequired(false)}>
                  Dismiss
                </button>
              </div>
            )}

            {/* MODELS */}
            <Section id="models" title="Models"
              subtitle="The fallback model is tried on low-confidence retries. Reranker is optional but improves precision on noisy corpora.">
              <Row label="Fallback model" hint="Tried on low-confidence retries. Set to the same model to disable." saving={isSavingField("generationFallback")}>
                <Select
                  value={s.generationFallback}
                  options={chatModelOptions}
                  onChange={(v) => set("generationFallback", v)} />
              </Row>
              <Row
                label="Reranker"
                hint="Supported options — verify the model is installed on your server before enabling. bge-reranker-v2 adds ~140ms p50 but lifts top-1 score by ~12%."
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
              <Row label="SSE completion mode" hint="Strict waits for persistence before sending done; async returns done immediately for lower p99 latency." saving={isSavingField("sseDoneMode")}>
                <Select value={s.sseDoneMode} options={["strict", "async"] as const}
                  onChange={(v) => set("sseDoneMode", v)} className="w-48" />
              </Row>
            </Section>

            {/* SOURCES */}
            <Section id="sources" title="Document sources"
              subtitle="Read-only — the local filesystem watch path is configured at deployment time. Drop a file in the directory below and it shows up in chat within ~30s.">
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
