// private-ai · Users page
// Drop into src/pages/admin/UsersPage.tsx
//
// Tailwind classes assume the config from handoff/tailwind.config.ts.
// Lucide icons. React Query hooks are sketched but you'll wire the real
// endpoints (GET/POST/DELETE /users) yourself.

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Search, Plus, MoreHorizontal, Shield, Mail, X, Check,
  UserPlus, ChevronDown,
} from "lucide-react";

// ── Domain ────────────────────────────────────────────────────────────────
export type UserRole = "admin" | "editor" | "viewer";
export type UserStatus = "active" | "invited" | "deactivated";

export interface AppUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  scope: string[];              // document folders the user can query
  lastSeen: string | null;      // ISO
  invitedBy?: string;
  queries30d: number;
}

// ── API stubs (replace with your client) ──────────────────────────────────
async function listUsers(): Promise<AppUser[]> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/users`, { credentials: "include" });
  if (!r.ok) throw new Error("failed to load users");
  return r.json();
}
async function inviteUser(body: { email: string; role: UserRole; scope: string[] }) {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/users`, {
    method: "POST", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error("invite failed");
  return r.json() as Promise<AppUser>;
}
async function setUserStatus(id: string, status: UserStatus) {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/users/${id}`, {
    method: "PATCH", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!r.ok) throw new Error("update failed");
}

// ── Atoms ─────────────────────────────────────────────────────────────────
function Avatar({ name, color = "bg-ink" }: { name: string; color?: string }) {
  const initials = name.split(" ").map(p => p[0]).slice(0, 2).join("").toUpperCase();
  return (
    <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full ${color} text-paper-2 text-[10.5px] font-semibold`}>
      {initials}
    </span>
  );
}

function StatusPill({ status }: { status: UserStatus }) {
  const map = {
    active:      { dot: "bg-success",  text: "Active" },
    invited:     { dot: "bg-accent",   text: "Invited" },
    deactivated: { dot: "bg-slate-2",  text: "Deactivated" },
  }[status];
  return (
    <span className="inline-flex items-center gap-1.5 h-[22px] px-2 rounded-full border border-line bg-surface text-[11.5px] text-text-2">
      <span className={`w-1.5 h-1.5 rounded-full ${map.dot}`} />
      {map.text}
    </span>
  );
}

function RolePill({ role }: { role: UserRole }) {
  const styles: Record<UserRole, string> = {
    admin:  "bg-ink text-paper-2 border-ink",
    editor: "bg-paper-2 text-text border-line",
    viewer: "bg-surface text-text-3 border-line",
  };
  return (
    <span className={`inline-flex items-center h-[20px] px-2 rounded text-[10.5px] font-medium font-mono uppercase tracking-wider border ${styles[role]}`}>
      {role}
    </span>
  );
}

// ── Invite modal ──────────────────────────────────────────────────────────
function InviteModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<UserRole>("viewer");
  const [scope, setScope] = useState<string[]>(["Legal"]);

  const invite = useMutation({
    mutationFn: inviteUser,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["users"] }); onClose(); },
  });

  const allScopes = ["Legal", "Procurement", "Compliance", "Engineering", "Finance", "People"];

  return (
    <div className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-sm flex items-center justify-center p-6"
         onClick={onClose}>
      <div className="bg-surface rounded-lg shadow-pop border border-line w-[480px] max-w-full"
           onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-line">
          <div className="flex items-center gap-2.5">
            <UserPlus className="w-4 h-4 text-text-3" strokeWidth={1.5} />
            <h3 className="text-[15px] font-medium text-ink tracking-tight">Invite teammate</h3>
          </div>
          <button onClick={onClose} className="w-7 h-7 rounded hover:bg-surface-2 flex items-center justify-center">
            <X className="w-3.5 h-3.5 text-text-3" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div>
            <label className="block text-[12px] font-medium text-text-2 mb-1.5">Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 w-3.5 h-3.5 text-text-3" strokeWidth={1.5} />
              <input
                type="email" autoFocus
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="name@safe4ai.com"
                className="w-full h-9 pl-9 pr-3 rounded border border-line bg-surface text-[13.5px] outline-none focus:border-accent focus:ring-2 focus:ring-accent/15"
              />
            </div>
            <p className="mt-1.5 text-[11px] font-mono text-text-3">
              Domain must match the configured allow-list (safe4ai.com).
            </p>
          </div>

          <div>
            <label className="block text-[12px] font-medium text-text-2 mb-1.5">Role</label>
            <div className="grid grid-cols-3 gap-2">
              {(["viewer", "editor", "admin"] as UserRole[]).map(r => (
                <button
                  key={r}
                  onClick={() => setRole(r)}
                  className={`h-9 rounded border text-[12.5px] font-medium capitalize transition-colors
                    ${role === r
                      ? "border-ink bg-paper-2 text-ink"
                      : "border-line bg-surface text-text-2 hover:bg-surface-2"}`}
                >
                  {r}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-[11px] text-text-3 leading-relaxed">
              {role === "admin"  && "Full access — users, settings, audit, all documents."}
              {role === "editor" && "Can upload, reindex and delete documents in their scope."}
              {role === "viewer" && "Can chat and rate answers within their scope. No admin."}
            </p>
          </div>

          <div>
            <label className="block text-[12px] font-medium text-text-2 mb-1.5">Document scope</label>
            <div className="flex flex-wrap gap-1.5">
              {allScopes.map(s => {
                const on = scope.includes(s);
                return (
                  <button
                    key={s}
                    onClick={() => setScope(on ? scope.filter(x => x !== s) : [...scope, s])}
                    className={`inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full text-[11.5px] border transition-colors
                      ${on
                        ? "bg-accent-soft border-transparent text-accent-2"
                        : "bg-surface border-line text-text-2 hover:bg-surface-2"}`}
                  >
                    {on && <Check className="w-3 h-3" strokeWidth={2} />}
                    {s}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-surface-2 rounded-b-lg">
          <button onClick={onClose}
            className="h-8 px-3 rounded border border-line bg-surface text-[12.5px] font-medium text-text hover:bg-surface-2">
            Cancel
          </button>
          <button
            onClick={() => invite.mutate({ email, role, scope })}
            disabled={!email || invite.isPending}
            className="h-8 px-3.5 rounded bg-ink text-paper-2 text-[12.5px] font-medium disabled:opacity-40 hover:bg-black">
            {invite.isPending ? "Sending…" : "Send invite"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────
export default function UsersPage() {
  const [filter, setFilter] = useState<"all" | UserStatus>("all");
  const [query, setQuery] = useState("");
  const [showInvite, setShowInvite] = useState(false);

  const { data: users = [], isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: listUsers,
  });

  const qc = useQueryClient();
  const toggle = useMutation({
    mutationFn: ({ id, status }: { id: string; status: UserStatus }) => setUserStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const filtered = users
    .filter(u => filter === "all" || u.status === filter)
    .filter(u =>
      !query ||
      u.name.toLowerCase().includes(query.toLowerCase()) ||
      u.email.toLowerCase().includes(query.toLowerCase())
    );

  const counts = {
    all: users.length,
    active: users.filter(u => u.status === "active").length,
    invited: users.filter(u => u.status === "invited").length,
    deactivated: users.filter(u => u.status === "deactivated").length,
  };

  return (
    <div className="h-full flex flex-col bg-paper">
      {/* Header */}
      <header className="px-7 py-4 border-b border-line flex items-center justify-between">
        <div>
          <div className="text-[10.5px] font-mono uppercase tracking-[.06em] text-text-3 mb-1">users</div>
          <h1 className="text-[19px] font-medium text-ink tracking-snug">Team</h1>
          <p className="text-[12.5px] text-text-2">
            {counts.active} active · {counts.invited} pending invite · last admin login 2h ago
          </p>
        </div>
        <button
          onClick={() => setShowInvite(true)}
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded bg-ink text-paper-2 text-[12.5px] font-medium hover:bg-black">
          <Plus className="w-3 h-3" strokeWidth={2} />
          Invite teammate
        </button>
      </header>

      {/* Toolbar */}
      <div className="px-7 py-3 border-b border-line flex items-center gap-3">
        <div className="flex items-center gap-1 bg-paper-2 rounded-md p-0.5">
          {(["all", "active", "invited", "deactivated"] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`h-7 px-3 rounded text-[12px] font-medium capitalize transition-colors
                ${filter === f ? "bg-surface shadow-sm text-ink" : "text-text-2 hover:text-ink"}`}>
              {f} <span className="ml-1 font-mono text-[10.5px] text-text-3">{counts[f]}</span>
            </button>
          ))}
        </div>

        <div className="relative ml-auto">
          <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-text-3" strokeWidth={1.5} />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search name or email…"
            className="h-8 w-64 pl-8 pr-3 rounded border border-line bg-surface text-[12.5px] outline-none focus:border-accent" />
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <div className="px-7 py-3 grid items-center gap-4
                        grid-cols-[minmax(0,2fr)_90px_140px_120px_100px_28px]
                        text-[10.5px] font-mono uppercase tracking-[.06em] text-text-3 border-b border-line">
          <span>Person</span>
          <span>Role</span>
          <span>Scope</span>
          <span>Last seen</span>
          <span className="text-right">30-day queries</span>
          <span />
        </div>

        {isLoading && (
          <div className="px-7 py-10 text-center text-[13px] text-text-3 font-mono">loading…</div>
        )}

        {filtered.map(u => (
          <div
            key={u.id}
            className="px-7 py-3 grid items-center gap-4
                       grid-cols-[minmax(0,2fr)_90px_140px_120px_100px_28px]
                       border-b border-line hover:bg-surface-2 group">
            <div className="flex items-center gap-3 min-w-0">
              <Avatar
                name={u.name}
                color={u.role === "admin" ? "bg-ink" : u.role === "editor" ? "bg-accent" : "bg-slate"} />
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-medium text-text truncate">{u.name}</span>
                  <StatusPill status={u.status} />
                </div>
                <div className="text-[11.5px] font-mono text-text-3 truncate">{u.email}</div>
              </div>
            </div>

            <div><RolePill role={u.role} /></div>

            <div className="text-[12px] text-text-2 truncate">
              {u.scope.length === 0
                ? <span className="text-text-3 italic">no scope</span>
                : u.scope.slice(0, 2).join(", ") + (u.scope.length > 2 ? ` +${u.scope.length - 2}` : "")}
            </div>

            <div className="text-[11.5px] font-mono text-text-3">
              {u.lastSeen ? new Date(u.lastSeen).toLocaleDateString() : "—"}
            </div>

            <div className="text-right font-mono text-[12px] tabular-nums text-text">
              {u.queries30d.toLocaleString()}
            </div>

            <div className="flex justify-end opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() =>
                  toggle.mutate({ id: u.id, status: u.status === "active" ? "deactivated" : "active" })
                }
                title={u.status === "active" ? "Deactivate" : "Reactivate"}
                className="w-7 h-7 rounded hover:bg-paper-2 flex items-center justify-center">
                <MoreHorizontal className="w-3.5 h-3.5 text-text-3" strokeWidth={1.5} />
              </button>
            </div>
          </div>
        ))}

        {!isLoading && filtered.length === 0 && (
          <div className="px-7 py-12 text-center">
            <div className="text-[14px] text-text mb-1">No matches</div>
            <div className="text-[12px] text-text-3">Try a different filter or search.</div>
          </div>
        )}

        {/* Audit footer */}
        <div className="px-7 py-4 flex items-center gap-2 text-[11px] font-mono text-text-3 border-t border-line">
          <Shield className="w-3 h-3" strokeWidth={1.5} />
          User changes are logged to the audit stream and retained for 365 days.
        </div>
      </div>

      {showInvite && <InviteModal onClose={() => setShowInvite(false)} />}
    </div>
  );
}
