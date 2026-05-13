import { apiFetch } from "./client";

export interface StatsToday {
  generatedAt: string;
  days: number;
  queries:       { total: number };
  cost:          { totalUsd: number };
  latency:       { avgMs: number | null };
  cacheTotalHits: number;
  uniqueUsers: number;
}

interface RawStats {
  generated_at: string;
  days: number;
  total_queries: number;
  total_cost_usd: number;
  avg_latency_ms: number | null;
  cache_total_hits: number;
  unique_users: number;
}

export const getStats = () =>
  apiFetch<RawStats>("/admin/stats").then(
    (r): StatsToday => ({
      generatedAt: r.generated_at,
      days: r.days,
      queries:        { total: r.total_queries },
      cost:           { totalUsd: r.total_cost_usd },
      latency:        { avgMs: r.avg_latency_ms },
      cacheTotalHits: r.cache_total_hits,
      uniqueUsers:    r.unique_users,
    }),
  );
