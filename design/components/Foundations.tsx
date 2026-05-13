import React from "react";

export function Foundations() {
  return (
    <div className="pa-root" style={{ padding: 36, background: "var(--paper)" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 36, height: "100%" }}>
        {/* LEFT: brand block */}
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <div className="kicker" style={{ marginBottom: 24 }}>safe4ai · internal · phase 4</div>
            <h1 style={{
              font: "500 56px/0.98 var(--font-serif)",
              letterSpacing: "-0.02em",
              margin: "0 0 18px 0",
              color: "var(--ink)",
              fontStyle: "italic",
            }}>
              private<span style={{ fontStyle: "normal", color: "var(--blue)" }}>·</span>ai
            </h1>
            <p style={{
              font: "400 17px/1.45 var(--font-sans)",
              letterSpacing: "-0.01em",
              color: "var(--text-2)",
              maxWidth: 480,
              margin: 0,
              textWrap: "pretty",
            }}>
              An internal RAG console for regulated teams — every answer is grounded in your
              own documents, every retrieval is logged, every model call is auditable.
            </p>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14, marginTop: 32 }}>
            {[
              ["Cited.", "Inline footnotes link back to source page + chunk."],
              ["Logged.", "Every prompt, retrieval and model call is auditable."],
              ["Yours.", "Documents and embeddings stay in your tenancy."],
            ].map(([h, b]) => (
              <div key={h}>
                <div style={{ font: "500 13px/1 var(--font-sans)", color: "var(--ink)", marginBottom: 6 }}>{h}</div>
                <div style={{ font: "400 12px/1.45 var(--font-sans)", color: "var(--text-2)" }}>{b}</div>
              </div>
            ))}
          </div>
        </div>

        {/* RIGHT: token grid */}
        <div style={{ display: "grid", gridTemplateRows: "auto auto auto 1fr", gap: 18 }}>
          {/* Color */}
          <div>
            <div className="kicker" style={{ marginBottom: 10 }}>palette</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 8 }}>
              {[
                ["Ink",    "#0b0d10", "#f4f1ea"],
                ["Paper",  "#f4f1ea", "#0b0d10"],
                ["Slate",  "#7c8aa0", "#f4f1ea"],
                ["Mist",   "#d6dde6", "#0b0d10"],
                ["Action", "#3b6cf2", "#ffffff"],
                ["Cream",  "#fafaf7", "#0b0d10"],
              ].map(([n, bg, fg]) => (
                <div key={n} style={{
                  height: 64, borderRadius: 8, background: bg, color: fg,
                  border: "1px solid var(--line)",
                  display: "flex", flexDirection: "column", justifyContent: "space-between",
                  padding: 8,
                  font: "500 10.5px/1 var(--font-mono)",
                  letterSpacing: 0,
                }}>
                  <span style={{ fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 500 }}>{n}</span>
                  <span style={{ opacity: .8 }}>{bg}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Type */}
          <div>
            <div className="kicker" style={{ marginBottom: 10 }}>type</div>
            <div className="card" style={{ padding: "4px 16px" }}>
              {[
                ["Geist",            "500 26px/1.15 var(--font-sans)",   "display · body · ui",                       "-0.02em"],
                ["Instrument Serif", "italic 500 28px/1.15 var(--font-serif)", "brand · headlines",                  "-0.005em"],
                ["Geist Mono",       "500 20px/1.15 var(--font-mono)",   "citations · timestamps · trust signals",   "0"],
              ].map(([name, f, desc, ls], idx, arr) => (
                <div key={name} style={{
                  display: "flex", alignItems: "baseline", gap: 12,
                  padding: "12px 0",
                  borderTop: idx === 0 ? "0" : "1px solid var(--line)",
                }}>
                  <span style={{ font: f, letterSpacing: ls, color: "var(--ink)", flex: "0 0 auto" }}>{name}</span>
                  <span style={{
                    font: "400 11px/1.3 var(--font-mono)", color: "var(--text-3)",
                    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                    minWidth: 0, flex: "1 1 auto",
                  }}>{desc}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Components */}
          <div>
            <div className="kicker" style={{ marginBottom: 10 }}>primitives</div>
            <div className="card" style={{ padding: 14, display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
              <button className="btn primary">Send</button>
              <button className="btn">Cancel</button>
              <button className="btn ghost">Skip</button>
              <span className="chip green"><span className="dot"/>indexed</span>
              <span className="chip"><span className="dot"/>queued</span>
              <span className="chip solid-blue">cache hit</span>
              <span className="cite-chip">12</span>
              <span className="kbd">⌘K</span>
              <span className="trust"><b>312ms</b> · cache · claude-haiku</span>
            </div>
          </div>

          {/* Voice */}
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <div style={{
              borderLeft: "2px solid var(--ink)",
              paddingLeft: 14,
              font: "italic 400 15px/1.45 var(--font-serif)",
              color: "var(--text)",
              maxWidth: 460,
            }}>
              "Calm, precise, accountable. We never invent. If the documents don't say it,
              the answer says <span style={{ background: "var(--paper-3)" }}>I don't know</span>."
              <div style={{ font: "400 11px/1 var(--font-mono)", color: "var(--text-3)", marginTop: 8, fontStyle: "normal" }}>— voice & tone</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
