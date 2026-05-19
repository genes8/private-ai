import { apiFetch } from "./client";

export type ProviderType = "ollama" | "openai_compatible";
export type SseDoneMode = "strict" | "async";

export interface AppSettings {
  generationModel: string;
  generationFallback: string;
  embeddingModel: string;
  visionModel: string;
  provider: {
    type: ProviderType;
    baseUrl: string;
    apiKeyConfigured: boolean;
    chatModel: string;
    embeddingModel: string;
    visionModel: string;
  };
  sseDoneMode: SseDoneMode;
  availableModels: {
    ollama: string[];
    provider: string[];
    reranker: string[];
  };
  reranker: { enabled: boolean; model: string };
  retrieval: {
    k: number;
    scoreFloor: number;
    chunkSize: number;
    chunkOverlap: number;
  };
  sources: Array<{
    id: string;
    kind: "s3" | "gdrive" | "watch";
    label: string;
    detail: string;
    docCount: number;
    syncedAt: string | null;
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

export type PatchableSettings = Partial<{
  generationModel: string;
  generationFallback: string;
  embeddingModel: string;
  visionModel: string;
  rerankerEnabled: boolean;
  rerankerModel: string;
  retrievalK: number;
  scoreFloor: number;
  chunkSize: number;
  chunkOverlap: number;
  ssoOnly: boolean;
  sessionHours: number;
  auditRetentionDays: number;
  redactPII: boolean;
  dailyCeilingUsd: number;
  monthlyCeilingUsd: number;
  // Inference provider
  providerType: ProviderType;
  providerBaseUrl: string;
  providerApiKey: string;
  providerChatModel: string;
  providerEmbeddingModel: string;
  providerVisionModel: string;
  sseDoneMode: SseDoneMode;
}>;

export const getSettings = () => apiFetch<AppSettings>("/settings");

export const patchSettings = (diff: PatchableSettings) =>
  apiFetch<AppSettings>("/settings", {
    method: "PATCH",
    body: JSON.stringify(diff),
  });

export const testProviderConnection = (body: Pick<PatchableSettings, "providerType" | "providerBaseUrl" | "providerApiKey">) =>
  apiFetch<{ status: string }>("/settings/provider/test", {
    method: "POST",
    body: JSON.stringify(body),
  });
