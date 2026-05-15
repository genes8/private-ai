import { apiFetch } from "./client";

export interface AppSettings {
  generationModel: string;
  generationFallback: string;
  embeddingModel: string;
  visionModel: string;
  availableModels: {
    ollama: string[];
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
}>;

export const getSettings = () => apiFetch<AppSettings>("/settings");

export const patchSettings = (diff: PatchableSettings) =>
  apiFetch<AppSettings>("/settings", {
    method: "PATCH",
    body: JSON.stringify(diff),
  });
