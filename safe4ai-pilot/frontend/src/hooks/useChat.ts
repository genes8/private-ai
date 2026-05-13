import { useCallback, useRef, useState } from "react";
import { type SseCite, type StepName, type StepState, streamChat } from "../api/chat";
import { submitFeedback } from "../api/feedback";

interface Step { name: StepName; state: StepState }

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: SseCite[];
  trust: { latencyMs: number; cacheHit: boolean; model: string; kRetrieved: number } | null;
  traceId: string | null;
  rated?: "up" | "down";
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [steps, setSteps] = useState<Step[]>([]);
  const [streaming, setStreaming] = useState(false);
  const sessionRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const messagesRef = useRef<ChatMessage[]>([]);
  messagesRef.current = messages;

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const sendMessage = useCallback(async (question: string) => {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
      sources: [],
      trust: null,
      traceId: null,
    };
    setMessages((prev) => [...prev, userMsg]);

    const ALL_STEPS: StepName[] = ["embed", "retrieve", "rerank", "generate"];
    const pending: Step[] = ALL_STEPS.map((name) => ({ name, state: "pending" as StepState }));
    setSteps(pending);
    setStreaming(true);

    const assistantId = crypto.randomUUID();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      sources: [],
      trust: null,
      traceId: null,
    };
    setMessages((prev) => [...prev, assistantMsg]);

    let traceId: string | null = null;

    const abort = new AbortController();
    abortRef.current = abort;

    try {
      for await (const ev of streamChat(question, sessionRef.current, "default", abort.signal)) {
        if (ev.type === "step") {
          setSteps((prev) =>
            prev.map((s) => s.name === ev.data.name ? { ...s, state: ev.data.state } : s),
          );
        } else if (ev.type === "token") {
          setMessages((prev) =>
            prev.map((m) => m.id === assistantId ? { ...m, content: m.content + ev.data.delta } : m),
          );
        } else if (ev.type === "cite") {
          setMessages((prev) =>
            prev.map((m) => m.id === assistantId ? { ...m, sources: [...m.sources, ev.data] } : m),
          );
        } else if (ev.type === "done") {
          traceId = ev.data.traceId;
          sessionRef.current = ev.data.sessionId;
          const trust = { latencyMs: ev.data.latencyMs, cacheHit: ev.data.cache, model: ev.data.model, kRetrieved: ev.data.kRetrieved };
          setMessages((prev) =>
            prev.map((m) => m.id === assistantId ? { ...m, trust, traceId } : m),
          );
        } else if (ev.type === "error") {
          setMessages((prev) =>
            prev.map((m) => m.id === assistantId ? { ...m, content: `Error: ${ev.data.message}` } : m),
          );
        }
      }
    } finally {
      setStreaming(false);
      setSteps([]);
    }
  }, []);

  const rate = useCallback(async (msgId: string, rating: "up" | "down") => {
    const msg = messagesRef.current.find((m) => m.id === msgId);
    if (!msg?.traceId || !sessionRef.current) return;
    const previousRating = msg.rated;
    setMessages((prev) =>
      prev.map((m) => m.id === msgId ? { ...m, rated: rating } : m),
    );
    try {
      await submitFeedback(sessionRef.current, msg.traceId, rating === "up" ? "positive" : "negative");
    } catch (error) {
      console.error("submitFeedback_failed", error);
      setMessages((prev) =>
        prev.map((m) => m.id === msgId ? { ...m, rated: previousRating } : m),
      );
    }
  }, []);

  return { messages, steps, streaming, sendMessage, rate, stop };
}
