import { apiFetch } from "./client";

export interface FeedbackItem {
  id: string;
  traceId: string;
  userId: string;
  sessionId: string;
  ts: string;
  rating: "up" | "down";
  note?: string;
}

export const submitFeedback = (
  session_id: string,
  trace_id: string,
  rating: "positive" | "negative",
  comment?: string,
) => apiFetch<void>("/feedback", { method: "POST", body: JSON.stringify({ session_id, trace_id, rating, comment }) });

interface RawFeedback {
  id: string;
  user_id: string;
  session_id: string;
  trace_id: string;
  rating: string;
  comment: string | null;
  created_at: string;
}

export const listFeedback = () =>
  apiFetch<RawFeedback[]>("/admin/feedback").then((rows) =>
    rows.map(
      (r): FeedbackItem => ({
        id: r.id,
        traceId: r.trace_id,
        userId: r.user_id,
        sessionId: r.session_id,
        ts: r.created_at,
        rating: r.rating === "positive" ? "up" : "down",
        note: r.comment ?? undefined,
      }),
    ),
  );
