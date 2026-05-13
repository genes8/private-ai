import React from "react";
import { Icon } from "./Icons";

export function Login() {
  return (
    <div className="pa-root" style={{ display: "grid", gridTemplateColumns: "1fr 1.05fr", height: "100%" }}>
      {/* LEFT — dark security panel */}
      <div style={{
        background: "var(--ink)",
        color: "#e8e6e0",
        position: "relative",
        padding: 40,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        overflow: "hidden",
      }}>
        {/* faint grid */}
        <div aria-hidden style={{
          position: "absolute", inset: 0,
          backgroundImage: "linear-gradient(rgba(255,255,255,.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.03) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
          maskImage: "radial-gradient(ellipse at 60% 40%, #000 0%, transparent 75%)",
        }}/>
        {/* subtle accent ring */}
        <div aria-hidden style={{
          position: "absolute",
          right: -120, top: -120,
          width: 460, height: 460,
          borderRadius: "50%",
          border: "1px solid rgba(244,241,234,.07)",
          boxShadow: "inset 0 0 0 80px rgba(244,241,234,.025)",
        }}/>
        <div aria-hidden style={{
          position: "absolute",
          right: 60, top: 80,
          width: 220, height: 220,
          borderRadius: "50%",
          border: "1px solid rgba(59,108,242,.18)",
        }}/>

        <div className="pa-logo" style={{ position: "relative" }}>
          <div className="mark" style={{ background: "#f4f1ea" }}/>
          <span className="word" style={{ color: "#f4f1ea" }}>private<span className="dim" style={{ color: "rgba(244,241,234,.5)" }}>·ai</span></span>
        </div>

        <div style={{ position: "relative", maxWidth: 380 }}>
          <div className="kicker" style={{ color: "rgba(244,241,234,.45)", marginBottom: 16 }}>internal · pilot · v0.4</div>
          <h2 style={{
            font: "400 36px/1.05 var(--font-serif)",
            fontStyle: "italic",
            margin: "0 0 16px 0",
            letterSpacing: "-0.015em",
            color: "#f4f1ea",
          }}>
            Answers grounded in <span style={{ color: "#7aa2f7" }}>your</span> documents.
            Nothing else.
          </h2>
          <p style={{ font: "400 13.5px/1.55 var(--font-sans)", color: "rgba(244,241,234,.62)", textWrap: "pretty" }}>
            Every retrieval is logged. Every answer is cited. Indexed corpus, model
            calls and feedback never leave your tenancy.
          </p>
        </div>

        <div style={{ position: "relative", display: "flex", gap: 18, color: "rgba(244,241,234,.42)", font: "400 11px/1 var(--font-mono)" }}>
          <span><Icon.Lock size={11} stroke="rgba(244,241,234,.5)" style={{ marginRight: 6 }}/>SOC 2 Type II</span>
          <span style={{ color: "rgba(244,241,234,.2)" }}>·</span>
          <span>Region: eu-west-1</span>
          <span style={{ color: "rgba(244,241,234,.2)" }}>·</span>
          <span>Build 0.4.18</span>
        </div>
      </div>

      {/* RIGHT — sign-in */}
      <div style={{
        background: "var(--paper)",
        padding: "60px 64px",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <div style={{ width: "100%", maxWidth: 360 }}>
          <div className="kicker" style={{ marginBottom: 12 }}>sign in</div>
          <h1 style={{
            font: "500 28px/1.1 var(--font-sans)",
            letterSpacing: "-0.02em",
            margin: "0 0 6px 0",
            color: "var(--ink)",
          }}>Welcome back.</h1>
          <p style={{ font: "400 13.5px/1.5 var(--font-sans)", color: "var(--text-2)", margin: "0 0 28px 0" }}>
            Use your safe4ai workspace credentials.
          </p>

          {/* SSO */}
          <button className="btn lg" style={{ width: "100%", justifyContent: "flex-start", paddingLeft: 14, fontWeight: 500 }}>
            <span style={{
              width: 16, height: 16, borderRadius: 4, background: "var(--ink)", color: "#f4f1ea",
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              font: "600 9px/1 var(--font-mono)", marginRight: 8,
            }}>SAML</span>
            Continue with safe4ai SSO
          </button>

          <div style={{
            display: "flex", alignItems: "center", gap: 12, margin: "20px 0",
            font: "400 11px/1 var(--font-mono)", color: "var(--text-3)",
          }}>
            <span style={{ flex: 1, height: 1, background: "var(--line)" }}/>
            or with credentials
            <span style={{ flex: 1, height: 1, background: "var(--line)" }}/>
          </div>

          {/* Form */}
          <label className="field-lbl">Email</label>
          <input className="field" defaultValue="alex.bremer@safe4ai.com" style={{ marginBottom: 14 }}/>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
            <label className="field-lbl" style={{ marginBottom: 0 }}>Password</label>
            <a style={{ font: "500 11.5px/1 var(--font-sans)", color: "var(--text-3)", textDecoration: "none" }}>Forgot?</a>
          </div>
          <input type="password" className="field" defaultValue="••••••••••••" style={{ marginBottom: 18 }}/>

          <button className="btn primary lg" style={{ width: "100%" }}>
            Sign in
            <Icon.ChevR size={14} stroke="#f4f1ea" style={{ marginLeft: 4 }}/>
          </button>

          <div style={{
            display: "flex", alignItems: "center", gap: 6,
            font: "400 11.5px/1 var(--font-mono)", color: "var(--text-3)",
            marginTop: 24, justifyContent: "center",
          }}>
            <span className="sdot" style={{ background: "var(--green)" }}/>
            All systems operational
            <span style={{ color: "var(--text-mute)" }}>· status.safe4ai.com</span>
          </div>
        </div>
      </div>
    </div>
  );
}
