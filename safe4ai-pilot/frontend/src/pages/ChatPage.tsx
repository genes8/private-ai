import { BookOpen, ChevronDown, LogOut, Settings, Shield, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import type { SseCite } from "../api/chat";
import Avatar from "../components/Avatar";
import Logo from "../components/Logo";
import AnswerBlock from "../components/chat/AnswerBlock";
import Composer from "../components/chat/Composer";
import MessageBubble from "../components/chat/MessageBubble";
import SourceRow from "../components/chat/SourceRow";
import StreamingPipeline from "../components/chat/StreamingPipeline";
import SuggestedPrompt from "../components/chat/SuggestedPrompt";
import { useAuth } from "../hooks/useAuth";
import { useChat } from "../hooks/useChat";

const SUGGESTED = [
  { tag: "Policy",    question: "What is the annual leave entitlement?" },
  { tag: "Finance",   question: "Who approves capital expenditure over €50,000?" },
  { tag: "IT",        question: "What is the minimum password length?" },
  { tag: "Compliance",question: "What are our data retention obligations?" },
];

function timeOfDay() {
  const h = new Date().getHours();
  return h < 12 ? "morning" : h < 17 ? "afternoon" : "evening";
}

export default function ChatPage() {
  const { me, isAdmin, signOut } = useAuth();
  const { messages, steps, streaming, sendMessage, rate, stop, ratingError } = useChat();
  const { data: corpusStats } = useQuery({
    queryKey: ["corpus-stats"],
    queryFn: () => apiFetch<{ docCount: number; chunkCount: number }>("/admin/corpus-stats"),
    staleTime: 10_000,
  });
  const [composer, setComposer] = useState("");
  const [activeCitationId, setActiveCitationId] = useState<string | null>(null);
  const [drawerMessageId, setDrawerMessageId] = useState<string | null>(null);
  const [mobileSourcesOpen, setMobileSourcesOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    function handleOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [menuOpen]);

  const totalChunks = corpusStats?.chunkCount ?? 0;
  const totalDocs = corpusStats?.docCount ?? 0;

  const latestAssistantWithSources = messages
    .filter((m) => m.role === "assistant" && m.sources.length > 0)
    .at(-1);
  const selectedDrawerMessage = messages.find(
    (m) => m.id === drawerMessageId && m.role === "assistant" && m.sources.length > 0,
  );
  const drawerSources: SseCite[] = selectedDrawerMessage?.sources ?? latestAssistantWithSources?.sources ?? [];

  async function handleCopy(content: string) {
    try {
      await navigator.clipboard.writeText(content);
    } catch (error) {
      console.error("clipboard_write_failed", error);
    }
  }

  function handleSubmit() {
    const q = composer.trim();
    if (!q || streaming) return;
    setComposer("");
    sendMessage(q).then(() =>
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50)
    );
  }

  const assistantMessages = messages.filter((m) => m.role === "assistant");

  return (
    <div className="flex h-screen bg-paper">
      {/* Main column */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Header */}
        <header className="flex items-center justify-between px-5 py-3 border-b border-line bg-surface">
          <div className="flex items-center gap-3">
            <Logo size={22} />
            <span className="font-medium text-[13.5px] tracking-tight text-ink">private·ai</span>
          </div>
          <div className="flex items-center gap-2">
            {streaming && (
              <span className="inline-flex items-center gap-1.5 h-[22px] px-2 rounded-full bg-surface border border-line text-[11.5px] text-text-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#3b6cf2] animate-pulse shrink-0" />
                Generating…
              </span>
            )}

            {/* Avatar menu */}
            <div className="relative" ref={menuRef}>
              <button
                type="button"
                onClick={() => setMenuOpen((o) => !o)}
                className="flex items-center gap-1 rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                aria-haspopup="true"
                aria-expanded={menuOpen}
              >
                <Avatar name={me?.email ?? "U"} size={26} />
                <ChevronDown
                  size={12}
                  className={`text-text-mute transition-transform duration-150 ${menuOpen ? "rotate-180" : ""}`}
                />
              </button>

              {menuOpen && (
                <div className="absolute right-0 top-9 z-50 w-48 rounded-lg border border-line bg-surface shadow-lg py-1 animate-in fade-in slide-in-from-top-1 duration-100">
                  {/* Email label */}
                  <div className="px-3 py-2 border-b border-line">
                    <p className="text-[11px] font-mono text-text-mute truncate">{me?.email}</p>
                  </div>

                  <Link
                    to="/settings"
                    onClick={() => setMenuOpen(false)}
                    className="flex items-center gap-2.5 px-3 py-2 text-[12.5px] text-text-2 hover:bg-surface-2 transition-colors"
                  >
                    <Settings size={13} className="text-text-3 shrink-0" />
                    Settings
                  </Link>

                  {isAdmin && (
                    <Link
                      to="/admin"
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center gap-2.5 px-3 py-2 text-[12.5px] text-text-2 hover:bg-surface-2 transition-colors"
                    >
                      <Shield size={13} className="text-text-3 shrink-0" />
                      Admin panel
                    </Link>
                  )}

                  <div className="border-t border-line my-1" />

                  <button
                    type="button"
                    onClick={() => { signOut(); setMenuOpen(false); }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 text-[12.5px] text-text-2 hover:bg-surface-2 transition-colors"
                  >
                    <LogOut size={13} className="text-text-3 shrink-0" />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-2xl px-4 py-8 space-y-6">
            {messages.length === 0 && (
              <div className="flex flex-col gap-8 pt-16">
                <div>
                  <p className="font-mono text-[10.5px] uppercase text-text-mute mb-3" style={{ letterSpacing: "0.08em" }}>
                    good {timeOfDay()}, {me?.email?.split("@")[0] ?? "there"}
                  </p>
                  <h2 className="font-serif text-[38px] italic leading-tight tracking-tight text-ink">
                    What should we look up today?
                  </h2>
                  <p className="mt-3 text-[13px] text-text-3 leading-relaxed">
                    Drawing from{" "}
                    <b className="text-text-2">{totalChunks.toLocaleString()}</b> chunks across{" "}
                    <b className="text-text-2">{totalDocs}</b> document{totalDocs !== 1 ? "s" : ""}.{" "}
                    All answers grounded in your uploaded documents.
                  </p>
                </div>
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.06em] text-text-mute mb-2">
                    Example questions — edit before sending
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    {SUGGESTED.map((s) => (
                      <SuggestedPrompt
                        key={s.question}
                        tag={s.tag}
                        icon={<BookOpen size={12} />}
                        question={s.question}
                        onSelect={() => {
                          setComposer(s.question);
                          setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
                        }}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <MessageBubble key={msg.id} role={msg.role}>
                {msg.role === "user" ? (
                  <span>{msg.content}</span>
                ) : (
                  <AnswerBlock
                    body={msg.content}
                    sources={msg.sources}
                    trust={
                      msg.trust ?? { latencyMs: 0, cacheHit: false, model: "—", kRetrieved: 0 }
                    }
                    isStreaming={
                      streaming && msg.id === assistantMessages.at(-1)?.id
                    }
                    rated={msg.rated}
                    onCopy={() => void handleCopy(msg.content)}
                    onRate={(r) => rate(msg.id, r)}
                    onCitationOpen={(id) => {
                      setDrawerMessageId(msg.id);
                      setActiveCitationId((prev) => (prev === id ? null : id));
                      setMobileSourcesOpen(true);
                    }}
                  />
                )}
              </MessageBubble>
            ))}

            {streaming && steps.length > 0 && (
              <div className="flex justify-start">
                <div className="rounded-xl border border-line bg-surface px-4 py-3 shadow-sm">
                  <StreamingPipeline steps={steps} />
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </div>

        {/* Composer */}
        <div className="border-t border-line bg-surface px-4 py-4">
            {streaming && (
              <div className="text-center mb-2">
                <button
                  type="button"
                  onClick={stop}
                  aria-label="Stop generating"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-line bg-surface text-[12px] text-text-2 hover:bg-surface-2 transition-colors"
                >
                  <Square size={10} className="fill-current" />
                  Stop generating
                </button>
            </div>
          )}
          {ratingError && (
            <div className="mx-auto mb-2 max-w-2xl px-3 py-2 rounded-md bg-red-50 border border-red-200 text-[12px] text-red-700">
              {ratingError}
            </div>
          )}
          <div className="mx-auto max-w-2xl">
            <Composer
              value={composer}
              onChange={setComposer}
              onSubmit={handleSubmit}
              disabled={streaming}
            />
          </div>
          {drawerSources.length > 0 && (
            <div className="mx-auto mt-3 max-w-2xl md:hidden">
              <button
                type="button"
                onClick={() => setMobileSourcesOpen((prev) => !prev)}
                className="flex w-full items-center justify-between rounded-lg border border-line bg-surface-2 px-3 py-2 text-left text-[12px] font-medium text-text-2"
              >
                <span>Sources</span>
                <span className="font-mono text-[11px] text-text-3">
                  {mobileSourcesOpen ? "Hide" : `Show ${drawerSources.length}`}
                </span>
              </button>
              {mobileSourcesOpen && (
                <div className="mt-2 overflow-hidden rounded-lg border border-line bg-surface-2">
                  {drawerSources.map((source) => (
                    <SourceRow key={source.id} source={source} active={activeCitationId === source.id} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Citation drawer — right side, auto-visible from last assistant message */}
      {drawerSources.length > 0 && (
        <aside className="hidden md:flex md:w-[320px] lg:w-[360px] shrink-0 border-l border-line bg-surface-2 flex-col">
          <div className="px-4 py-3 border-b border-line">
            <span className="text-[12px] font-semibold text-text-2">Sources</span>
          </div>
          <div className="flex-1 overflow-y-auto py-1">
            {drawerSources.map((s) => (
              <SourceRow key={s.id} source={s} active={activeCitationId === s.id} />
            ))}
          </div>
        </aside>
      )}
    </div>
  );
}
