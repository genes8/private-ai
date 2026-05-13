import React from "react";
import { Icon } from "./Icons";
import { SAMPLE_QUESTION, SAMPLE_ANSWER_BODY, UserBubble } from "./ChatShared";

export function ChatEmpty() {
  return (
    <div className="pa-root" style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--paper)" }}>
      <header style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "14px 20px", borderBottom: "1px solid var(--line)",
      }}>
        <div className="pa-logo">
          <div className="mark"/>
          <span className="word">private<span className="dim">·ai</span></span>
          <span className="kicker" style={{ marginLeft: 12, color: "var(--text-3)" }}>· legal · new thread</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="kbd">⌘K</span>
          <span className="avatar">AB</span>
        </div>
      </header>

      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 20px" }}>
        <div style={{ maxWidth: 720, margin: "0 auto", width: "100%" }}>
          <div style={{ marginBottom: 36 }}>
            <div className="kicker" style={{ marginBottom: 10 }}>good afternoon, alex</div>
            <h1 style={{
              font: "400 38px/1.1 var(--font-serif)",
              fontStyle: "italic",
              color: "var(--ink)",
              margin: "0 0 10px",
              letterSpacing: "-0.015em",
            }}>
              What should we look up <span style={{ color: "var(--blue)" }}>today</span>?
            </h1>
            <p style={{
              font: "400 13.5px/1.5 var(--font-sans)",
              color: "var(--text-2)",
              margin: 0, maxWidth: 480,
            }}>
              Drawing from <b>14,827</b> chunks across <b>312 documents</b> in the
              Legal scope. Last index: <span className="mono">2 min ago</span>.
            </p>
          </div>

          {/* Composer */}
          <div className="card" style={{ padding: 4, boxShadow: "var(--sh-2)", borderRadius: 12, marginBottom: 28 }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 8, padding: "12px 14px" }}>
              <span style={{ flex: 1, font: "400 14px/1.5 var(--font-sans)", color: "var(--text-mute)" }}>
                Ask about your indexed documents…
              </span>
              <button className="btn primary" style={{ width: 32, height: 32, padding: 0, borderRadius: 8 }}>
                <Icon.Send size={14} stroke="#f4f1ea"/>
              </button>
            </div>
            <div style={{
              display: "flex", alignItems: "center", gap: 4,
              padding: "8px 8px", borderTop: "1px solid var(--line)",
            }}>
              <button className="btn ghost sm" style={{ padding: "0 8px" }}>
                <Icon.Folder size={12} stroke="var(--text-3)"/>
                <span>Legal scope</span>
                <Icon.ChevD size={10} stroke="var(--text-3)" style={{ marginLeft: 2 }}/>
              </button>
              <button className="btn ghost sm" style={{ padding: "0 8px" }}>
                <Icon.Paper size={12} stroke="var(--text-3)"/>
                Attach
              </button>
              <span style={{ flex: 1 }}/>
              <span style={{ font: "400 11px/1 var(--font-mono)", color: "var(--text-3)" }}>
                claude-haiku-4-5 · 4k retrieval
              </span>
            </div>
          </div>

          {/* Suggested prompts — pulled from corpus */}
          <div>
            <div className="kicker" style={{ marginBottom: 12 }}>suggested · pulled from your recent docs</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              {[
                { tag: "freshly indexed", icon: "Doc",
                  q: "Summarize the changes between MSA v3 and v4 for Riley Aerospace.",
                  src: "MSA_Vendor_Riley_Aerospace_2024.pdf · added 2 min ago" },
                { tag: "open question", icon: "Activity",
                  q: "Which of our vendors have a liability cap below the procurement floor?",
                  src: "across 47 active MSAs" },
                { tag: "from feedback", icon: "Spark",
                  q: "Draft a redline pushing Lattice's IP carve-out to match Northwind.",
                  src: "thumbs-up answer · last Friday" },
                { tag: "recently asked", icon: "Clock",
                  q: "What's our exposure if a Tier-2 vendor breaches confidentiality?",
                  src: "team asked 4× this week" },
              ].map((s, idx) => {
                const Ic = Icon[s.icon];
                return (
                  <div key={idx} className="card" style={{
                    padding: 14, cursor: "default",
                    transition: "border-color .12s, transform .12s",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
                      <Ic size={11} stroke="var(--text-3)"/>
                      <span style={{
                        font: "500 9.5px/1 var(--font-mono)",
                        letterSpacing: ".06em", textTransform: "uppercase",
                        color: "var(--text-3)",
                      }}>{s.tag}</span>
                    </div>
                    <div style={{
                      font: "400 13.5px/1.45 var(--font-sans)",
                      color: "var(--text)",
                      marginBottom: 10,
                      letterSpacing: "-0.005em",
                    }}>{s.q}</div>
                    <div style={{
                      font: "400 11px/1.3 var(--font-mono)",
                      color: "var(--text-3)",
                      borderTop: "1px solid var(--line)",
                      paddingTop: 8,
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>{s.src}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function ChatStreaming() {
  return (
    <div className="pa-root" style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--paper)" }}>
      <header style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "14px 20px", borderBottom: "1px solid var(--line)",
      }}>
        <div className="pa-logo">
          <div className="mark"/>
          <span className="word">private<span className="dim">·ai</span></span>
          <span className="kicker" style={{ marginLeft: 12, color: "var(--text-3)" }}>· generating answer</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="chip blue"><span className="dot"/>retrieving</span>
          <span className="avatar">AB</span>
        </div>
      </header>

      <div className="scroll" style={{ flex: 1, overflowY: "auto", padding: "28px 20px 20px" }}>
        <div style={{ maxWidth: 720, margin: "0 auto" }}>
          <UserBubble>{SAMPLE_QUESTION}</UserBubble>

          {/* Retrieval pipeline display */}
          <div style={{
            display: "grid", gridTemplateColumns: "28px 1fr", gap: 12,
            marginBottom: 16,
          }}>
            <div style={{ width: 28, height: 28, borderRadius: 7, background: "var(--ink)", position: "relative", marginTop: 2 }}>
              <span style={{
                position: "absolute", inset: 6, borderRadius: 1,
                background: "linear-gradient(135deg, #f4f1ea 0 50%, transparent 50%)",
              }}/>
              <span style={{
                position: "absolute", width: 5, height: 5, top: 6, right: 6,
                background: "var(--blue)", borderRadius: 1,
                animation: "pa-caret 1s steps(1) infinite",
              }}/>
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <span style={{ font: "500 13px/1 var(--font-sans)", color: "var(--ink)" }}>private·ai</span>
                <span className="trust">
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                    <span className="sdot" style={{ background: "var(--blue)", animation: "pa-caret 1s steps(1) infinite" }}/>
                    streaming · <b>0.8s</b>
                  </span>
                </span>
              </div>

              {/* pipeline steps */}
              <div style={{ marginBottom: 14, paddingLeft: 0 }}>
                {[
                  { label: "Embed query",    val: "1536-d · 18ms", done: true },
                  { label: "Retrieve chunks", val: "k=4 · score≥0.78 · 47ms", done: true },
                  { label: "Rerank",          val: "bge-reranker-v2 · 142ms", done: true },
                  { label: "Generate",        val: "claude-haiku-4-5", done: false },
                ].map((s, idx) => (
                  <div key={idx} style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "4px 0",
                    font: "400 11.5px/1 var(--font-mono)",
                    color: s.done ? "var(--text-3)" : "var(--text)",
                  }}>
                    {s.done
                      ? <Icon.Check size={12} stroke="var(--green)"/>
                      : <span className="sdot" style={{ background: "var(--blue)", animation: "pa-caret 1s steps(1) infinite" }}/>
                    }
                    <span style={{ minWidth: 110, color: s.done ? "var(--text-3)" : "var(--ink)", fontWeight: s.done ? 400 : 500 }}>{s.label}</span>
                    <span style={{ color: "var(--text-3)" }}>{s.val}</span>
                  </div>
                ))}
              </div>

              {/* streaming answer */}
              <div style={{
                font: "400 14.5px/1.65 var(--font-sans)",
                color: "var(--text)",
              }}>
                <p>
                  Under the current draft, <b>Riley Aerospace's aggregate liability is capped at 1× the fees paid in
                  the trailing twelve months</b><span className="cite-chip">2</span> — meaningfully below the
                  company's procurement minimum of 2× annual fees for Tier-2 vendors<span className="cite-chip">3</span>.
                </p>
                <p>
                  The cap excludes the standard carve-outs for indemnification of IP infringement and unauthorized
                  disclosure of Confidential Information<span className="cite-chip">1</span>, so those exposures
                  remain uncapped.
                </p>
                <p>
                  During the prior cycle Riley accepted<span className="caret"/>
                </p>
              </div>

              <button className="btn sm" style={{ marginTop: 14, fontWeight: 400 }}>
                <Icon.X size={11} stroke="var(--text-2)"/>
                Stop generating
              </button>
            </div>
          </div>
        </div>
      </div>

      <div style={{ padding: "12px 20px 20px" }}>
        <div style={{ maxWidth: 720, margin: "0 auto", opacity: .55 }}>
          <div className="card" style={{ padding: "12px 14px", display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ flex: 1, font: "400 14px/1.5 var(--font-sans)", color: "var(--text-mute)" }}>
              Wait for current answer to finish…
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function ChatCiteHover() {
  return (
    <div className="pa-root" style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--paper)" }}>
      <header style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "14px 20px", borderBottom: "1px solid var(--line)",
      }}>
        <div className="pa-logo">
          <div className="mark"/>
          <span className="word">private<span className="dim">·ai</span></span>
          <span className="kicker" style={{ marginLeft: 12, color: "var(--text-3)" }}>· hovering citation [2]</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="avatar">AB</span>
        </div>
      </header>

      <div style={{ flex: 1, padding: "28px 20px", overflow: "hidden", position: "relative" }}>
        <div style={{ maxWidth: 720, margin: "0 auto", position: "relative" }}>
          <UserBubble>{SAMPLE_QUESTION}</UserBubble>

          <div style={{ display: "grid", gridTemplateColumns: "28px 1fr", gap: 12 }}>
            <div style={{ width: 28, height: 28, borderRadius: 7, background: "var(--ink)", position: "relative", marginTop: 2 }}>
              <span style={{
                position: "absolute", inset: 6, borderRadius: 1,
                background: "linear-gradient(135deg, #f4f1ea 0 50%, transparent 50%)",
              }}/>
              <span style={{
                position: "absolute", width: 5, height: 5, top: 6, right: 6,
                background: "var(--blue)", borderRadius: 1,
              }}/>
            </div>
            <div style={{ position: "relative" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <span style={{ font: "500 13px/1 var(--font-sans)", color: "var(--ink)" }}>private·ai</span>
                <span className="trust"><b>284ms</b> · fresh · <b>4</b> retrievals · claude-haiku-4-5</span>
              </div>

              <div style={{
                font: "400 14.5px/1.65 var(--font-sans)",
                color: "var(--text)",
              }}>
                <p>
                  Under the current draft, <b>Riley Aerospace's aggregate liability is capped at 1× the fees paid in the
                  trailing twelve months</b>
                  <span className="cite-chip" style={{
                    background: "#3b6cf2", color: "#fff",
                    boxShadow: "0 0 0 3px rgba(59,108,242,.18)",
                    borderColor: "transparent",
                  }}>2</span>
                  {" "}— meaningfully below the company's procurement minimum of 2× annual fees for Tier-2 vendors
                  <span className="cite-chip">3</span>.
                </p>
                <p>
                  The cap excludes the standard carve-outs for indemnification of IP infringement and unauthorized
                  disclosure of Confidential Information<span className="cite-chip">1</span>, so those exposures
                  remain uncapped.
                </p>
              </div>

              {/* HOVER PREVIEW POPOVER */}
              <div className="cite-pop" style={{
                left: 240,
                top: 82,
                width: 360,
              }}>
                {/* arrow */}
                <span aria-hidden style={{
                  position: "absolute", top: -7, left: 30,
                  width: 12, height: 12, transform: "rotate(45deg)",
                  background: "var(--surface)",
                  borderTop: "1px solid var(--line-2)",
                  borderLeft: "1px solid var(--line-2)",
                }}/>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                  <span className="cite-chip">2</span>
                  <Icon.DocText size={12} stroke="var(--text-3)"/>
                  <span style={{
                    font: "500 12px/1 var(--font-sans)", color: "var(--ink)", flex: 1,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>MSA_Vendor_Riley_Aerospace_2024.pdf</span>
                  <span className="mono" style={{ font: "400 10.5px/1 var(--font-mono)", color: "var(--text-3)" }}>p.11</span>
                </div>

                {/* Mini PDF page peek */}
                <div style={{
                  border: "1px solid var(--line)",
                  borderRadius: 6,
                  padding: 10,
                  background: "#fff",
                  marginBottom: 10,
                }}>
                  <div style={{ font: "500 9px/1 var(--font-mono)", color: "var(--text-3)", letterSpacing: ".05em", marginBottom: 8 }}>
                    § 9.1  LIMITATION OF LIABILITY
                  </div>
                  {[100, 92, 86].map((w, i) => (
                    <div key={i} style={{
                      height: 4, background: "var(--paper-3)", borderRadius: 2,
                      width: w + "%", marginBottom: 5,
                    }}/>
                  ))}
                  <div style={{
                    background: "rgba(59,108,242,.10)",
                    padding: "6px 8px",
                    font: "400 10.5px/1.45 var(--font-sans)",
                    color: "var(--text)",
                    borderRadius: 3,
                    marginTop: 6,
                  }}>
                    "…each party's aggregate liability under this Agreement <b>shall not exceed the fees paid by Customer
                    to Vendor in the twelve (12) months</b> preceding the claim…"
                  </div>
                  {[80, 90].map((w, i) => (
                    <div key={i} style={{
                      height: 4, background: "var(--paper-3)", borderRadius: 2,
                      width: w + "%", marginTop: 6,
                    }}/>
                  ))}
                </div>

                <div style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  font: "400 10.5px/1 var(--font-mono)", color: "var(--text-3)",
                }}>
                  <span>retrieval score · <b style={{ color: "var(--green)" }}>0.91</b></span>
                  <span style={{ display: "flex", gap: 10 }}>
                    <span>⏎ open</span>
                    <span>⌘C cite</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
