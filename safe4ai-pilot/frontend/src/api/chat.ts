import { apiUrl, csrfHeaders } from "./client";
import { emitUnauthorized } from "./authEvents";

export type StepName = "embed" | "retrieve" | "rerank" | "generate";
export type StepState = "pending" | "active" | "done";

export interface SseStep   { name: StepName; state: StepState; t: number; meta?: Record<string, unknown> }
export interface SseToken  { delta: string }
export interface SseCite   { id: string; file: string; page: number; score: number }
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

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let eventName = "";
  let dataLines: string[] = [];

  function emitEvent(): SseEvent | null {
    if (!eventName || dataLines.length === 0) return null;
    const raw = dataLines.join("\n");
    dataLines = [];
    const name = eventName;
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
    return null;
  }

  while (true) {
    let done: boolean, value: Uint8Array | undefined;
    try {
      ({ done, value } = await reader.read());
    } catch {
      break;
    }
    if (done) break;
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
        dataLines.push(line.slice(5).trimStart());
      }
    }
  }
}
