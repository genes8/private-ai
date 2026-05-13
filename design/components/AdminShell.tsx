import React from "react";
import { Icon } from "./Icons";

interface AdminShellProps {
  active?: string;
  title: string;
  subtitle?: string;
  headerRight?: React.ReactNode;
  children?: React.ReactNode;
}

export function AdminShell({ active = "documents", title, subtitle, headerRight, children }: AdminShellProps) {
  const items = [
    { id: "overview",  label: "Overview",   icon: "Brain" },
    { id: "documents", label: "Documents",  icon: "Folder" },
    { id: "audit",     label: "Activity",   icon: "Activity" },
    { id: "feedback",  label: "Feedback",   icon: "Inbox" },
    { id: "users",     label: "Users",      icon: "Users" },
    { id: "settings",  label: "Settings",   icon: "Settings" },
  ];

  return (
    <div className="pa-root" style={{
      display: "grid",
      gridTemplateColumns: "212px 1fr",
      height: "100%",
      background: "var(--paper)",
    }}>
      {/* RAIL */}
      <aside style={{
        background: "var(--surface-2)",
        borderRight: "1px solid var(--line)",
        display: "flex", flexDirection: "column",
      }}>
        <div style={{ padding: "16px 14px 14px" }}>
          <div className="pa-logo" style={{ paddingLeft: 4 }}>
            <div className="mark"/>
            <span className="word">private<span className="dim">·ai</span></span>
          </div>
          <div style={{
            font: "500 10.5px/1 var(--font-mono)", letterSpacing: ".06em", textTransform: "uppercase",
            color: "var(--text-3)", marginTop: 6, paddingLeft: 30,
          }}>admin</div>
        </div>

        <div style={{ padding: "0 8px", display: "flex", flexDirection: "column", gap: 1 }}>
          {items.map(it => {
            const Ic = Icon[it.icon as keyof typeof Icon];
            const on = it.id === active;
            return (
              <div key={it.id} className={"nav-row" + (on ? " active" : "")} style={{
                ...(on ? { background: "var(--surface)", boxShadow: "0 0 0 1px var(--line)" } : {}),
              }}>
                <Ic size={14} stroke={on ? "var(--ink)" : "var(--text-3)"}/>
                <span>{it.label}</span>
                {it.id === "feedback" && <span className="chip solid-blue" style={{
                  marginLeft: "auto", height: 16, padding: "0 6px", fontSize: 10,
                }}>3</span>}
              </div>
            );
          })}
        </div>

        <div style={{ flex: 1 }}/>

        <div style={{
          margin: 12, padding: "10px 12px",
          background: "var(--paper-2)", border: "1px solid var(--line)", borderRadius: 8,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
            <span className="sdot"/>
            <span style={{ font: "500 11.5px/1 var(--font-sans)", color: "var(--ink)" }}>Indexing healthy</span>
          </div>
          <div style={{ font: "400 10.5px/1.45 var(--font-mono)", color: "var(--text-3)" }}>
            14,827 chunks · 312 docs<br/>
            queue empty · last 2m ago
          </div>
        </div>

        <div style={{
          borderTop: "1px solid var(--line)",
          padding: "10px 12px",
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <span className="avatar" style={{ background: "var(--blue)" }}>MR</span>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ font: "500 12px/1.2 var(--font-sans)", color: "var(--text)" }}>Maya Reyes</div>
            <div style={{ font: "400 10.5px/1.2 var(--font-mono)", color: "var(--text-3)" }}>Admin</div>
          </div>
        </div>
      </aside>

      {/* MAIN */}
      <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
        <header style={{
          padding: "16px 28px",
          borderBottom: "1px solid var(--line)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div>
            <div className="kicker" style={{ marginBottom: 4 }}>{active}</div>
            <h1 style={{
              font: "500 19px/1 var(--font-sans)",
              letterSpacing: "-0.012em",
              color: "var(--ink)", margin: "0 0 4px",
            }}>{title}</h1>
            {subtitle && (
              <div style={{ font: "400 12.5px/1 var(--font-sans)", color: "var(--text-2)" }}>{subtitle}</div>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>{headerRight}</div>
        </header>

        <div style={{ flex: 1, overflow: "hidden", minHeight: 0 }}>{children}</div>
      </div>
    </div>
  );
}
