import React from "react";
import { Icon } from "./Icons";
import type { SourceData } from "../types";

const SAMPLE_SOURCES: SourceData[] = [
  { i: 1, file: "MSA_Vendor_Riley_Aerospace_2024.pdf",   page: 8,  loc: "§ 7.2 — Indemnification", excerpt: "The Vendor shall indemnify and hold harmless the Customer from any third-party claim arising out of (a) Vendor's gross negligence, (b) infringement of intellectual property rights, or (c) unauthorized disclosure of Confidential Information…" },
  { i: 2, file: "MSA_Vendor_Riley_Aerospace_2024.pdf",   page: 11, loc: "§ 9.1 — Liability cap",       excerpt: "Notwithstanding anything to the contrary, each party's aggregate liability under this Agreement shall not exceed the fees paid by Customer to Vendor in the twelve (12) months preceding the claim…" },
  { i: 3, file: "Procurement_Playbook_v3.docx",          page: 14, loc: "§ 4.4 — Liability tiering",   excerpt: "For Tier-2 vendors with annual contract value above $250k, Procurement requires a minimum liability cap of 2× annual fees, plus a carve-out for IP infringement and confidentiality breaches uncapped." },
  { i: 4, file: "Legal_Review_Notes_2025-04-12.md",      page: 1,  loc: "Notes — Riley Aero renewal",   excerpt: "Riley Aerospace agreed to a 2× cap during last cycle but reverted to 1× in current draft. Recommend pushing back; precedent set with Northwind and Lattice." },
];

const SAMPLE_ANSWER_BODY: React.ReactElement = (
  <>
    <p>
      Under the current draft, <b>Riley Aerospace's aggregate liability is capped at 1× the fees paid in the trailing twelve months</b>
      <span className="cite-chip">2</span> — meaningfully below the company's procurement minimum of 2× annual fees for Tier-2 vendors
      <span className="cite-chip">3</span>.
    </p>
    <p>
      The cap excludes the standard carve-outs for indemnification of IP infringement and unauthorized disclosure of Confidential Information
      <span className="cite-chip">1</span>, so those exposures remain uncapped.
    </p>
    <p>
      During the prior cycle Riley accepted a 2× cap, and Legal flagged the reversion in the latest review notes
      <span className="cite-chip">4</span>. Procurement precedent (Northwind, Lattice) supports holding the line.
    </p>
  </>
);

const SAMPLE_QUESTION: string = "What's the liability cap on the Riley Aerospace MSA, and does it match our procurement floor?";

function SourceRow({ s, compact = false }: { s: SourceData; compact?: boolean }) {
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "20px 1fr",
      gap: 10,
      padding: compact ? "8px 0" : "12px 0",
      borderTop: "1px solid var(--line)",
      alignItems: "start",
    }}>
      <span className="cite-chip" style={{ marginTop: 1 }}>{s.i}</span>
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <Icon.DocText size={12} stroke="var(--text-3)"/>
          <span style={{
            font: "500 12px/1 var(--font-sans)", color: "var(--text)",
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: "0 1 auto", maxWidth: "100%",
          }}>{s.file}</span>
          <span className="mono" style={{ font: "400 11px/1 var(--font-mono)", color: "var(--text-3)" }}>p.{s.page}</span>
        </div>
        <div className="mono" style={{ font: "400 11px/1 var(--font-mono)", color: "var(--text-3)", marginBottom: 6 }}>{s.loc}</div>
        {!compact && (
          <div style={{
            font: "400 12px/1.5 var(--font-sans)",
            color: "var(--text-2)",
            background: "var(--paper-2)",
            borderLeft: "2px solid var(--slate-3)",
            padding: "8px 10px",
            borderRadius: "0 4px 4px 0",
          }}>
            "{s.excerpt}"
          </div>
        )}
      </div>
    </div>
  );
}

function TrustSignal({ ms = 312, cache = false, model = "claude-haiku-4-5", retrievals = 4 }: {
  ms?: number;
  cache?: boolean;
  model?: string;
  retrievals?: number;
}) {
  return (
    <div className="trust">
      <span><b>{ms}ms</b></span>
      <span style={{ color: "var(--line-3)" }}>·</span>
      <span>{cache ? <b style={{ color: "var(--green)" }}>cache hit</b> : "fresh"}</span>
      <span style={{ color: "var(--line-3)" }}>·</span>
      <span><b>{retrievals}</b> retrievals</span>
      <span style={{ color: "var(--line-3)" }}>·</span>
      <span>{model}</span>
    </div>
  );
}

function UserBubble({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      display: "flex", justifyContent: "flex-end",
      margin: "0 0 16px 0",
    }}>
      <div style={{
        maxWidth: "78%",
        background: "var(--paper-2)",
        border: "1px solid var(--line)",
        borderRadius: "14px 14px 4px 14px",
        padding: "10px 14px",
        font: "400 14px/1.5 var(--font-sans)",
        color: "var(--text)",
        letterSpacing: "-0.005em",
      }}>{children}</div>
    </div>
  );
}

export { SAMPLE_SOURCES, SAMPLE_ANSWER_BODY, SAMPLE_QUESTION, SourceRow, TrustSignal, UserBubble };
