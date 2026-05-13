import React from "react";
import { Icon } from "./Icons";
import { SAMPLE_ANSWER_BODY, SAMPLE_QUESTION, TrustSignal, UserBubble } from "./ChatShared";

export function ChatB() {
  const sessions = [
    { t: "Riley Aerospace MSA — liability cap", time: "now",   active: true,  count: 3, tag: "legal" },
    { t: "Q2 procurement spend by category",     time: "11:42", active: false, count: 7, tag: "ops" },
    { t: "Northwind renewal — IP carve-out",     time: "Yest", active: false, count: 12, tag: "legal" },
    { t: "Onboarding policy for contractors",    time: "Mon",  active: false, count: 4, tag: "people" },
    { t: "ISO 27001 — encryption-at-rest scope", time: "Mon",  active: false, count: 9, tag: "secops" },
    { t: "FY24 audit findings recap",            time: "Apr 28", active: false, count: 5, tag: "finance" },
    { t: "Lattice termination clause precedent", time: "Apr 24", active: false, count: 6, tag: "legal" },
  ];

  const tagColor = {
    legal:   { bg: "#ecebff", fg: "#3d36c2" },
    ops:     { bg: "#e6f3ec", fg: "#1f6e45" },
    people:  { bg: "#f9efd9", fg: "#8b5a16" },
    secops:  { bg: "#eaf0ff", fg: "#1d3fa6" },
    finance: { bg: "#fbe9e6", fg: "#8c2a20" },
  };

  return (
    <div className="pa-root" style={{
      display: "grid",
      gridTemplateColumns: "260px 1fr 320px",
      height: "100%",
      background: "var(--paper)",
    }}>
      {/* SESSIONS */}
      <aside style={{
        background: "var(--surface-2)",
        borderRight: "1px solid var(--line)",
        display: "flex", flexDirection: "column",
        minHeight: 0,
      }}>
        <div style={{ padding: "14px 12px 10px" }}>
          <div className="pa-logo" style={{ marginBottom: 16, paddingLeft: 4 }}>
            <div className="mark"/>
            <span className="word">private<span className="dim">·ai</span></span>
          </div>
          <div style={{ position: "relative", marginBottom: 10 }}>
            <Icon.Search size={13} stroke="var(--text-3)" style={{ position: "absolute", left: 9, top: 9.5 }}/>
            <input className="field" placeholder="Search threads"
              style={{ height: 30, fontSize: 12.5, paddingLeft: 28, background: "var(--surface)" }}/>
            <span className="kbd" style={{ position: "absolute", right: 6, top: 6 }}>/</span>
          </div>
          <button className="btn primary sm" style={{ width: "100%", justifyContent: "flex-start" }}>
            <Icon.Plus size={12} stroke="#f4f1ea"/>
            New thread
          </button>
        </div>

        <div style={{ padding: "8px 12px 4px" }}>
          <div className="kicker" style={{ marginBottom: 2 }}>recent</div>
        </div>

        <div className="scroll" style={{ flex: 1, overflowY: "auto", padding: "2px 6px 12px" }}>
          {sessions.map((s, idx) => (
            <div key={idx} className={"nav-row" + (s.active ? " active" : "")} style={{
              height: "auto", padding: "8px 8px",
              alignItems: "flex-start", flexDirection: "column", gap: 4,
              ...(s.active ? { background: "var(--surface)", boxShadow: "0 0 0 1px var(--line)" } : {}),
            }}>
              <div style={{
                font: "500 12.5px/1.3 var(--font-sans)",
                color: s.active ? "var(--ink)" : "var(--text)",
                width: "100%",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}>{s.t}</div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
                <span style={{
                  font: "500 9.5px/1 var(--font-mono)",
                  letterSpacing: ".06em", textTransform: "uppercase",
                  color: tagColor[s.tag].fg,
                  background: tagColor[s.tag].bg,
                  padding: "2px 5px", borderRadius: 3,
                }}>{s.tag}</span>
                <span style={{ font: "400 10.5px/1 var(--font-mono)", color: "var(--text-3)" }}>{s.count} msg</span>
                <span style={{ flex: 1 }}/>
                <span style={{ font: "400 10.5px/1 var(--font-mono)", color: "var(--text-3)" }}>{s.time}</span>
              </div>
            </div>
          ))}
        </div>

        <div style={{
          borderTop: "1px solid var(--line)",
          padding: "10px 12px",
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <span className="avatar">AB</span>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ font: "500 12px/1.2 var(--font-sans)", color: "var(--text)" }}>Alex Bremer</div>
            <div style={{ font: "400 10.5px/1.2 var(--font-mono)", color: "var(--text-3)" }}>Legal · pilot</div>
          </div>
          <button className="btn ghost sm" style={{ padding: "0 6px" }}>
            <Icon.Settings size={13} stroke="var(--text-3)"/>
          </button>
        </div>
      </aside>

      {/* MAIN */}
      <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <header style={{
          padding: "14px 24px", borderBottom: "1px solid var(--line)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div>
            <div className="kicker" style={{ marginBottom: 4 }}>thread · 3 messages</div>
            <h2 style={{ font: "500 16px/1 var(--font-sans)", letterSpacing: "-0.01em", margin: 0, color: "var(--ink)" }}>
              Riley Aerospace MSA — liability cap
            </h2>
          </div>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <span className="chip"><Icon.Folder size={11} stroke="var(--text-3)"/> 3 sources scoped</span>
            <button className="btn ghost sm" style={{ padding: "0 7px" }}><Icon.External size={13} stroke="var(--text-3)"/></button>
            <button className="btn ghost sm" style={{ padding: "0 7px" }}><Icon.Dots size={13} stroke="var(--text-3)"/></button>
          </div>
        </header>

        <div className="scroll" style={{ flex: 1, overflowY: "auto", padding: "24px 24px 12px" }}>
          <div style={{ maxWidth: 680, margin: "0 auto" }}>
            <UserBubble>{SAMPLE_QUESTION}</UserBubble>

            <div style={{ display: "grid", gridTemplateColumns: "28px 1fr", gap: 12, alignItems: "start" }}>
              <div style={{
                width: 28, height: 28, borderRadius: 7, background: "var(--ink)",
                position: "relative", marginTop: 2, flex: "0 0 auto",
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
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                  <span style={{ font: "500 13px/1 var(--font-sans)", color: "var(--ink)" }}>private·ai</span>
                  <TrustSignal ms={284} retrievals={4}/>
                </div>
                <div style={{
                  font: "400 14.5px/1.65 var(--font-sans)",
                  color: "var(--text)",
                }}>{SAMPLE_ANSWER_BODY}</div>

                <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 14, marginLeft: -6 }}>
                  <button className="btn ghost sm" style={{ padding: "0 7px" }}><Icon.ThumbUp size={13} stroke="var(--text-3)"/></button>
                  <button className="btn ghost sm" style={{ padding: "0 7px" }}><Icon.ThumbDown size={13} stroke="var(--text-3)"/></button>
                  <button className="btn ghost sm" style={{ padding: "0 7px" }}><Icon.Copy size={13} stroke="var(--text-3)"/></button>
                </div>
              </div>
            </div>

            {/* Follow-up suggestions */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 22, marginLeft: 40 }}>
              <span className="kicker" style={{ width: "100%", marginBottom: 4 }}>follow-up</span>
              {[
                "Draft a redline pushing back to 2× cap",
                "Compare to Northwind's final language",
                "Show me the original §9.1 verbatim",
              ].map(t => (
                <button key={t} className="btn sm" style={{
                  background: "var(--paper-2)", borderColor: "var(--line)",
                  color: "var(--text)", fontWeight: 400,
                }}>{t}</button>
              ))}
            </div>
          </div>
        </div>

        <div style={{ padding: "12px 24px 20px" }}>
          <div style={{ maxWidth: 680, margin: "0 auto" }}>
            <div className="card" style={{ padding: "8px 10px 8px 14px", display: "flex", alignItems: "center", gap: 10 }}>
              <input placeholder="Ask follow-up…"
                style={{
                  flex: 1, border: 0, outline: "none",
                  font: "400 13.5px/1.5 var(--font-sans)", color: "var(--text)",
                  background: "transparent", letterSpacing: "-0.005em",
                }}/>
              <span className="kbd">⌘↵</span>
              <button className="btn primary" style={{ width: 30, height: 30, padding: 0, borderRadius: 7 }}>
                <Icon.Send size={13} stroke="#f4f1ea"/>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* SOURCE RAIL — focused preview */}
      <aside style={{
        background: "var(--surface-2)",
        borderLeft: "1px solid var(--line)",
        display: "flex", flexDirection: "column",
        minHeight: 0,
      }}>
        <div style={{ padding: "14px 16px 6px" }}>
          <div className="kicker" style={{ marginBottom: 4 }}>focused source</div>
          <div style={{ font: "500 12.5px/1.3 var(--font-sans)", color: "var(--ink)", marginBottom: 4 }}>
            MSA_Vendor_Riley_Aerospace_2024.pdf
          </div>
          <div style={{ display: "flex", gap: 6, alignItems: "center", font: "400 11px/1 var(--font-mono)", color: "var(--text-3)" }}>
            <span>p.11 / 24</span>
            <span style={{ color: "var(--line-3)" }}>·</span>
            <span>§ 9.1</span>
            <span style={{ flex: 1 }}/>
            <button className="btn ghost sm" style={{ padding: "0 5px" }}><Icon.ChevL size={11} stroke="var(--text-3)"/></button>
            <button className="btn ghost sm" style={{ padding: "0 5px" }}><Icon.ChevR size={11} stroke="var(--text-3)"/></button>
          </div>
        </div>
        <hr className="hr" style={{ margin: "8px 0 0" }}/>

        {/* PDF page mock */}
        <div style={{ padding: 16, flex: 1, overflow: "hidden" }}>
          <div style={{
            background: "#fff",
            border: "1px solid var(--line)",
            borderRadius: 6,
            boxShadow: "var(--sh-1)",
            padding: 18,
            height: "100%",
            position: "relative",
            overflow: "hidden",
          }}>
            <div style={{ font: "500 9.5px/1 var(--font-mono)", color: "var(--text-3)", letterSpacing: ".05em", marginBottom: 14 }}>
              MSA — RILEY AEROSPACE · CONFIDENTIAL
            </div>
            {/* fake paragraphs */}
            {[100, 92, 96, 86, 0].map((w, i) => (
              <div key={i} style={{
                height: 5, background: "var(--paper-3)", borderRadius: 2,
                width: w + "%", marginBottom: 7,
              }}/>
            ))}
            <div style={{
              font: "500 11px/1 var(--font-sans)", color: "var(--ink)",
              marginTop: 14, marginBottom: 8,
            }}>9.1  Limitation of Liability</div>
            {/* Highlighted passage */}
            <div style={{
              background: "rgba(59,108,242,.10)",
              border: "1px solid rgba(59,108,242,.25)",
              borderRadius: 4,
              padding: "8px 10px",
              font: "400 11px/1.55 var(--font-sans)",
              color: "var(--text)",
              position: "relative",
              marginBottom: 10,
            }}>
              <span className="cite-chip" style={{ position: "absolute", left: -8, top: -8 }}>2</span>
              Notwithstanding anything to the contrary, each party's aggregate liability under this
              Agreement shall not exceed the fees paid by Customer to Vendor in the twelve (12) months
              preceding the claim…
            </div>
            {[94, 88, 100, 70].map((w, i) => (
              <div key={i} style={{
                height: 5, background: "var(--paper-3)", borderRadius: 2,
                width: w + "%", marginBottom: 7,
              }}/>
            ))}
          </div>
        </div>

        <div style={{
          borderTop: "1px solid var(--line)",
          padding: "10px 16px",
          display: "flex", gap: 8, alignItems: "center",
        }}>
          <button className="btn sm" style={{ flex: 1 }}>
            <Icon.External size={11} stroke="var(--text-2)"/>
            Open document
          </button>
          <button className="btn sm" style={{ padding: "0 8px" }}>
            <Icon.Download size={11} stroke="var(--text-2)"/>
          </button>
        </div>
      </aside>
    </div>
  );
}
