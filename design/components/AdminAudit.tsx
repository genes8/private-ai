import React from "react";
import { Icon } from "./Icons";
import { AdminShell } from "./AdminShell";

export function AdminAudit() {
  const events = [
    { t: "14:42:08", k: "query", who: "alex.bremer", role: "Legal",
      q: "What's the liability cap on the Riley Aerospace MSA, and does it match our procurement floor?",
      ms: 284, cache: false, model: "haiku-4-5", k_: 4, score: 0.84, fb: "+", trace: "9c4f-2a18" },
    { t: "14:39:51", k: "query", who: "diane.kowalski", role: "Compliance",
      q: "Summarize ISO 27001 encryption-at-rest controls for our SaaS perimeter.",
      ms: 47, cache: true, model: "haiku-4-5", k_: 6, score: 0.91, trace: "be71-4d09" },
    { t: "14:36:14", k: "upload", who: "auto · S3 watch",
      doc: "Q2_Compliance_Audit_Findings.pdf", chunks: 192, status: "embedding" },
    { t: "14:31:02", k: "query", who: "alex.bremer", role: "Legal",
      q: "Northwind MSA — show me the IP carve-out language verbatim.",
      ms: 312, cache: false, model: "haiku-4-5", k_: 3, score: 0.88, trace: "1f2c-87ee" },
    { t: "14:28:45", k: "feedback", who: "marcus.lin", role: "Procurement",
      rating: "down", q: "Vendors with cap below procurement floor",
      note: "Missed Lattice — known cap of 0.5×.", trace: "44a1-d28b" },
    { t: "14:24:11", k: "query", who: "marcus.lin", role: "Procurement",
      q: "List vendors with liability cap below 2× annual fees.",
      ms: 428, cache: false, model: "sonnet-4-5", k_: 8, score: 0.72, trace: "44a1-d28b" },
    { t: "14:18:33", k: "fallback", who: "rashid.h", role: "Eng",
      q: "How do I write a custom retrieval scorer?",
      reason: "Top-1 score 0.34 below threshold (0.5)", model: "haiku-4-5" },
    { t: "14:11:09", k: "login", who: "maya.reyes", role: "Admin", ip: "10.4.8.22" },
    { t: "13:58:27", k: "query", who: "alex.bremer", role: "Legal",
      q: "Lattice termination clause — typical notice period?",
      ms: 38, cache: true, model: "haiku-4-5", k_: 4, score: 0.93, trace: "06bd-9a02" },
    { t: "13:42:01", k: "upload", who: "maya.reyes",
      doc: "Procurement_Playbook_v3.docx", chunks: 64, status: "indexed" },
  ];

  const KindBadge = ({ k }: { k: string }) => {
    const map: Record<string, { lbl: string; bg: string; fg: string }> = {
      query:    { lbl: "QUERY",    bg: "var(--paper-2)",    fg: "var(--text)" },
      upload:   { lbl: "INDEX",    bg: "#eaf0ff",            fg: "#1d3fa6" },
      feedback: { lbl: "FEEDBACK", bg: "#f9efd9",            fg: "#8b5a16" },
      login:    { lbl: "AUTH",     bg: "#e6f3ec",            fg: "#1f6e45" },
      fallback: { lbl: "FALLBACK", bg: "#fbe9e6",            fg: "#8c2a20" },
    };
    const m = map[k];
    return (
      <span className="mono" style={{
        font: "500 9.5px/1 var(--font-mono)", letterSpacing: ".06em",
        padding: "3px 6px", borderRadius: 3, background: m.bg, color: m.fg,
      }}>{m.lbl}</span>
    );
  };

  return (
    <AdminShell
      active="audit"
      title="Activity"
      subtitle="A continuous record of every query, retrieval and admin action."
      headerRight={<>
        <span className="trust" style={{ marginRight: 8 }}>
          <span><b style={{ color: "var(--ink)" }}>1,247</b> events today</span>
          <span style={{ color: "var(--line-3)" }}>·</span>
          <span><b style={{ color: "var(--ink)" }}>312ms</b> p50</span>
          <span style={{ color: "var(--line-3)" }}>·</span>
          <span><b style={{ color: "var(--green)" }}>34%</b> cache</span>
        </span>
        <button className="btn sm"><Icon.Download size={11} stroke="var(--text-2)"/>Export CSV</button>
      </>}
    >
      <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", height: "100%", minHeight: 0 }}>
        {/* FILTER RAIL */}
        <aside style={{ padding: "16px 12px 16px 28px", borderRight: "1px solid var(--line)" }}>
          <div className="kicker" style={{ marginBottom: 8 }}>kind</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 1, marginBottom: 18 }}>
            {[
              ["All",       "1247", true],
              ["Query",     "892",  false],
              ["Index",     "47",   false],
              ["Feedback",  "31",   false],
              ["Auth",      "264",  false],
              ["Fallback",  "13",   false],
            ].map(([n, c, on]) => (
              <div key={n} className={"nav-row" + (on ? " active" : "")} style={{
                ...(on ? { background: "var(--paper-2)" } : {}),
                paddingRight: 8,
              }}>
                <span style={{ flex: 1 }}>{n}</span>
                <span className="mono" style={{ font: "400 11px/1 var(--font-mono)", color: "var(--text-3)" }}>{c}</span>
              </div>
            ))}
          </div>

          <div className="kicker" style={{ marginBottom: 8 }}>user</div>
          <div style={{ position: "relative", marginBottom: 14 }}>
            <Icon.Search size={12} stroke="var(--text-3)" style={{ position: "absolute", left: 8, top: 8 }}/>
            <input className="field" placeholder="filter…"
              style={{ height: 28, fontSize: 12, paddingLeft: 24, background: "var(--surface)" }}/>
          </div>

          <div className="kicker" style={{ marginBottom: 8 }}>range</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 1, marginBottom: 18 }}>
            {[["Last hour", false], ["Today", true], ["Last 7 days", false], ["Last 30 days", false], ["Custom…", false]].map(([n, on]) => (
              <div key={n} className={"nav-row" + (on ? " active" : "")} style={on ? { background: "var(--paper-2)" } : {}}>{n}</div>
            ))}
          </div>

          <div style={{
            background: "var(--paper-2)",
            borderRadius: 6,
            padding: "10px 12px",
            font: "400 11px/1.5 var(--font-mono)",
            color: "var(--text-3)",
          }}>
            <div style={{ font: "500 10.5px/1 var(--font-mono)", color: "var(--ink)", marginBottom: 6, letterSpacing: ".06em", textTransform: "uppercase" }}>retention</div>
            All audit events retained <b style={{ color: "var(--text)" }}>365 days</b>, then archived to immutable storage.
          </div>
        </aside>

        {/* STREAM */}
        <div className="scroll" style={{ overflowY: "auto" }}>
          <div style={{ padding: "0 28px 24px" }}>

            {/* Day header */}
            <div style={{
              position: "sticky", top: 0, zIndex: 2,
              background: "var(--paper)",
              padding: "16px 0 10px",
              display: "flex", alignItems: "baseline", gap: 12,
              borderBottom: "1px solid var(--line)",
            }}>
              <h2 style={{
                font: "500 22px/1 var(--font-serif)",
                fontStyle: "italic", letterSpacing: "-0.01em",
                color: "var(--ink)", margin: 0,
              }}>Today</h2>
              <span className="mono" style={{ font: "400 11.5px/1 var(--font-mono)", color: "var(--text-3)" }}>
                Friday · May 9, 2026
              </span>
              <span style={{ flex: 1 }}/>
              <span style={{ display: "flex", alignItems: "center", gap: 6, font: "400 11.5px/1 var(--font-mono)", color: "var(--text-3)" }}>
                <span className="sdot" style={{ background: "var(--blue)", animation: "pa-caret 1s steps(1) infinite" }}/>
                live
              </span>
            </div>

            {/* Stream — each row shares a left timeline rule */}
            <div style={{ position: "relative", paddingLeft: 18, marginTop: 4 }}>
              {/* timeline rule */}
              <span aria-hidden style={{
                position: "absolute", left: 4, top: 18, bottom: 12, width: 1,
                background: "var(--line)",
              }}/>

              {events.map((e, idx) => (
                <div key={idx} style={{
                  position: "relative",
                  padding: "16px 0",
                  borderBottom: "1px solid var(--line)",
                }}>
                  {/* node dot */}
                  <span aria-hidden style={{
                    position: "absolute", left: -18, top: 22,
                    width: 9, height: 9, borderRadius: "50%",
                    background: "var(--surface)",
                    border: "2px solid " + (
                      e.k === "query" ? "var(--ink)" :
                      e.k === "upload" ? "var(--blue)" :
                      e.k === "feedback" ? "var(--amber)" :
                      e.k === "fallback" ? "var(--red)" :
                      "var(--green)"
                    ),
                  }}/>

                  <div style={{ display: "grid", gridTemplateColumns: "70px 1fr", gap: 18, alignItems: "start" }}>
                    {/* time */}
                    <span className="mono" style={{
                      font: "400 11.5px/1.4 var(--font-mono)", color: "var(--text-3)",
                      paddingTop: 2,
                    }}>{e.t}</span>

                    <div style={{ minWidth: 0 }}>
                      {/* meta line */}
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
                        <KindBadge k={e.k}/>
                        <span style={{ font: "500 12.5px/1 var(--font-sans)", color: "var(--ink)" }}>
                          {e.who}
                        </span>
                        {e.role && <span style={{ font: "400 11px/1 var(--font-mono)", color: "var(--text-3)" }}>· {e.role}</span>}
                        <span style={{ flex: 1 }}/>
                        {e.k === "query" && (
                          <span className="trust" style={{ fontSize: 10.5 }}>
                            <span><b>{e.ms}ms</b></span>
                            <span style={{ color: "var(--line-3)" }}>·</span>
                            <span style={{ color: e.cache ? "var(--green)" : "var(--text-3)" }}>{e.cache ? "cache" : "fresh"}</span>
                            <span style={{ color: "var(--line-3)" }}>·</span>
                            <span>k={e.k_} · score {e.score}</span>
                          </span>
                        )}
                        {e.k === "upload" && (
                          <span className="trust" style={{ fontSize: 10.5 }}>
                            <span><b>{e.chunks}</b> chunks</span>
                            <span style={{ color: "var(--line-3)" }}>·</span>
                            <span style={{ color: e.status === "indexed" ? "var(--green)" : "var(--blue)" }}>{e.status}</span>
                          </span>
                        )}
                        {e.k === "fallback" && (
                          <span className="chip solid-red">no answer · {e.reason}</span>
                        )}
                        {e.k === "feedback" && (
                          <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                            {e.rating === "up"
                              ? <Icon.ThumbUp size={11} stroke="var(--green)"/>
                              : <Icon.ThumbDown size={11} stroke="var(--red)"/>}
                            <span className="mono" style={{ font: "500 10.5px/1 var(--font-mono)", color: e.rating === "up" ? "var(--green)" : "var(--red)" }}>
                              {e.rating === "up" ? "thumbs up" : "thumbs down"}
                            </span>
                          </span>
                        )}
                        {e.k === "login" && <span className="mono" style={{ font: "400 10.5px/1 var(--font-mono)", color: "var(--text-3)" }}>{e.ip}</span>}
                      </div>

                      {/* main content */}
                      {e.q && (
                        <div style={{
                          font: "400 13.5px/1.5 var(--font-sans)",
                          color: "var(--text)",
                          marginBottom: 4,
                          letterSpacing: "-0.005em",
                          display: "-webkit-box",
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                        }}>
                          {e.k === "query" || e.k === "fallback" ? "\u201c" : ""}{e.q}{e.k === "query" || e.k === "fallback" ? "\u201d" : ""}
                        </div>
                      )}
                      {e.note && (
                        <div style={{
                          font: "400 12.5px/1.45 var(--font-sans)",
                          color: "var(--text-2)",
                          background: "var(--paper-2)",
                          borderLeft: "2px solid var(--amber)",
                          padding: "6px 10px", marginTop: 6, borderRadius: "0 4px 4px 0",
                        }}>
                          <span style={{ font: "500 10.5px/1 var(--font-mono)", color: "var(--text-3)", letterSpacing: ".06em", textTransform: "uppercase", marginRight: 6 }}>note</span>
                          {e.note}
                        </div>
                      )}
                      {e.doc && (
                        <div style={{ display: "flex", alignItems: "center", gap: 8, font: "500 13px/1 var(--font-sans)", color: "var(--text)" }}>
                          <Icon.DocText size={12} stroke="var(--text-3)"/>
                          {e.doc}
                        </div>
                      )}

                      {/* footer / trace */}
                      {e.trace && (
                        <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 10 }}>
                          <span className="mono" style={{ font: "400 10.5px/1 var(--font-mono)", color: "var(--text-3)" }}>
                            trace · {e.trace}
                          </span>
                          {e.model && (
                            <span className="mono" style={{ font: "400 10.5px/1 var(--font-mono)", color: "var(--text-3)" }}>
                              · {e.model}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AdminShell>
  );
}
