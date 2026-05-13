import React from "react";
import { Icon } from "./Icons";
import { SAMPLE_SOURCES, SAMPLE_ANSWER_BODY, SAMPLE_QUESTION, SourceRow, TrustSignal, UserBubble } from "./ChatShared";

export function ChatA() {
  return (
    <div className="pa-root" style={{ display: "grid", gridTemplateColumns: "1fr 360px", height: "100%", background: "var(--paper)" }}>
      {/* MAIN COLUMN */}
      <div style={{ display: "flex", flexDirection: "column", height: "100%", minWidth: 0 }}>
        {/* Top bar */}
        <header style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "14px 20px", borderBottom: "1px solid var(--line)",
        }}>
          <div className="pa-logo">
            <div className="mark"/>
            <span className="word">private<span className="dim">·ai</span></span>
            <span className="kicker" style={{ marginLeft: 12, color: "var(--text-3)" }}>· legal · q2 review</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="kbd">⌘K</span>
            <button className="btn sm">
              <Icon.Plus size={12} stroke="var(--text-2)"/>
              New chat
            </button>
            <span style={{ width: 1, height: 20, background: "var(--line)", margin: "0 4px" }}/>
            <span className="avatar">AB</span>
          </div>
        </header>

        {/* Conversation */}
        <div className="scroll" style={{ flex: 1, overflowY: "auto", padding: "28px 20px 20px" }}>
          <div style={{ maxWidth: 720, margin: "0 auto" }}>

            <div style={{ textAlign: "center", marginBottom: 28, font: "400 11.5px/1 var(--font-mono)", color: "var(--text-3)" }}>
              Today · 14:32
            </div>

            <UserBubble>{SAMPLE_QUESTION}</UserBubble>

            {/* Assistant answer */}
            <div style={{ display: "grid", gridTemplateColumns: "28px 1fr", gap: 12, alignItems: "start" }}>
              <div style={{
                width: 28, height: 28, borderRadius: 7, background: "var(--ink)",
                display: "flex", alignItems: "center", justifyContent: "center",
                position: "relative", marginTop: 2,
              }}>
                <span style={{
                  position: "absolute", inset: 6, borderRadius: 1,
                  background: "linear-gradient(135deg, #f4f1ea 0 50%, transparent 50%)",
                }}/>
                <span style={{
                  position: "absolute", width: 5, height: 5, top: 6, right: 6,
                  background: "var(--blue)", borderRadius: 1,
                }}/>
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                  <span style={{ font: "500 13px/1 var(--font-sans)", color: "var(--ink)" }}>private·ai</span>
                  <TrustSignal ms={284} retrievals={4} model="claude-haiku-4-5"/>
                </div>

                <div style={{
                  font: "400 14.5px/1.65 var(--font-sans)",
                  color: "var(--text)",
                  letterSpacing: "-0.005em",
                }}>
                  {SAMPLE_ANSWER_BODY}
                </div>

                {/* Action row */}
                <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 16, marginLeft: -6 }}>
                  <button className="btn ghost sm" style={{ padding: "0 7px" }}><Icon.ThumbUp size={13} stroke="var(--text-3)"/></button>
                  <button className="btn ghost sm" style={{ padding: "0 7px" }}><Icon.ThumbDown size={13} stroke="var(--text-3)"/></button>
                  <span style={{ width: 1, height: 14, background: "var(--line)", margin: "0 4px" }}/>
                  <button className="btn ghost sm" style={{ padding: "0 7px" }}><Icon.Copy size={13} stroke="var(--text-3)"/></button>
                  <button className="btn ghost sm" style={{ padding: "0 7px" }}><Icon.Refresh size={13} stroke="var(--text-3)"/></button>
                  <span style={{ flex: 1 }}/>
                  <span style={{ font: "400 11px/1 var(--font-mono)", color: "var(--text-3)" }}>4 sources cited</span>
                </div>
              </div>
            </div>

          </div>
        </div>

        {/* Composer */}
        <div style={{ padding: "12px 20px 20px" }}>
          <div style={{ maxWidth: 720, margin: "0 auto" }}>
            <div className="card" style={{ padding: 4, boxShadow: "var(--sh-1)", borderRadius: 12 }}>
              <div style={{
                display: "flex", alignItems: "flex-end", gap: 8, padding: "10px 12px",
              }}>
                <textarea placeholder="Ask about your indexed documents… (⌘↵ to send)"
                  defaultValue=""
                  style={{
                    flex: 1, border: 0, outline: "none", resize: "none",
                    font: "400 14px/1.5 var(--font-sans)", color: "var(--text)",
                    background: "transparent", minHeight: 22, maxHeight: 100,
                    letterSpacing: "-0.005em",
                  }}/>
                <button className="btn primary" style={{ width: 32, height: 32, padding: 0, borderRadius: 8 }}>
                  <Icon.Send size={14} stroke="#f4f1ea"/>
                </button>
              </div>
              <div style={{
                display: "flex", alignItems: "center", gap: 4, padding: "0 8px 8px 8px",
                borderTop: "1px solid var(--line)", paddingTop: 8,
              }}>
                <button className="btn ghost sm" style={{ padding: "0 8px" }}>
                  <Icon.Folder size={12} stroke="var(--text-3)"/>
                  <span>3 sources</span>
                  <Icon.ChevD size={10} stroke="var(--text-3)" style={{ marginLeft: 2 }}/>
                </button>
                <button className="btn ghost sm" style={{ padding: "0 8px" }}>
                  <Icon.Paper size={12} stroke="var(--text-3)"/>
                  Attach
                </button>
                <span style={{ flex: 1 }}/>
                <span style={{ font: "400 11px/1 var(--font-mono)", color: "var(--text-3)" }}>
                  retrieval: legal · 14,827 chunks
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* CITATION DRAWER */}
      <aside style={{
        background: "var(--surface-2)",
        borderLeft: "1px solid var(--line)",
        display: "flex", flexDirection: "column",
        minHeight: 0,
      }}>
        <div style={{
          padding: "14px 18px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div>
            <div className="kicker" style={{ marginBottom: 2 }}>sources</div>
            <div style={{ font: "500 13px/1 var(--font-sans)", color: "var(--ink)" }}>4 retrieved · 0.84 avg score</div>
          </div>
          <button className="btn ghost sm" style={{ padding: "0 6px" }}>
            <Icon.ChevR size={12} stroke="var(--text-3)"/>
          </button>
        </div>
        <hr className="hr"/>
        <div className="scroll" style={{ flex: 1, overflowY: "auto", padding: "0 18px 18px" }}>
          {SAMPLE_SOURCES.map(s => <SourceRow key={s.i} s={s}/>)}
        </div>
        <div style={{
          borderTop: "1px solid var(--line)",
          padding: "10px 18px",
          font: "400 11px/1.4 var(--font-mono)", color: "var(--text-3)",
          display: "flex", alignItems: "center", gap: 6,
        }}>
          <Icon.Shield size={11} stroke="var(--text-3)"/>
          Retrieval logged · trace 9c4f-2a18
        </div>
      </aside>
    </div>
  );
}
