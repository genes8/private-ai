/**
 * useSettings — encapsulates all settings query, mutation, optimistic-update,
 * and save-queue logic so that SettingsPage.tsx stays a thin rendering shell.
 *
 * Extracted from admin/SettingsPage.tsx (H5 audit item).
 */
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getSettings,
  patchSettings,
  type AppSettings,
  type EmbeddingSource,
  type PatchableSettings,
  type ProviderMode,
} from "../api/settings";

// ── Types ────────────────────────────────────────────────────────────────────

export type SaveField =
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

// ── Constants ─────────────────────────────────────────────────────────────────

export const DEFAULT_PROVIDER: AppSettings["provider"] = {
  type: "ollama",
  baseUrl: "http://localhost:11434",
  apiKeyConfigured: false,
  chatModel: "",
  embeddingModel: "",
  visionModel: "",
  embeddingSource: "ollama" as EmbeddingSource,
  providerMode: "local" as ProviderMode,
};

// ── Internal helpers ──────────────────────────────────────────────────────────

function mergeDiffs(base: PatchableSettings, next: PatchableSettings): PatchableSettings {
  return { ...base, ...next };
}

function diffFieldKeys(diff: PatchableSettings): SaveField[] {
  return Object.keys(diff) as SaveField[];
}

function applyDiff(current: AppSettings, diff: PatchableSettings): AppSettings {
  const currentMode = current.provider?.providerMode ?? "local";
  return {
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
      chatModel:
        diff.providerChatModel ??
        (currentMode === "local" && diff.generationModel != null
          ? diff.generationModel
          : undefined) ??
        (current.provider?.chatModel ?? DEFAULT_PROVIDER.chatModel),
      embeddingModel:
        diff.providerEmbeddingModel ??
        (diff.embeddingModel != null ? diff.embeddingModel : undefined) ??
        (current.provider?.embeddingModel ?? DEFAULT_PROVIDER.embeddingModel),
      visionModel:
        diff.providerVisionModel ??
        (diff.visionModel != null ? diff.visionModel : undefined) ??
        (current.provider?.visionModel ?? DEFAULT_PROVIDER.visionModel),
      embeddingSource:
        (diff.embeddingSource ?? current.provider?.embeddingSource) ??
        DEFAULT_PROVIDER.embeddingSource,
      providerMode:
        diff.providerMode ?? current.provider?.providerMode ?? DEFAULT_PROVIDER.providerMode,
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
  };
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export interface UseSettingsReturn {
  s: AppSettings | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  provider: AppSettings["provider"];
  set: <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => void;
  queueSave: (diff: PatchableSettings) => void;
  isSavingField: (field: string) => boolean;
  isSaving: boolean;
  saveErrorText: string | null;
  reindexRequired: boolean;
  retryUnsaved: () => void;
  dismissReindexWarning: () => void;
  onSaveCustomModels: (models: string[]) => Promise<void>;
}

export function useSettings(): UseSettingsReturn {
  const [saveErrorText, setSaveErrorText] = useState<string | null>(null);
  const [savingFields, setSavingFields] = useState<SaveField[]>([]);
  const [reindexRequired, setReindexRequired] = useState(false);
  const qc = useQueryClient();
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());
  const unsavedDiffRef = useRef<PatchableSettings>({});

  const { data: s, isLoading, isError, error } = useQuery({
    queryKey: ["settings"],
    queryFn: getSettings,
    staleTime: 30_000,
    retry: 1,
  });

  const save = useMutation({ mutationFn: patchSettings });

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
        const diffToSave = unsavedDiffRef.current;
        unsavedDiffRef.current = {};
        if (Object.keys(diffToSave).length === 0) return;
        try {
          const nextSettings = await save.mutateAsync(diffToSave);
          qc.setQueryData<AppSettings>(["settings"], nextSettings);
          if ((nextSettings as AppSettings & { reindexRequired?: boolean }).reindexRequired) {
            setReindexRequired(true);
          }
          setSavingFields(diffFieldKeys(unsavedDiffRef.current));
        } catch (err) {
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
    if (key === "generationModel" && value !== s.generationModel)
      diff.generationModel = value as string;
    if (key === "generationFallback" && value !== s.generationFallback)
      diff.generationFallback = value as string;
    if (key === "embeddingModel" && value !== s.embeddingModel)
      diff.embeddingModel = value as string;
    if (key === "visionModel" && value !== s.visionModel)
      diff.visionModel = value as string;
    if (key === "reranker") {
      const r = value as AppSettings["reranker"];
      if (r.enabled !== s.reranker.enabled) diff.rerankerEnabled = r.enabled;
      if (r.model !== s.reranker.model) diff.rerankerModel = r.model;
    }
    if (key === "retrieval") {
      const r = value as AppSettings["retrieval"];
      if (r.k !== s.retrieval.k) diff.retrievalK = r.k;
      if (r.scoreFloor !== s.retrieval.scoreFloor) diff.scoreFloor = r.scoreFloor;
      if (r.chunkSize !== s.retrieval.chunkSize) diff.chunkSize = r.chunkSize;
      if (r.chunkOverlap !== s.retrieval.chunkOverlap) diff.chunkOverlap = r.chunkOverlap;
    }
    if (key === "security") {
      const sec = value as AppSettings["security"];
      if (sec.ssoOnly !== s.security.ssoOnly) diff.ssoOnly = sec.ssoOnly;
      if (sec.sessionHours !== s.security.sessionHours) diff.sessionHours = sec.sessionHours;
      if (sec.auditRetentionDays !== s.security.auditRetentionDays)
        diff.auditRetentionDays = sec.auditRetentionDays;
      if (sec.redactPII !== s.security.redactPII) diff.redactPII = sec.redactPII;
    }
    if (key === "cost") {
      const cost = value as AppSettings["cost"];
      if (cost.dailyCeilingUsd !== s.cost.dailyCeilingUsd)
        diff.dailyCeilingUsd = cost.dailyCeilingUsd;
      if (cost.monthlyCeilingUsd !== s.cost.monthlyCeilingUsd)
        diff.monthlyCeilingUsd = cost.monthlyCeilingUsd;
    }
    if (key === "provider") {
      const p = value as AppSettings["provider"];
      const cur = s.provider ?? DEFAULT_PROVIDER;
      if (p.type !== cur.type) diff.providerType = p.type;
      if (p.baseUrl !== cur.baseUrl) diff.providerBaseUrl = p.baseUrl;
      if (p.chatModel !== cur.chatModel) diff.providerChatModel = p.chatModel;
      if (p.embeddingModel !== cur.embeddingModel) diff.providerEmbeddingModel = p.embeddingModel;
      if (p.visionModel !== cur.visionModel) diff.providerVisionModel = p.visionModel;
      if (p.providerMode !== cur.providerMode) diff.providerMode = p.providerMode;
    }
    if (key === "sseDoneMode" && value !== s.sseDoneMode)
      diff.sseDoneMode = value as AppSettings["sseDoneMode"];
    if (Object.keys(diff).length > 0) queueSave(diff);
  };

  const retryUnsaved = () => {
    setSaveErrorText(null);
    if (Object.keys(unsavedDiffRef.current).length > 0) {
      queueSave(unsavedDiffRef.current);
    }
  };

  const dismissReindexWarning = () => setReindexRequired(false);

  const onSaveCustomModels = async (models: string[]) => {
    const next = await save.mutateAsync({ providerCustomModels: models });
    qc.setQueryData<AppSettings>(["settings"], next);
  };

  return {
    s,
    isLoading,
    isError,
    error: error as Error | null,
    provider: s?.provider ?? DEFAULT_PROVIDER,
    set,
    queueSave,
    isSavingField,
    isSaving: save.isPending,
    saveErrorText,
    reindexRequired,
    retryUnsaved,
    dismissReindexWarning,
    onSaveCustomModels,
  };
}
