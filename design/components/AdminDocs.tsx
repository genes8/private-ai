import React from "react";
import { Icon } from "./Icons";
import { AdminShell } from "./AdminShell";

export function AdminDocs() {
  const docs = [
    { name: "MSA_Vendor_Riley_Aerospace_2024.pdf", type: "PDF",  size: "1.2 MB", chunks: 87,  status: "indexed",  date: "2m ago",   by: "Maya R." },
    { name: "Procurement_Playbook_v3.docx",         type: "DOCX", size: "428 KB", chunks: 64,  status: "indexed",  date: "14m ago",  by: "Maya R." },
    { name: "Q2_Compliance_Audit_Findings.pdf",     type: "PDF",  size: "3.4 MB", chunks: 192, status: "embedding", date: "now",     by: "Auto · folder",  progress: 0.62 },
    { name: "Legal_Review_Notes_2025-04-12.md",     type: "MD",   size: "12 KB",  chunks: 4,   status: "indexed",  date: "Apr 28",   by: "Alex B." },
    { name: "ISO27001_Encryption_Scope.pdf",        type: "PDF",  size: "847 KB", chunks: 51,  status: "indexed",  date: "Apr 25",   by: "Diane K." },
    { name: "Northwind_MSA_signed_2023.pdf",        type: "PDF",  size: "892 KB", chunks: 73,  status: "indexed",  date: "Apr 22",   by: "Maya R." },
    { name: "Vendor_Onboarding_Checklist.csv",      type: "CSV",  size: "8 KB",   chunks: 1,   status: "skipped",  date: "Apr 22",   by: "Auto · folder", note: "no extractable text" },
    { name: "Lattice_termination_clause.pdf",       type: "PDF",  size: "210 KB", chunks: 9,   status: "indexed",  date: "Apr 18",   by: "Alex B." },
    { name: "FY24_Audit_Recap.pdf",                 type: "PDF",  size: "2.1 MB", chunks: 121, status: "failed",   date: "Apr 18",   by: "Maya R.",  note: "OCR — page 4 corrupted" },
  ];

  const statusEl = (d: typeof docs[number]) => {
    if (d.status === "indexed")   return <span className="chip green"><span className="dot"/>indexed</span>;
    if (d.status === "embedding") return <span className="chip blue"><span className="dot"/>embedding · {Math.round(d.progress*100)}%</span>;
    if (d.status === "skipped")   return <span className="chip" style={{ color: "var(--text-3)" }}><span className="dot" style={{ background: "var(--slate-2)" }}/>skipped</span>;
    if (d.status === "failed")    return <span className="chip red"><span className="dot"/>failed</span>;
    return <span className="chip"><span className="dot"/>{d.status}</span>;
  };

  return (
    <AdminShell
      active="documents"
      title="Documents"
      subtitle="312 indexed · 14,827 chunks · 2.4 GB · last index 2 min ago"
      headerRight={<>
        <div style={{ position: "relative" }}>
          <Icon.Search size={13} stroke="var(--text-3)" style={{ position: "absolute", left: 9, top: 9.5 }}/>
          <input className="field" placeholder="Search documents…"
            style={{ height: 30, width: 220, paddingLeft: 28, fontSize: 12.5 }}/>
        </div>
        <button className="btn sm"><Icon.Filter size={11} stroke="var(--text-2)"/>Filter</button>
        <button className="btn primary sm"><Icon.Upload size={11} stroke="#f4f1ea"/>Upload</button>
      </>}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", height: "100%", minHeight: 0 }}>
        {/* TABLE */}
        <div className="scroll" style={{ overflowY: "auto", padding: "16px 28px 28px" }}>
          {/* Drop zone */}
          <div style={{
            border: "1.5px dashed var(--line-3)",
            borderRadius: 10,
            background: "rgba(59,108,242,.025)",
            padding: "18px 20px",
            display: "flex", alignItems: "center", gap: 16,
            marginBottom: 18,
          }}>
            <div style={{
              width: 38, height: 38, borderRadius: 9,
              background: "var(--blue-soft)", color: "var(--blue-2)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Icon.Upload size={16} stroke="var(--blue-2)"/>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ font: "500 13px/1.2 var(--font-sans)", color: "var(--ink)", marginBottom: 2 }}>
                Drop PDFs, DOCX, MD or TXT here
              </div>
              <div style={{ font: "400 12px/1.4 var(--font-sans)", color: "var(--text-2)" }}>
                Files are chunked, embedded and indexed within ~30s. Watch
                folders or connect a S3 bucket in <span style={{ color: "var(--blue)" }}>Settings</span>.
              </div>
            </div>
            <button className="btn sm">Browse</button>
          </div>

          {/* Table header */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 2fr) 80px 90px 90px 1fr 28px",
            gap: 12,
            padding: "0 12px 8px",
            font: "500 10.5px/1 var(--font-mono)", letterSpacing: ".06em",
            textTransform: "uppercase", color: "var(--text-3)",
            borderBottom: "1px solid var(--line)",
          }}>
            <span>Name</span>
            <span>Type</span>
            <span>Chunks</span>
            <span>Size</span>
            <span>Status · added by</span>
            <span/>
          </div>

          {/* Rows */}
          <div>
            {docs.map((d, idx) => (
              <div key={idx} style={{
                display: "grid",
                gridTemplateColumns: "minmax(0, 2fr) 80px 90px 90px 1fr 28px",
                gap: 12,
                padding: "12px",
                borderBottom: "1px solid var(--line)",
                alignItems: "center",
                background: idx === 0 ? "rgba(59,108,242,.025)" : "transparent",
              }}>
                {/* Name + icon */}
                <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                  <span style={{
                    width: 26, height: 32, borderRadius: 4,
                    background: d.type === "PDF" ? "#fef0ec" :
                                d.type === "DOCX" ? "#eaf0ff" :
                                d.type === "MD"   ? "var(--paper-2)" :
                                "var(--surface-2)",
                    border: "1px solid var(--line)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    font: "600 9px/1 var(--font-mono)",
                    color: d.type === "PDF" ? "#c0392b" :
                           d.type === "DOCX" ? "#1d3fa6" :
                           "var(--text-2)",
                    flex: "0 0 auto",
                  }}>{d.type}</span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{
                      font: "500 13px/1.2 var(--font-sans)", color: "var(--text)",
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>{d.name}</div>
                    {d.note && (
                      <div style={{ font: "400 11px/1.2 var(--font-mono)", color: d.status === "failed" ? "var(--red)" : "var(--text-3)", marginTop: 2 }}>
                        {d.note}
                      </div>
                    )}
                  </div>
                </div>
                <span className="mono" style={{ font: "400 11.5px/1 var(--font-mono)", color: "var(--text-3)" }}>{d.type}</span>
                <span className="mono" style={{ font: "400 12px/1 var(--font-mono)", color: "var(--text-2)", fontVariantNumeric: "tabular-nums" }}>{d.chunks.toLocaleString()}</span>
                <span className="mono" style={{ font: "400 11.5px/1 var(--font-mono)", color: "var(--text-3)" }}>{d.size}</span>
                <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                  {statusEl(d)}
                  <span style={{
                    font: "400 11px/1 var(--font-mono)", color: "var(--text-3)",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>{d.date} · {d.by}</span>
                </div>
                <button className="btn ghost sm" style={{ padding: "0 4px", height: 22, justifySelf: "end" }}>
                  <Icon.Dots size={12} stroke="var(--text-3)"/>
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* INSPECTOR */}
        <aside style={{
          background: "var(--surface-2)",
          borderLeft: "1px solid var(--line)",
          display: "flex", flexDirection: "column",
        }}>
          <div style={{ padding: "16px 18px 12px" }}>
            <div className="kicker" style={{ marginBottom: 4 }}>selected</div>
            <div style={{ font: "500 13.5px/1.3 var(--font-sans)", color: "var(--ink)", marginBottom: 4 }}>
              MSA_Vendor_Riley_Aerospace_2024.pdf
            </div>
            <div style={{ font: "400 11.5px/1.4 var(--font-mono)", color: "var(--text-3)" }}>
              sha256 · 9c4f2a18…f7e3 · 24 pages
            </div>
          </div>
          <hr className="hr"/>

          <div style={{ padding: "14px 18px" }}>
            <div className="kicker" style={{ marginBottom: 8 }}>indexing</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {[
                ["chunks", "87"],
                ["tokens", "31,420"],
                ["embeddings", "1536-d"],
                ["model", "voyage-3"],
              ].map(([k, v]) => (
                <div key={k} style={{ background: "var(--surface)", borderRadius: 6, padding: "8px 10px" }}>
                  <div style={{ font: "400 10px/1 var(--font-mono)", letterSpacing: ".06em", textTransform: "uppercase", color: "var(--text-3)", marginBottom: 4 }}>{k}</div>
                  <div className="mono" style={{ font: "500 13px/1 var(--font-mono)", color: "var(--ink)", fontVariantNumeric: "tabular-nums" }}>{v}</div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ padding: "0 18px 14px" }}>
            <div className="kicker" style={{ marginBottom: 8 }}>retrieval — last 7 days</div>
            <div className="card" style={{ padding: 12 }}>
              {/* tiny histogram */}
              <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 38, marginBottom: 6 }}>
                {[12, 8, 22, 18, 31, 24, 41, 36, 28, 19, 24, 33, 47, 38].map((v, idx) => (
                  <span key={idx} style={{
                    flex: 1, background: idx > 10 ? "var(--blue)" : "var(--slate-2)",
                    height: v + "%", borderRadius: 1, minHeight: 2,
                  }}/>
                ))}
              </div>
              <div style={{
                display: "flex", justifyContent: "space-between",
                font: "400 10.5px/1 var(--font-mono)", color: "var(--text-3)",
              }}>
                <span><b style={{ color: "var(--ink)" }}>184</b> retrievals · 12 unique users</span>
                <span>↑ 32% w/w</span>
              </div>
            </div>
          </div>

          <div style={{ padding: "0 18px 14px" }}>
            <div className="kicker" style={{ marginBottom: 8 }}>top retrieved chunks</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {[
                { p: 11, q: "§ 9.1 Limitation of Liability", n: 28 },
                { p: 8,  q: "§ 7.2 Indemnification",          n: 19 },
                { p: 14, q: "§ 11 Termination",               n: 11 },
              ].map((c, idx) => (
                <div key={idx} style={{
                  background: "var(--surface)", borderRadius: 6,
                  padding: "8px 10px", display: "flex", alignItems: "center", gap: 8,
                }}>
                  <span className="mono" style={{ font: "500 10.5px/1 var(--font-mono)", color: "var(--text-3)", minWidth: 22 }}>p.{c.p}</span>
                  <span style={{ flex: 1, font: "400 12px/1.2 var(--font-sans)", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.q}</span>
                  <span className="chip" style={{ height: 18, padding: "0 6px", fontSize: 10.5 }}>{c.n}×</span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ flex: 1 }}/>

          <div style={{
            borderTop: "1px solid var(--line)", padding: "10px 14px",
            display: "flex", gap: 6,
          }}>
            <button className="btn sm" style={{ flex: 1 }}><Icon.Refresh size={11} stroke="var(--text-2)"/>Reindex</button>
            <button className="btn sm" style={{ flex: 1, color: "var(--red)" }}><Icon.Trash size={11} stroke="var(--red)"/>Delete</button>
          </div>
        </aside>
      </div>
    </AdminShell>
  );
}
