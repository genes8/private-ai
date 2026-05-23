import { useState } from "react";
import { Server, CloudLightning, Cloud, Plus, X } from "lucide-react";
import { testProviderConnection, type AppSettings, type PatchableSettings, type ProviderMode } from "../../api/settings";
import { Section, Row, Select, TextInput, PasswordInput, ModelSelect } from "./SettingsAtoms";

// ── Types ─────────────────────────────────────────────────────────────────────

type ModeCard = {
  id: ProviderMode;
  title: string;
  subtitle: string;
  badge?: string;
  Icon: React.ComponentType<{ className?: string; strokeWidth?: string | number }>;
};

const MODE_CARDS: ModeCard[] = [
  { id: "local", title: "Local only", subtitle: "Chat and document search run entirely on your server via Ollama. No data leaves.", Icon: Server },
  { id: "hybrid", title: "Hybrid", subtitle: "Cloud LLM for answers, Ollama for document search. Best quality — documents stay local.", badge: "Recommended", Icon: CloudLightning },
  { id: "cloud", title: "Fully cloud", subtitle: "Chat and document search both via a cloud API (requires /embeddings support, e.g. OpenAI).", Icon: Cloud },
];

// ── Props ─────────────────────────────────────────────────────────────────────

interface ProviderSettingsSectionProps {
  provider: AppSettings["provider"];
  availableModels: AppSettings["availableModels"];
  sseDoneMode: AppSettings["sseDoneMode"];
  isSavingField: (field: string) => boolean;
  queueSave: (diff: PatchableSettings) => void;
  onSaveCustomModels: (models: string[]) => Promise<void>;
  onSaveError: (msg: string) => void;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ProviderSettingsSection({
  provider,
  availableModels,
  sseDoneMode,
  isSavingField,
  queueSave,
  onSaveCustomModels,
  onSaveError,
}: ProviderSettingsSectionProps) {
  const [testState, setTestState] = useState<"idle" | "testing" | "ok" | "error">("idle");
  const [testMsg, setTestMsg] = useState("");
  const [pendingApiKey, setPendingApiKey] = useState("");
  const [customModelInput, setCustomModelInput] = useState("");
  const [savingCustomModels, setSavingCustomModels] = useState(false);

  const providerModels = availableModels?.provider ?? [];
  const ollamaModels = availableModels?.ollama ?? [];
  const customProviderModels = availableModels?.customProvider ?? [];
  const mode = provider.providerMode ?? "local";

  const saveCustomModels = async (models: string[]) => {
    setSavingCustomModels(true);
    try {
      await onSaveCustomModels(models);
    } catch (err) {
      onSaveError(err instanceof Error ? err.message : "Failed to save custom models");
    } finally {
      setSavingCustomModels(false);
    }
  };

  const CustomModelManager = () => (
    <div className="px-5 py-4 border-t border-line">
      <div className="text-[12px] font-medium text-ink mb-1">Custom model names</div>
      <div className="text-[11.5px] text-text-2 mb-3 max-w-[55ch]">
        Add model IDs that aren't in the dropdown above — e.g.{" "}
        <span className="font-mono">deepseek-v4-flash</span>,{" "}
        <span className="font-mono">qwen-plus</span>,{" "}
        <span className="font-mono">glm-4</span>.
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
              if (!customProviderModels.includes(name)) saveCustomModels([...customProviderModels, name]);
            }
          }}
          placeholder="e.g. deepseek-v4-flash"
          className="w-52 h-8 px-2.5 rounded border border-line bg-surface text-[12.5px] font-mono outline-none focus:border-accent" />
        <button
          disabled={!customModelInput.trim() || savingCustomModels}
          onClick={() => {
            const name = customModelInput.trim();
            if (!name) return;
            setCustomModelInput("");
            if (!customProviderModels.includes(name)) saveCustomModels([...customProviderModels, name]);
          }}
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded border border-line bg-surface text-[12px] font-medium text-text hover:bg-paper-2 disabled:opacity-40">
          <Plus className="w-3.5 h-3.5" />
          Add
        </button>
        {savingCustomModels && <span className="text-[11px] font-mono text-accent animate-pulse">Saving…</span>}
      </div>
    </div>
  );

  return (
    <Section id="provider" title="Inference provider"
      subtitle="Choose how AI models are served. Hybrid gives you cloud quality with local privacy.">

      {/* Mode selector cards */}
      <div className="px-5 py-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
        {MODE_CARDS.map(({ id, title, subtitle, badge, Icon }) => {
          const selected = mode === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => queueSave({ providerMode: id })}
              className={`relative flex flex-col items-start gap-2 p-4 rounded-lg border text-left transition-all ${
                selected ? "border-ink bg-ink/5 ring-1 ring-ink shadow-sm" : "border-line bg-surface hover:bg-paper-2"
              }`}>
              {badge && (
                <span className="absolute top-2.5 right-2.5 inline-flex items-center h-4 px-1.5 rounded-full bg-accent text-[9px] font-mono font-semibold text-paper uppercase tracking-wide">
                  {badge}
                </span>
              )}
              <div className={`w-7 h-7 rounded-md flex items-center justify-center ${selected ? "bg-ink text-paper" : "bg-paper-2 text-text-2"}`}>
                <Icon className="w-4 h-4" strokeWidth={1.5} />
              </div>
              <div>
                <div className={`text-[13px] font-medium ${selected ? "text-ink" : "text-text"}`}>{title}</div>
                <div className="text-[11.5px] text-text-2 mt-0.5 leading-relaxed">{subtitle}</div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Local mode: all models from Ollama */}
      {mode === "local" && (
        <>
          <Row label="Chat model" hint="Used for query rewriting, grading, generation, and routing." saving={isSavingField("generationModel")}>
            <ModelSelect value={provider.chatModel} options={ollamaModels}
              onChange={v => queueSave({ generationModel: v })} placeholder="No Ollama models found" />
          </Row>
          <Row label="Embedding model" hint="Changing this requires reindexing the entire document corpus." saving={isSavingField("embeddingModel")}>
            <ModelSelect value={provider.embeddingModel} options={ollamaModels}
              onChange={v => queueSave({ embeddingModel: v })} placeholder="No Ollama models found" />
          </Row>
          <Row label="Vision model" hint="Used for OCR on PDF pages with insufficient text." saving={isSavingField("visionModel")}>
            <ModelSelect value={provider.visionModel} options={ollamaModels}
              onChange={v => queueSave({ visionModel: v })} placeholder="No Ollama models found" />
          </Row>
        </>
      )}

      {/* Hybrid mode: cloud chat, Ollama embeddings + vision */}
      {mode === "hybrid" && (
        <>
          <Row label="API base URL" hint="e.g. https://api.deepseek.com/v1" saving={isSavingField("providerBaseUrl")}>
            <TextInput value={provider.baseUrl} onCommit={v => queueSave({ providerBaseUrl: v })} />
          </Row>
          <Row label="API key"
            hint={provider.apiKeyConfigured ? "A key is configured. Enter a new key to rotate it." : "Required for cloud API access."}
            saving={isSavingField("providerApiKey")}>
            <PasswordInput
              placeholder={provider.apiKeyConfigured ? "Configured — enter to rotate" : "Paste API key"}
              onCommit={v => { if (v) { queueSave({ providerApiKey: v }); setPendingApiKey(""); } }}
              onChange={setPendingApiKey} />
          </Row>
          <Row label="Chat model" hint="Model for answers — e.g. deepseek-v4-flash or deepseek-reasoner." saving={isSavingField("providerChatModel")}>
            <ModelSelect value={provider.chatModel} options={providerModels}
              onChange={v => queueSave({ providerChatModel: v })} placeholder="Select or add a model" />
          </Row>
          <div className="px-5 py-3 flex items-start gap-2.5 bg-blue-50/60 border-t border-line">
            <svg className="w-4 h-4 mt-0.5 text-blue-500 shrink-0" viewBox="0 0 16 16" fill="currentColor">
              <circle cx="8" cy="8" r="7" fillOpacity=".15" />
              <path d="M7.25 6.5h1.5v5h-1.5zm0-2.5h1.5v1.5h-1.5z" />
            </svg>
            <p className="text-[12px] text-text-2 leading-relaxed">
              Document search embeddings are always generated by{" "}
              <span className="font-mono text-text">nomic-embed-text</span> on your local Ollama.
              DeepSeek does not provide an <span className="font-mono text-text">/embeddings</span> API — no documents leave your server.
            </p>
          </div>
          <CustomModelManager />
        </>
      )}

      {/* Cloud mode: chat + embeddings + vision from cloud provider */}
      {mode === "cloud" && (
        <>
          <Row label="API base URL" hint="e.g. https://api.openai.com/v1" saving={isSavingField("providerBaseUrl")}>
            <TextInput value={provider.baseUrl} onCommit={v => queueSave({ providerBaseUrl: v })} />
          </Row>
          <Row label="API key"
            hint={provider.apiKeyConfigured ? "A key is configured. Enter a new key to rotate it." : "Required for cloud API access."}
            saving={isSavingField("providerApiKey")}>
            <PasswordInput
              placeholder={provider.apiKeyConfigured ? "Configured — enter to rotate" : "Paste API key"}
              onCommit={v => { if (v) { queueSave({ providerApiKey: v }); setPendingApiKey(""); } }}
              onChange={setPendingApiKey} />
          </Row>
          <Row label="Chat model" hint="Model for answers — e.g. gpt-4o or gpt-4o-mini." saving={isSavingField("providerChatModel")}>
            <ModelSelect value={provider.chatModel} options={providerModels}
              onChange={v => queueSave({ providerChatModel: v })} placeholder="Select or add a model" />
          </Row>
          <Row label="Embedding model" hint="Changing this requires reindexing. Use text-embedding-3-small or ada-002." saving={isSavingField("providerEmbeddingModel")}>
            <ModelSelect value={provider.embeddingModel} options={providerModels}
              onChange={v => queueSave({ providerEmbeddingModel: v })} placeholder="Select or add a model" />
          </Row>
          <Row label="Vision model" hint="Used for OCR on PDF pages with insufficient text." saving={isSavingField("providerVisionModel")}>
            <ModelSelect value={provider.visionModel} options={providerModels}
              onChange={v => queueSave({ providerVisionModel: v })} placeholder="Select or add a model" />
          </Row>
          <CustomModelManager />
        </>
      )}

      <Row label="SSE completion mode"
        hint="Strict waits for persistence before sending done; async returns done immediately for lower p99 latency."
        saving={isSavingField("sseDoneMode")}>
        <Select value={sseDoneMode} options={["strict", "async"] as const}
          onChange={v => queueSave({ sseDoneMode: v })} className="w-48" />
      </Row>

      {/* Footer: local note or cloud connection test */}
      <div className="px-5 py-3.5 flex items-center gap-3">
        {mode === "local" ? (
          <span className="text-[12px] text-text-3 font-mono">Local Ollama — no API key required</span>
        ) : (
          <>
            <button
              disabled={testState === "testing"}
              onClick={async () => {
                setTestState("testing");
                setTestMsg("");
                try {
                  await testProviderConnection({
                    providerType: "openai_compatible",
                    providerBaseUrl: provider.baseUrl,
                    ...(pendingApiKey ? { providerApiKey: pendingApiKey } : {}),
                  });
                  setTestState("ok");
                  setTestMsg("Cloud provider connected");
                } catch (err) {
                  setTestState("error");
                  setTestMsg(err instanceof Error ? err.message : "Connection failed");
                }
              }}
              className="inline-flex items-center gap-1.5 h-7 px-3 rounded border border-line bg-surface text-[12px] font-medium text-text hover:bg-paper-2 disabled:opacity-50">
              {testState === "testing" ? "Testing…" : "Test cloud connection"}
            </button>
            {testState === "ok" && <span className="text-[12px] text-success font-mono">{testMsg}</span>}
            {testState === "error" && <span className="text-[12px] text-danger font-mono">{testMsg}</span>}
          </>
        )}
      </div>
    </Section>
  );
}
