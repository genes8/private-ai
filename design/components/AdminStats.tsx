import React from "react";
import { Icon } from "./Icons";
import { AdminShell } from "./AdminShell";

export function AdminStats() {
  const Spark = ({ data, color = "var(--ink)", height = 26, fill = false }: {
    data: number[];
    color?: string;
    height?: number;
    fill?: boolean;
  }) => {
    const max = Math.max(...data);
    const min = Math.min(...data);
    const w = 80;
    const step = w / (data.length - 1);
    const norm = (v: number) => height - ((v - min) / (max - min || 1)) * (height - 4) - 2;
    const path = data.map((v, idx) => `${idx === 0 ? "M" : "L"}${(idx * step).toFixed(1)},${norm(v).toFixed(1)}`).join(" ");
    const area = `${path} L${w},${height} L0,${height} Z`;
    return (
      <svg width={w} height={height} style={{ verticalAlign: "-3px" }}>
        {fill && <path d={area} fill={color} fillOpacity="0.08"/>}
        <path d={path} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx={w} cy={norm(data[data.length-1])} r="2" fill={color}/>
      </svg>
    );
  };

  const Stat = ({ value, unit, sub, color }: { value: string; unit?: string; sub?: string; color?: string }) => (
    <span style={{
      display: "inline-flex", alignItems: "baseline", gap: 3,
      background: "var(--paper-2)", padding: "1px 8px", borderRadius: 4,
      verticalAlign: "1px",
    }}>
      <b className="mono" style={{
        font: "500 16px/1 var(--font-mono)", color: color || "var(--ink)",
        fontVariantNumeric: "tabular-nums",
      }}>{value}</b>
      {unit && <span className="mono" style={{ font: "400 11px/1 var(--font-mono)", color: "var(--text-3)" }}>{unit}</span>}
      {sub && <span className="mono" style={{ font: "400 11px/1 var(--font-mono)", color: "var(--text-3)" }}>· {sub}</span>}
    </span>
  );

  return (
    <AdminShell
      active="overview"
      title="Today's briefing"
      subtitle="Friday · May 9, 2026 — generated at 14:42, refreshes every 5 min."
      headerRight={<>
        <button className="btn sm"><Icon.Download size={11} stroke="var(--text-2)"/>Export JSON</button>
        <button className="btn sm"><Icon.Refresh size={11} stroke="var(--text-2)"/>Refresh</button>
      </>}
    >
      <div className="scroll" style={{ overflowY: "auto", height: "100%" }}>
        <div style={{
          maxWidth: 760, margin: "0 auto", padding: "32px 28px 48px",
        }}>

          {/* Headline */}
          <div className="kicker" style={{ marginBottom: 12 }}>summary</div>
          <p style={{
            font: "400 19px/1.5 var(--font-serif)",
            color: "var(--ink)",
            margin: "0 0 28px",
            letterSpacing: "-0.005em",
            textWrap: "pretty",
          }}>
            The pilot processed{" "}
            <Stat value="1,247" sub="↑ 18% w/w"/>{" "}
            queries today across{" "}
            <Stat value="34"/>{" "}
            active users. Median latency held at{" "}
            <Stat value="312" unit="ms"/>{" "}
            and the cache absorbed{" "}
            <Stat value="34" unit="%" color="var(--green)"/>{" "}
            of traffic — both inside target. The fallback rate climbed to{" "}
            <Stat value="4.1" unit="%" color="var(--amber)"/>, mostly driven by an
            unindexed batch of HR policies users started asking about.
          </p>

          {/* Latency chart */}
          <div style={{
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: 10,
            padding: "20px 24px",
            marginBottom: 32,
          }}>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 14 }}>
              <div>
                <div className="kicker" style={{ marginBottom: 4 }}>latency · 24h</div>
                <div style={{ font: "500 15px/1 var(--font-sans)", color: "var(--ink)" }}>p50 / p95 across all queries</div>
              </div>
              <div style={{ display: "flex", gap: 14, font: "400 11px/1 var(--font-mono)", color: "var(--text-3)" }}>
                <span><span className="sdot" style={{ background: "var(--ink)", marginRight: 4 }}/> p50</span>
                <span><span className="sdot" style={{ background: "var(--blue)", marginRight: 4 }}/> p95</span>
              </div>
            </div>

            {/* Chart */}
            <div style={{ position: "relative", height: 140, marginLeft: 28 }}>
              {/* y-axis labels */}
              {[800, 600, 400, 200, 0].map((v, idx) => (
                <span key={v} className="mono" style={{
                  position: "absolute", left: -32, top: idx * 35 - 6,
                  font: "400 10px/1 var(--font-mono)", color: "var(--text-3)",
                }}>{v}</span>
              ))}
              {/* grid lines */}
              {[0, 1, 2, 3, 4].map(i => (
                <span key={i} aria-hidden style={{
                  position: "absolute", left: 0, right: 0, top: i * 35,
                  height: 1, background: i === 4 ? "var(--line-3)" : "var(--line)",
                }}/>
              ))}
              {/* chart svg */}
              <svg viewBox="0 0 600 140" preserveAspectRatio="none" style={{
                position: "absolute", inset: 0, width: "100%", height: "100%",
              }}>
                {/* p95 area */}
                <path
                  d="M0,80 C40,75 80,60 120,68 C160,76 200,55 240,40 C280,25 320,55 360,52 C400,50 440,38 480,42 C520,46 560,30 600,38 L600,140 L0,140 Z"
                  fill="rgba(59,108,242,0.07)"
                />
                {/* p95 line */}
                <path
                  d="M0,80 C40,75 80,60 120,68 C160,76 200,55 240,40 C280,25 320,55 360,52 C400,50 440,38 480,42 C520,46 560,30 600,38"
                  fill="none" stroke="var(--blue)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke"
                />
                {/* p50 line */}
                <path
                  d="M0,108 C40,106 80,100 120,103 C160,105 200,96 240,92 C280,88 320,98 360,96 C400,94 440,90 480,92 C520,93 560,89 600,91"
                  fill="none" stroke="var(--ink)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke"
                />
                {/* now marker */}
                <line x1="540" y1="0" x2="540" y2="140" stroke="var(--text-3)" strokeWidth="1" strokeDasharray="2 3" vectorEffect="non-scaling-stroke"/>
              </svg>
            </div>
            {/* x-axis */}
            <div style={{
              display: "flex", justifyContent: "space-between", marginTop: 8, marginLeft: 28,
              font: "400 10.5px/1 var(--font-mono)", color: "var(--text-3)",
            }}>
              <span>00:00</span><span>04:00</span><span>08:00</span><span>12:00</span><span>now · 14:42</span><span style={{ opacity: 0 }}>20:00</span>
            </div>
          </div>

          {/* Section: traffic */}
          <div className="kicker" style={{ marginBottom: 10 }}>traffic</div>
          <p style={{ font: "400 14.5px/1.65 var(--font-sans)", color: "var(--text)", margin: "0 0 14px", letterSpacing: "-0.005em" }}>
            Volume is concentrated in the <b>11am–3pm</b> window
            {"  "}<Spark data={[3, 5, 4, 8, 12, 18, 24, 28, 31, 22, 14, 9, 6, 4]} fill/>{"  "}
            with Legal and Procurement together accounting for <Stat value="71" unit="%"/> of queries.
            The <b>Riley Aerospace MSA</b> remains the most-retrieved document for
            the third day running ({" "}<Stat value="184"/>{" "}retrievals · 12 unique users).
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, margin: "16px 0 28px" }}>
            {[
              { label: "Total queries",   value: "1,247", trend: "+18%", up: true,  data: [22,28,24,31,35,29,38,42,47,53,49,58] },
              { label: "Unique users",    value: "34",    trend: "+2",  up: true,   data: [21, 24, 22, 25, 28, 26, 30, 31, 29, 32, 33, 34] },
              { label: "Avg cost / query", value: "$0.018", trend: "−12%", up: false, data: [0.024, 0.022, 0.023, 0.021, 0.02, 0.019, 0.019, 0.018, 0.018] },
            ].map(s => (
              <div key={s.label} style={{
                background: "var(--surface)", border: "1px solid var(--line)",
                borderRadius: 8, padding: "12px 14px",
              }}>
                <div className="kicker" style={{ marginBottom: 6 }}>{s.label}</div>
                <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 6 }}>
                  <span className="mono" style={{ font: "500 22px/1 var(--font-mono)", color: "var(--ink)", fontVariantNumeric: "tabular-nums" }}>{s.value}</span>
                  <span style={{
                    font: "500 11px/1 var(--font-mono)",
                    color: s.up ? "var(--green)" : "var(--green)",
                  }}>{s.trend}</span>
                </div>
                <Spark data={s.data} color="var(--slate)" fill/>
              </div>
            ))}
          </div>

          {/* Section: quality */}
          <div className="kicker" style={{ marginBottom: 10 }}>quality</div>
          <p style={{ font: "400 14.5px/1.65 var(--font-sans)", color: "var(--text)", margin: "0 0 14px", letterSpacing: "-0.005em" }}>
            Of the <Stat value="1,247"/> answers, <Stat value="89.3" unit="%" color="var(--green)"/>
            cleared the retrieval-score floor; {" "}
            <Stat value="51"/> queries fell back to "I don't know" — the
            preferred outcome over hallucinating. Users marked{" "}
            <Stat value="247" sub="👍" color="var(--green)"/> answers helpful and{" "}
            <Stat value="12" sub="👎" color="var(--red)"/> not — a roughly 20:1 ratio,
            consistent with last week.
          </p>

          {/* feedback bar */}
          <div style={{
            background: "var(--surface)", border: "1px solid var(--line)",
            borderRadius: 8, padding: "14px 16px", margin: "16px 0 28px",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
              <Icon.ThumbUp size={12} stroke="var(--text-3)"/>
              <span style={{ font: "500 12px/1 var(--font-sans)", color: "var(--ink)", flex: 1 }}>247 helpful · 12 not helpful</span>
              <span className="mono" style={{ font: "400 11px/1 var(--font-mono)", color: "var(--text-3)" }}>20.6 : 1</span>
            </div>
            <div style={{ height: 8, borderRadius: 4, background: "var(--paper-2)", overflow: "hidden", display: "flex" }}>
              <div style={{ width: "95.4%", background: "var(--green)" }}/>
              <div style={{ width: "4.6%", background: "var(--red)" }}/>
            </div>
          </div>

          {/* Section: notable */}
          <div className="kicker" style={{ marginBottom: 10 }}>worth a look</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[
              { tag: "FALLBACK", color: "var(--red)",
                head: "13 queries about HR policies returned no answer.",
                body: "Top-1 retrieval scores 0.31–0.42, well below the 0.5 floor. Likely cause: the HR policy folder hasn't been indexed yet.",
                cta: "Index folder" },
              { tag: "FEEDBACK", color: "var(--amber)",
                head: "Marcus Lin gave thumbs-down on a Procurement query.",
                body: "Note: \"Missed Lattice — known cap of 0.5×.\" Trace 44a1-d28b. Worth checking the document chunking; the Lattice MSA has tables that may have been dropped.",
                cta: "Open trace" },
              { tag: "INDEX",    color: "var(--blue)",
                head: "Q2_Compliance_Audit_Findings.pdf is still embedding (62%).",
                body: "Larger than usual at 192 chunks; expected to land in the next ~90s.",
                cta: "View progress" },
            ].map((n, idx) => (
              <div key={idx} style={{
                display: "grid", gridTemplateColumns: "70px 1fr auto", gap: 14,
                padding: "12px 14px",
                background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8,
                alignItems: "start",
              }}>
                <span className="mono" style={{
                  font: "500 9.5px/1 var(--font-mono)", letterSpacing: ".06em",
                  color: n.color,
                  alignSelf: "start", marginTop: 2,
                }}>{n.tag}</span>
                <div>
                  <div style={{ font: "500 13.5px/1.4 var(--font-sans)", color: "var(--ink)", marginBottom: 4, letterSpacing: "-0.005em" }}>{n.head}</div>
                  <div style={{ font: "400 12.5px/1.5 var(--font-sans)", color: "var(--text-2)" }}>{n.body}</div>
                </div>
                <button className="btn sm">{n.cta}</button>
              </div>
            ))}
          </div>

          {/* Section: cost */}
          <div className="kicker" style={{ margin: "28px 0 10px" }}>cost</div>
          <p style={{ font: "400 14.5px/1.65 var(--font-sans)", color: "var(--text)", margin: 0, letterSpacing: "-0.005em" }}>
            Today's spend so far: <Stat value="$22.45"/>, of which{" "}
            <Stat value="$3.92" sub="embeddings"/>, <Stat value="$17.81" sub="generation"/>{" "}
            and <Stat value="$0.72" sub="reranker"/>. Pace puts the day's total around <b>$31</b>
            {" "} — well under the <b>$80</b> daily ceiling.
          </p>
        </div>
      </div>
    </AdminShell>
  );
}
