import React from "react";
import { Icon } from "./Icons";
import { AdminShell } from "./AdminShell";

export function AdminFeedback() {
  const items = [
    { id: 1, rating: "down", who: "Marcus Lin",   role: "Procurement", time: "14m ago",
      q: "List vendors with liability cap below 2× annual fees.",
      note: "Missed Lattice — known cap of 0.5×.",
      active: true },
    { id: 2, rating: "up",   who: "Diane Kowalski", role: "Compliance", time: "32m ago",
      q: "Summarize ISO 27001 encryption-at-rest controls for our SaaS perimeter.",
      note: "Great cite to §A.10.1; saved me 20 min." },
    { id: 3, rating: "up",   who: "Alex Bremer",  role: "Legal",      time: "1h ago",
      q: "Northwind MSA — show me the IP carve-out language verbatim.",
      note: "" },
    { id: 4, rating: "down", who: "Rashid Hassan", role: "Eng",       time: "3h ago",
      q: "How do I write a custom retrieval scorer?",
      note: "Fell back; the engineering wiki should be indexed." },
    { id: 5, rating: "up",   who: "Priya Nair",   role: "Finance",    time: "Yesterday",
      q: "FY24 audit — top three findings by severity?",
      note: "" },
    { id: 6, rating: "up",   who: "Alex Bremer",  role: "Legal",      time: "Yesterday",
      q: "Lattice termination clause — typical notice period?",
      note: "Cached and instant. Love it." },
  ];

  return (
    <AdminShell
      active="feedback"
      title="Feedback"
      subtitle="259 ratings this week · 95.4% helpful · 12 flagged for review"
      headerRight={<>
        <button className="btn sm" style={{ background: "var(--paper-2)" }}>All · 259</button>
        <button className="btn sm">👍 247</button>
        <button className="btn sm" style={{ background: "var(--red-soft)", color: "var(--red)", borderColor: "var(--red-soft)" }}>👎 12</button>
      </>}
    >
      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", height: "100%", minHeight: 0 }}>
        {/* LIST */}
        <aside style={{ borderRight: "1px solid var(--line)", display: "flex", flexDirection: "column" }}>
          <div className="scroll" style={{ overflowY: "auto", flex: 1 }}>
            {items.map(it => (
              <div key={it.id} style={{
                padding: "14px 18px",
                borderBottom: "1px solid var(--line)",
                background: it.active ? "var(--paper-2)" : "transparent",
                borderLeft: it.active ? "2px solid var(--ink)" : "2px solid transparent",
                cursor: "default",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  {it.rating === "up"
                    ? <Icon.ThumbUp size={11} stroke="var(--green)"/>
                    : <Icon.ThumbDown size={11} stroke="var(--red)"/>}
                  <span style={{ font: "500 12.5px/1 var(--font-sans)", color: "var(--ink)" }}>{it.who}</span>
                  <span style={{ font: "400 10.5px/1 var(--font-mono)", color: "var(--text-3)" }}>· {it.role}</span>
                  <span style={{ flex: 1 }}/>
                  <span style={{ font: "400 10.5px/1 var(--font-mono)", color: "var(--text-3)" }}>{it.time}</span>
                </div>
                <div style={{
                  font: "400 13px/1.4 var(--font-sans)", color: "var(--text)", marginBottom: 4,
                  display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
                  letterSpacing: "-0.005em",
                }}>"{it.q}"</div>
                {it.note && (
                  <div style={{
                    font: "400 11.5px/1.45 var(--font-sans)", color: "var(--text-2)",
                    background: it.rating === "down" ? "var(--red-soft)" : "var(--green-soft)",
                    color: it.rating === "down" ? "#8c2a20" : "#1f6e45",
                    padding: "5px 8px", borderRadius: 4, marginTop: 2,
                  }}>{it.note}</div>
                )}
              </div>
            ))}
          </div>
        </aside>

        {/* DETAIL */}
        <div className="scroll" style={{ overflowY: "auto" }}>
          <div style={{ padding: "24px 32px 36px", maxWidth: 760 }}>

            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <span className="chip solid-red"><Icon.ThumbDown size={11} stroke="#8c2a20"/> thumbs down</span>
              <span className="mono" style={{ font: "400 11.5px/1 var(--font-mono)", color: "var(--text-3)" }}>
                trace · 44a1-d28b · 14:24:11 · 14m ago
              </span>
              <span style={{ flex: 1 }}/>
              <button className="btn sm"><Icon.ChevL size={11} stroke="var(--text-2)"/></button>
              <button className="btn sm"><Icon.ChevR size={11} stroke="var(--text-2)"/></button>
            </div>

            {/* Reporter */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
              <span className="avatar" style={{ background: "var(--ink)" }}>ML</span>
              <div>
                <div style={{ font: "500 13.5px/1.2 var(--font-sans)", color: "var(--ink)" }}>Marcus Lin</div>
                <div style={{ font: "400 11.5px/1 var(--font-mono)", color: "var(--text-3)" }}>marcus.lin@safe4ai.com · Procurement</div>
              </div>
            </div>

            {/* Question */}
            <div className="kicker" style={{ marginBottom: 6 }}>question</div>
            <div style={{
              font: "400 16px/1.5 var(--font-serif)", fontStyle: "italic",
              color: "var(--ink)", marginBottom: 22, letterSpacing: "-0.005em",
              borderLeft: "2px solid var(--ink)", paddingLeft: 14,
            }}>
              "List vendors with liability cap below 2× annual fees."
            </div>

            {/* Answer */}
            <div className="kicker" style={{ marginBottom: 6 }}>answer given</div>
            <div className="card" style={{ padding: 16, marginBottom: 14 }}>
              <p style={{ font: "400 13.5px/1.6 var(--font-sans)", color: "var(--text)", margin: "0 0 8px", letterSpacing: "-0.005em" }}>
                Based on the indexed MSAs, two vendors currently sit below the 2×
                procurement floor:
              </p>
              <ul style={{ margin: 0, paddingLeft: 20, font: "400 13.5px/1.6 var(--font-sans)", color: "var(--text)" }}>
                <li>Riley Aerospace — 1× annual fees<span className="cite-chip">2</span></li>
                <li>Northwind Industries — 1.5× annual fees<span className="cite-chip">5</span></li>
              </ul>
            </div>

            {/* Reviewer note */}
            <div className="kicker" style={{ marginBottom: 6 }}>marcus's comment</div>
            <div style={{
              background: "var(--red-soft)", color: "#8c2a20",
              borderRadius: 8, padding: "12px 14px",
              font: "400 13.5px/1.5 var(--font-sans)", letterSpacing: "-0.005em",
              marginBottom: 22,
            }}>
              "Missed <b>Lattice</b> — known cap of 0.5×, signed last quarter. Worth
              checking why it didn't surface."
            </div>

            {/* Trace */}
            <div className="kicker" style={{ marginBottom: 8 }}>trace</div>
            <div className="card" style={{ padding: "12px 16px", marginBottom: 14 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 14 }}>
                {[
                  ["latency",  "428ms"],
                  ["cache",    "fresh"],
                  ["model",    "sonnet-4-5"],
                  ["k retrieved", "8"],
                ].map(([k, v]) => (
                  <div key={k}>
                    <div className="kicker" style={{ marginBottom: 4 }}>{k}</div>
                    <div className="mono" style={{ font: "500 13px/1 var(--font-mono)", color: "var(--ink)" }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="kicker" style={{ marginBottom: 8 }}>retrieved chunks (k=8)</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 18 }}>
              {[
                { score: 0.88, doc: "MSA_Vendor_Riley_Aerospace_2024.pdf", loc: "p.11 · §9.1", in: true },
                { score: 0.82, doc: "Northwind_MSA_signed_2023.pdf",        loc: "p.9 · §10.2", in: true },
                { score: 0.76, doc: "Procurement_Playbook_v3.docx",         loc: "p.14 · §4.4", in: true },
                { score: 0.71, doc: "MSA_Vendor_Acme_2022.pdf",              loc: "p.6 · §8.1",  in: false },
                { score: 0.64, doc: "Northwind_MSA_signed_2023.pdf",         loc: "p.11 · §11",  in: false },
                { score: 0.41, doc: "MSA_Vendor_Vertex_2024.pdf",            loc: "p.5 · §7.4",  in: false },
              ].map((c, idx) => (
                <div key={idx} style={{
                  display: "grid",
                  gridTemplateColumns: "auto 50px minmax(0, 1fr) auto",
                  gap: 12,
                  padding: "8px 12px",
                  background: c.in ? "var(--paper-2)" : "var(--surface)",
                  border: "1px solid var(--line)",
                  borderRadius: 6,
                  alignItems: "center",
                }}>
                  <span className="mono" style={{
                    font: "500 11px/1 var(--font-mono)",
                    color: c.score >= 0.7 ? "var(--green)" : "var(--text-3)",
                    fontVariantNumeric: "tabular-nums",
                  }}>{c.score.toFixed(2)}</span>
                  {c.in
                    ? <span className="chip solid-blue" style={{ height: 18, fontSize: 10 }}>used</span>
                    : <span className="chip" style={{ height: 18, fontSize: 10, color: "var(--text-3)" }}>filtered</span>}
                  <span style={{ minWidth: 0, font: "500 12.5px/1 var(--font-sans)", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {c.doc}
                  </span>
                  <span className="mono" style={{ font: "400 11px/1 var(--font-mono)", color: "var(--text-3)" }}>{c.loc}</span>
                </div>
              ))}
            </div>

            <div className="card" style={{
              padding: 14, background: "var(--paper-2)", borderColor: "var(--line)",
              display: "flex", gap: 12, alignItems: "center",
            }}>
              <span style={{
                width: 32, height: 32, borderRadius: 7, background: "var(--amber-soft)", color: "#8b5a16",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>!</span>
              <div style={{ flex: 1 }}>
                <div style={{ font: "500 13px/1.3 var(--font-sans)", color: "var(--ink)", marginBottom: 2 }}>
                  Suspected cause: Lattice MSA chunking
                </div>
                <div style={{ font: "400 12px/1.4 var(--font-sans)", color: "var(--text-2)" }}>
                  Lattice MSA was indexed but its liability cap lives in a table on p.7 — table extraction may have dropped it. Reindex with table-aware extractor.
                </div>
              </div>
              <button className="btn primary sm">Reindex</button>
            </div>

          </div>
        </div>
      </div>
    </AdminShell>
  );
}
