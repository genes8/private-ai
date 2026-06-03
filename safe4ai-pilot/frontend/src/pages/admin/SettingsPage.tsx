import { useRef, useState, useEffect, useLayoutEffect } from "react";
import { Brain, Search as SearchIcon, Folder, Lock, Activity, AlertCircle, Plug, BadgeCheck } from "lucide-react";
import { type AppSettings, type TierName } from "../../api/settings";
import AdminLayout from "./AdminLayout";
import ProviderSettingsSection from "../../components/admin/ProviderSettingsSection";
import { Section, Row, Toggle, Select, NumberInput, TextInput, PasswordInput } from "../../components/admin/SettingsAtoms";
import { useSettings } from "../../hooks/useSettings";

// ── Navigation ────────────────────────────────────────────────────────────────

type SectionId = "provider" | "tier" | "models" | "retrieval" | "sources" | "security" | "cost";

const NAV: Array<{
  id: SectionId;
  label: string;
  icon: React.ComponentType<{ className?: string; strokeWidth?: string | number }>;
}> = [
  { id: "provider",  label: "Provider",         icon: Plug },
  { id: "tier",      label: "Tier",             icon: BadgeCheck },
  { id: "models",    label: "Models",           icon: Brain },
  { id: "retrieval", label: "Retrieval",        icon: SearchIcon },
  { id: "sources",   label: "Document sources", icon: Folder },
  { id: "security",  label: "Security",         icon: Lock },
  { id: "cost",      label: "Cost ceiling",     icon: Activity },
];

// ── Sub-components ────────────────────────────────────────────────────────────

function SourceCard({ s }: { s: AppSettings["sources"][number] }) {
  return (
    <div className="px-5 py-4 flex items-center gap-4">
      <div className="size-8 rounded-md bg-paper-2 flex items-center justify-center text-[10px] font-mono font-semibold text-text-2 uppercase">
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

function SettingsLoadingState() {
  return (
    <AdminLayout>
      <div className="h-full flex items-center justify-center bg-paper">
        <span className="text-[13px] text-text-mute font-mono">Loading settings…</span>
      </div>
    </AdminLayout>
  );
}

function SettingsErrorState({ message }: { message?: string }) {
  return (
    <AdminLayout>
      <div className="h-full flex items-center justify-center bg-paper">
        <div className="text-center">
          <AlertCircle className="size-6 text-danger mx-auto mb-2" strokeWidth={1.5} />
          <p className="text-[13px] text-danger font-mono mb-1">Failed to load settings</p>
          <p className="text-[12px] text-text-3 font-mono max-w-sm">
            {message ?? "The server returned an error. Please try again later."}
          </p>
        </div>
      </div>
    </AdminLayout>
  );
}

function compactLimit(value: number, unit: string) {
  return value > 0 ? `${value.toLocaleString()} ${unit}` : `Unlimited ${unit}`;
}

function TermsInput({
  value,
  onCommit,
  placeholder = "mrn\npatient identifier",
}: {
  value: string[];
  onCommit: (terms: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState(value.join("\n"));

  useLayoutEffect(() => {
    setDraft(value.join("\n"));
  }, [value]);

  const commit = () => {
    const next = Array.from(
      new Set(
        draft
          .split(/[\n,]/)
          .map((term) => term.trim().toLowerCase())
          .filter(Boolean),
      ),
    );
    if (next.join("\n") !== value.join("\n")) onCommit(next);
  };

  return (
    <textarea
      aria-label="Blocked terms"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      rows={4}
      className="w-80 max-w-full resize-y rounded border border-line bg-surface px-2.5 py-2 text-[12.5px] font-mono text-text outline-none focus:border-accent"
      placeholder={placeholder}
    />
  );
}

function DateTimeInput({
  value,
  onCommit,
}: {
  value: string | null;
  onCommit: (value: string | null) => void;
}) {
  const localValue = value ? value.slice(0, 16) : "";

  return (
    <input
      type="datetime-local"
      aria-label="Tier expiry"
      key={localValue}
      defaultValue={localValue}
      onBlur={(e) => {
        const raw = e.currentTarget.value;
        onCommit(raw ? new Date(raw).toISOString() : null);
      }}
      className="h-8 w-52 px-2.5 rounded border border-line bg-surface text-[12.5px] font-mono outline-none focus:border-accent"
    />
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [active, setActive] = useState<SectionId>("models");
  const scrollingRef = useRef(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const {
    s,
    isLoading,
    isError,
    error,
    provider,
    set,
    queueSave,
    isSavingField,
    isSaving,
    saveErrorText,
    reindexRequired,
    retryUnsaved,
    dismissReindexWarning,
    onSaveCustomModels,
  } = useSettings();

  // Sync active nav item with scroll position.
  useEffect(() => {
    const root = contentRef.current;
    if (!root) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (scrollingRef.current) return;
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length > 0) setActive(visible[0].target.id as SectionId);
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
    return <SettingsLoadingState />;
  }

  if (isError || !s) {
    return <SettingsErrorState message={error?.message} />;
  }

  const allOllamaModels = s.availableModels?.ollama ?? [];
  const allProviderModels = s.availableModels?.provider ?? [];
  const baseModels =
    s.provider?.type === "openai_compatible" && allProviderModels.length > 0
      ? allProviderModels
      : allOllamaModels;
  const chatModelOptions = Array.from(
    new Set([...baseModels, s.generationModel, s.generationFallback].filter(Boolean)),
  );
  const tierOptions: TierName[] = ["evaluation", "team", "enterprise"];

  return (
    <AdminLayout>
      <div className="h-full flex flex-col md:grid md:grid-cols-[200px_1fr] bg-paper">
        {/* Left nav */}
        <aside className="border-b border-line md:border-b-0 md:border-r p-4 md:sticky md:top-0 md:self-start overflow-x-auto">
          <div className="text-[10.5px] font-mono uppercase tracking-[.06em] text-text-3 mb-2 px-2">
            settings
          </div>
          <nav className="flex flex-row md:flex-col gap-0.5 overflow-x-auto pb-1 md:pb-0">
            {NAV.map((item) => {
              const Ic = item.icon;
              const on = item.id === active;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setActive(item.id);
                    scrollingRef.current = true;
                    document
                      .getElementById(item.id)
                      ?.scrollIntoView({ behavior: "smooth", block: "start" });
                    setTimeout(() => { scrollingRef.current = false; }, 800);
                  }}
                  className={`flex items-center gap-2.5 h-7 px-2 rounded text-[12.5px] font-medium transition-colors
                    ${on ? "bg-surface shadow-sm text-ink ring-1 ring-line" : "text-text-2 hover:bg-surface-2"}`}
                >
                  <Ic className={`size-3.5 ${on ? "text-ink" : "text-text-3"}`} strokeWidth={1.5} />
                  {item.label}
                </button>
              );
            })}
          </nav>
          <div className="mt-6 p-3 rounded bg-paper-2 text-[11px] font-mono text-text-3 leading-relaxed">
            Changes save automatically. Applied to all users within ~30s. No restart needed.
          </div>
        </aside>

        {/* Content */}
        <div className="overflow-auto" ref={contentRef}>
          <div className="max-w-3xl mx-auto p-8">
            <header className="mb-8">
              <div className="text-[10.5px] font-mono uppercase tracking-[.06em] text-text-3 mb-1.5">
                configuration
              </div>
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
              onSaveCustomModels={onSaveCustomModels}
              onSaveError={(msg) => console.error("settings_save_error", msg)}
            />

            {/* TIER */}
            <Section id="tier" title="Tier" subtitle="License limits enforced before user creation and chat execution.">
              <Row label="Current tier" hint="Controls default seat and monthly query policy." saving={isSavingField("tier")}>
                <Select<TierName>
                  value={s.tier.name}
                  options={tierOptions}
                  onChange={(v) => set("tier", { ...s.tier, name: v })}
                  className="w-40"
                />
              </Row>
              <Row label="Seats" hint={compactLimit(s.tier.maxSeats, "seats")} saving={isSavingField("maxSeats")}>
                <NumberInput
                  value={s.tier.maxSeats}
                  min={0}
                  max={10000}
                  onChange={(v) => set("tier", { ...s.tier, maxSeats: v })}
                />
              </Row>
              <Row
                label="Monthly queries"
                hint={compactLimit(s.tier.monthlyQueryLimit, "queries")}
                saving={isSavingField("monthlyQueryLimit")}
              >
                <NumberInput
                  value={s.tier.monthlyQueryLimit}
                  min={0}
                  max={10000000}
                  step={100}
                  onChange={(v) => set("tier", { ...s.tier, monthlyQueryLimit: v })}
                />
              </Row>
              <Row label="Tier expiry" hint="Leave empty for no expiry." saving={isSavingField("tierExpiresAt")}>
                <DateTimeInput
                  value={s.tier.tierExpiresAt}
                  onCommit={(v) => set("tier", { ...s.tier, tierExpiresAt: v })}
                />
              </Row>
              <Row label="Current usage" hint="Read from active users and this month's audit entries.">
                <div className="flex flex-wrap items-center justify-end gap-2 text-[12px] font-mono text-text-2">
                  <span className="rounded border border-line px-2 py-1">
                    {s.tier.seatsUsed.toLocaleString()} seats
                  </span>
                  <span className="rounded border border-line px-2 py-1">
                    {s.tier.monthlyQueriesUsed.toLocaleString()} queries
                  </span>
                </div>
              </Row>
            </Section>

            {/* Reindex warning */}
            {reindexRequired && (
              <div className="flex items-center gap-3 mb-6 px-4 py-3 rounded-lg bg-amber-50 border border-amber-200 text-[12.5px] text-amber-900">
                <AlertCircle className="size-4 shrink-0 text-amber-600" strokeWidth={1.5} />
                <span className="flex-1">
                  Embedding configuration changed, reindex all documents to apply the new
                  embedding model.
                </span>
                <button
                  type="button"
                  className="shrink-0 text-[12px] underline hover:no-underline"
                  onClick={dismissReindexWarning}
                >
                  Dismiss
                </button>
              </div>
            )}

            {/* MODELS */}
            <Section
              id="models"
              title="Models"
              subtitle="The fallback model is tried on low-confidence retries. Reranker is optional but improves precision on noisy corpora."
            >
              <Row
                label="Fallback model"
                hint="Tried on low-confidence retries. Set to the same model to disable."
                saving={isSavingField("generationFallback")}
              >
                <Select
                  value={s.generationFallback}
                  options={chatModelOptions}
                  onChange={(v) => set("generationFallback", v)}
                />
              </Row>
              <Row
                label="Reranker"
                hint="bge-reranker-v2 adds ~140ms p50 but lifts top-1 score by ~12%."
                saving={isSavingField("rerankerEnabled") || isSavingField("rerankerModel")}
              >
                <div className="flex items-center gap-3">
                  <Toggle
                    value={s.reranker.enabled}
                    onChange={(v) => set("reranker", { ...s.reranker, enabled: v })}
                  />
                  <Select
                    value={s.reranker.model}
                    options={s.availableModels?.reranker ?? []}
                    onChange={(v) => set("reranker", { ...s.reranker, model: v })}
                  />
                </div>
              </Row>
            </Section>

            {/* RETRIEVAL */}
            <Section
              id="retrieval"
              title="Retrieval"
              subtitle="How chunks are pulled from the index before the model sees them."
            >
              <Row label="Chunks retrieved (k)" hint="Higher k = more context, more tokens, more cost." saving={isSavingField("retrievalK")}>
                <NumberInput value={s.retrieval.k} min={1} max={32}
                  onChange={(v) => set("retrieval", { ...s.retrieval, k: v })} />
              </Row>
              <Row label="Score floor" hint={"Below this score, private·ai returns “I don’t know.”"} saving={isSavingField("scoreFloor")}>
                <NumberInput value={s.retrieval.scoreFloor} min={0} max={1} step={0.05}
                  onChange={(v) => set("retrieval", { ...s.retrieval, scoreFloor: v })} />
              </Row>
              <Row label="Chunk size" hint="Tokens per chunk at index time." saving={isSavingField("chunkSize")}>
                <NumberInput value={s.retrieval.chunkSize} unit="tokens" min={128} max={2048} step={64}
                  onChange={(v) => set("retrieval", { ...s.retrieval, chunkSize: v })} />
              </Row>
              <Row label="Chunk overlap" hint="Tokens shared between adjacent chunks." saving={isSavingField("chunkOverlap")}>
                <NumberInput value={s.retrieval.chunkOverlap} unit="tokens" min={0} max={512} step={16}
                  onChange={(v) => set("retrieval", { ...s.retrieval, chunkOverlap: v })} />
              </Row>
              <Row label="SSE completion mode" hint="Strict waits for persistence before done; async returns done immediately." saving={isSavingField("sseDoneMode")}>
                <Select value={s.sseDoneMode} options={["strict", "async"] as const}
                  onChange={(v) => set("sseDoneMode", v)} className="w-48" />
              </Row>
            </Section>

            {/* SOURCES */}
            <Section
              id="sources"
              title="Document sources"
              subtitle="Read-only; the local filesystem watch path is configured at deployment time."
            >
              {s.sources.map((src) => <SourceCard key={src.id} s={src} />)}
            </Section>

            {/* SECURITY */}
            <Section id="security" title="Security" subtitle="Auth, session lifetime and audit log retention.">
              <Row label="SSO only" hint="Disables password login after OIDC is configured." saving={isSavingField("ssoOnly")}>
                <Toggle value={s.security.ssoOnly}
                  onChange={(v) => set("security", { ...s.security, ssoOnly: v })} />
              </Row>
              <Row
                label="OIDC provider"
                hint={s.security.oidc.configured ? "Ready for browser SSO login." : "Issuer, client ID, secret and redirect URI are required."}
                saving={isSavingField("oidcEnabled")}
              >
                <div className="flex items-center gap-3">
                  <Toggle
                    value={s.security.oidc.enabled}
                    onChange={(v) =>
                      set("security", {
                        ...s.security,
                        oidc: { ...s.security.oidc, enabled: v },
                      })
                    }
                  />
                  <span className="rounded border border-line px-2 py-1 text-[11px] font-mono text-text-2">
                    {s.security.oidc.configured ? "configured" : "incomplete"}
                  </span>
                </div>
              </Row>
              <Row label="Issuer URL" hint="OIDC discovery URL root." saving={isSavingField("oidcIssuerUrl")}>
                <TextInput
                  value={s.security.oidc.issuerUrl}
                  onCommit={(v) =>
                    set("security", {
                      ...s.security,
                      oidc: { ...s.security.oidc, issuerUrl: v },
                    })
                  }
                />
              </Row>
              <Row label="Client ID" hint="Registered OIDC application client ID." saving={isSavingField("oidcClientId")}>
                <TextInput
                  value={s.security.oidc.clientId}
                  onCommit={(v) =>
                    set("security", {
                      ...s.security,
                      oidc: { ...s.security.oidc, clientId: v },
                    })
                  }
                />
              </Row>
              <Row label="Client secret" hint={s.security.oidc.clientSecretConfigured ? "Secret is configured; enter a new value to rotate." : "Required before SSO can be used."} saving={isSavingField("oidcClientSecret")}>
                <PasswordInput
                  placeholder={s.security.oidc.clientSecretConfigured ? "configured" : "not configured"}
                  onCommit={(v) => queueSave({ oidcClientSecret: v })}
                />
              </Row>
              <Row label="Redirect URI" hint="Must match the IdP app registration callback." saving={isSavingField("oidcRedirectUri")}>
                <TextInput
                  value={s.security.oidc.redirectUri}
                  onCommit={(v) =>
                    set("security", {
                      ...s.security,
                      oidc: { ...s.security.oidc, redirectUri: v },
                    })
                  }
                />
              </Row>
              <Row
                label="Allowed domains"
                hint="Empty allows any verified OIDC email domain."
                saving={isSavingField("oidcAllowedDomains")}
              >
                <TermsInput
                  value={s.security.oidc.allowedDomains}
                  placeholder={"example.com\nsubsidiary.example"}
                  onCommit={(domains) =>
                    set("security", {
                      ...s.security,
                      oidc: { ...s.security.oidc, allowedDomains: domains },
                    })
                  }
                />
              </Row>
              <Row label="Auto-provision users" hint="Creates pilot users after verified OIDC login when no local user exists." saving={isSavingField("oidcAutoProvision")}>
                <Toggle
                  value={s.security.oidc.autoProvision}
                  onChange={(v) =>
                    set("security", {
                      ...s.security,
                      oidc: { ...s.security.oidc, autoProvision: v },
                    })
                  }
                />
              </Row>
              <Row label="Session lifetime" hint="How long a JWT cookie is valid before re-auth." saving={isSavingField("sessionHours")}>
                <NumberInput value={s.security.sessionHours} unit="hours" min={1} max={720}
                  onChange={(v) => set("security", { ...s.security, sessionHours: v })} />
              </Row>
              <Row label="Audit retention" hint="Cleanup removes expired rows after archive export is configured." saving={isSavingField("auditRetentionDays")}>
                <NumberInput value={s.security.auditRetentionDays} unit="days" min={30} max={3650}
                  onChange={(v) => set("security", { ...s.security, auditRetentionDays: v })} />
              </Row>
              <Row
                label="Blocked terms"
                hint="Queries and retrieved chunks containing these terms are blocked from generation."
                saving={isSavingField("blockedTerms")}
              >
                <TermsInput
                  value={s.security.blockedTerms ?? []}
                  onCommit={(terms) => set("security", { ...s.security, blockedTerms: terms })}
                />
              </Row>
              <Row label="Redact PII in audit log" hint="Emails, phone numbers and names are hashed before the audit stream." saving={isSavingField("redactPII")}>
                <Toggle value={s.security.redactPII}
                  onChange={(v) => set("security", { ...s.security, redactPII: v })} />
              </Row>
            </Section>

            {/* COST */}
            <Section id="cost" title="Cost ceiling" subtitle="A hard kill-switch on spend.">
              <Row
                label="Today's spend"
                hint={`${s.cost.dailyCeilingUsd > 0 ? ((s.cost.todayUsd / s.cost.dailyCeilingUsd) * 100).toFixed(0) : "0"}% of daily ceiling.`}
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[15px] tabular-nums text-ink font-medium">
                    ${s.cost.todayUsd.toFixed(2)}
                  </span>
	                <div className="h-1.5 w-32 rounded-full bg-paper-2 overflow-hidden">
                    <div
                      className="h-full bg-ink"
                      style={{
                        width: `${s.cost.dailyCeilingUsd > 0 ? Math.min(100, (s.cost.todayUsd / s.cost.dailyCeilingUsd) * 100) : 0}%`,
                      }}
                    />
                  </div>
                </div>
              </Row>
              <Row label="Daily ceiling" hint="Service degrades gracefully when hit." saving={isSavingField("dailyCeilingUsd")}>
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
                <AlertCircle className="size-4 shrink-0" strokeWidth={1.5} />
                <span className="flex-1">{saveErrorText}</span>
                <button type="button" className="text-[12px] underline hover:no-underline shrink-0" onClick={retryUnsaved}>
                  Retry
                </button>
              </div>
            )}

            {isSaving && (
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
