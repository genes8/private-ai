import { useCallback, useEffect, useRef, useState } from "react";
import { getChatSessionMessages, type SseCite, type StepName, type StepState, streamChat } from "../api/chat";
import { submitFeedback } from "../api/feedback";
import { readStoredChatSessionId, storeChatSessionId } from "../utils/chatSessionStorage";

interface Step { name: StepName; state: StepState }
const DEFAULT_COLLECTION = import.meta.env.VITE_DEFAULT_COLLECTION ?? "default";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: SseCite[];
  trust: { latencyMs: number; cacheHit: boolean; model: string; kRetrieved: number } | null;
  traceId: string | null;
  rated?: "up" | "down";
}

export function useChat(userId?: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [steps, setSteps] = useState<Step[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [ratingError, setRatingError] = useState<string | null>(null);
  const sessionRef = useRef<string | null>(readStoredChatSessionId(userId));
  // Mirror of sessionRef for rendering (sidebar highlight); the ref stays the
  // source of truth for stream calls because it updates mid-stream.
  const [activeSessionId, setActiveSessionId] = useState<string | null>(sessionRef.current);
  const abortRef = useRef<AbortController | null>(null);
  const messagesRef = useRef<ChatMessage[]>([]);
  messagesRef.current = messages;
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    sessionRef.current = readStoredChatSessionId(userId);
    setActiveSessionId(sessionRef.current);
  }, [userId]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const newChat = useCallback(() => {
    abortRef.current?.abort();
    sessionRef.current = null;
    setActiveSessionId(null);
    setMessages([]);
    setSteps([]);
    setStreaming(false);
  }, []);

  const loadSession = useCallback(async (sessionId: string) => {
    abortRef.current?.abort();
    const { messages: history } = await getChatSessionMessages(sessionId);
    if (!mountedRef.current) return;
    sessionRef.current = sessionId;
    setActiveSessionId(sessionId);
    storeChatSessionId(userId, sessionId);
    // Restored messages have no per-message citation/trust data — the state
    // only persists role + content. Sources reappear on the next live answer.
    setMessages(
      history.map((m) => ({
        id: crypto.randomUUID(),
        role: m.role,
        content: m.content,
        sources: [],
        trust: null,
        traceId: null,
      })),
    );
    setSteps([]);
    setStreaming(false);
  }, [userId]);

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
    let streamCompleted = false;
    let streamErrored = false;

    const abort = new AbortController();
    abortRef.current = abort;

    try {
      for await (const ev of streamChat(question, sessionRef.current, DEFAULT_COLLECTION, abort.signal)) {
        if (!mountedRef.current) break;
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
          setActiveSessionId(ev.data.sessionId);
          storeChatSessionId(userId, ev.data.sessionId);
          streamCompleted = !ev.data.error;
          const trust = { latencyMs: ev.data.latencyMs, cacheHit: ev.data.cache, model: ev.data.model, kRetrieved: ev.data.kRetrieved };
          setMessages((prev) =>
            prev.map((m) => m.id === assistantId ? { ...m, trust, traceId } : m),
          );
        } else if (ev.type === "error") {
          streamErrored = true;
          setMessages((prev) =>
            prev.map((m) => m.id === assistantId ? { ...m, content: `Error: ${ev.data.message}` } : m),
          );
        }
      }
    } finally {
      if (mountedRef.current) {
        if (!streamCompleted && !streamErrored && !abort.signal.aborted) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: `${m.content}${m.content ? "\n\n" : ""}Response interrupted before completion. Please retry.`,
                  }
                : m,
            ),
          );
        }
        setStreaming(false);
        setSteps([]);
      }
    }
  }, [userId]);

  const rate = useCallback(async (msgId: string, rating: "up" | "down") => {
    const msg = messagesRef.current.find((m) => m.id === msgId);
    if (!msg?.traceId || !sessionRef.current) {
      setRatingError("Feedback unavailable — session context lost. Please reload the page.");
      return;
    }
    setRatingError(null);
    const previousRating = msg.rated;
    setMessages((prev) =>
      prev.map((m) => m.id === msgId ? { ...m, rated: rating } : m),
    );
    try {
      await submitFeedback(sessionRef.current, msg.traceId, rating === "up" ? "positive" : "negative");
    } catch (error) {
      console.error("submitFeedback_failed", error);
      setRatingError("Failed to submit feedback. Please try again.");
      setMessages((prev) =>
        prev.map((m) => m.id === msgId ? { ...m, rated: previousRating } : m),
      );
    }
  }, []);

  return {
    messages,
    steps,
    streaming,
    sendMessage,
    rate,
    stop,
    ratingError,
    newChat,
    loadSession,
    activeSessionId,
  };
}
