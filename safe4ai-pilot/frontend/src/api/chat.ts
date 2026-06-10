import { apiFetch, apiUrl, csrfHeaders } from "./client";
import { emitUnauthorized } from "./authEvents";

export type StepName = "embed" | "retrieve" | "rerank" | "generate";
export type StepState = "pending" | "active" | "done";

export interface SseStep   { name: StepName; state: StepState; t: number; meta?: Record<string, unknown> }
export interface SseToken  { delta: string }
export interface SseCite   { id: string; file: string; page: number; score: number; excerpt?: string }
export interface SseDone   {
  traceId: string; latencyMs: number; cache: boolean;
  model: string; kRetrieved: number; sessionId: string; error?: string;
}

export type SseEvent =
  | { type: "step";  data: SseStep  }
  | { type: "token"; data: SseToken }
  | { type: "cite";  data: SseCite  }
  | { type: "done";  data: SseDone  }
  | { type: "error"; data: { message: string } };

async function* readStreamChunks(reader: ReadableStreamDefaultReader<Uint8Array>): AsyncGenerator<Uint8Array> {
  while (true) {
    let result: ReadableStreamReadResult<Uint8Array>;
    try {
      result = await reader.read();
    } catch (err) {
      throw err instanceof Error ? err : new Error("Stream read failed");
    }
    if (result.done) return;
    yield result.value;
  }
}

export async function* streamChat(
  question: string,
  sessionId: string | null,
  collection = "default",
  signal?: AbortSignal,
): AsyncGenerator<SseEvent> {
  const res = await fetch(apiUrl("/chat/stream"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify({ question, session_id: sessionId, collection }),
    signal,
  });

  if (!res.ok) {
    const msg = await res.text().catch(() => String(res.status));
    if (res.status === 401) {
      emitUnauthorized();
    }
    yield { type: "error", data: { message: msg } };
    return;
  }

  if (!res.body) {
    yield { type: "error", data: { message: "Streaming response body was empty" } };
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let eventName = "";
  let dataLines: string[] = [];

  function emitEvent(): SseEvent | null {
    if (dataLines.length === 0) return null;
    const raw = dataLines.join("\n");
    dataLines = [];
    const name = eventName || "message";
    eventName = "";
    try {
      const data = JSON.parse(raw) as unknown;
      if (name === "step") return { type: "step", data: data as SseStep };
      if (name === "token") return { type: "token", data: data as SseToken };
      if (name === "cite") return { type: "cite", data: data as SseCite };
      if (name === "done") return { type: "done", data: data as SseDone };
    } catch (err) {
      console.warn("[sse] failed to parse event data", name, raw, err);
    }
    return { type: "error", data: { message: `Unexpected SSE event: ${name}` } };
  }

  try {
    for await (const value of readStreamChunks(reader)) {
      buf += decoder.decode(value, { stream: true });

      const lines = buf.split(/\r?\n/);
      buf = lines.pop() ?? "";

      for (const line of lines) {
        if (line === "") {
          const ev = emitEvent();
          if (ev) yield ev;
          continue;
        }
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
          continue;
        }
        if (line.startsWith("data:")) {
          dataLines.push(line.startsWith("data: ") ? line.slice(6) : line.slice(5));
        }
      }
    }
  } catch (err) {
    if (signal?.aborted) return;
    yield {
      type: "error",
      data: { message: err instanceof Error ? err.message : "Streaming connection interrupted" },
    };
  }
}

// ---------------------------------------------------------------------------
// Session history
// ---------------------------------------------------------------------------

export interface ChatSessionSummary {
  sessionId: string;
  title: string;
  updatedAt: string | null;
  messageCount: number;
}

export interface ChatSessionMessage {
  role: "user" | "assistant";
  content: string;
}

interface RawSessionSummary {
  session_id: string;
  title: string;
  updated_at: string | null;
  message_count: number;
}

export const listChatSessions = () =>
  apiFetch<RawSessionSummary[]>("/chat/sessions").then((rows) =>
    rows.map(
      (r): ChatSessionSummary => ({
        sessionId: r.session_id,
        title: r.title,
        updatedAt: r.updated_at,
        messageCount: r.message_count,
      }),
    ),
  );

export const getChatSessionMessages = (sessionId: string) =>
  apiFetch<{ session_id: string; messages: ChatSessionMessage[] }>(
    `/chat/sessions/${encodeURIComponent(sessionId)}/messages`,
  );
