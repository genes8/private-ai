import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Search,
  Plus,
  MoreHorizontal,
  Shield,
  Mail,
  X,
  UserPlus,
  ShieldCheck,
  UserX,
} from "lucide-react";
import Avatar from "../../components/Avatar";
import { apiFetch } from "../../api/client";
import { getSettings } from "../../api/settings";
import AdminLayout from "./AdminLayout";

// ── Domain ────────────────────────────────────────────────────────────────
interface User {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

type UserStatus = "active" | "inactive";
type FilterTab = "all" | UserStatus;

const listUsers = () => apiFetch<User[]>("/admin/users");
const deactivateUser = (id: string) =>
  apiFetch<void>(`/admin/users/${id}`, { method: "DELETE" });
const inviteUser = (body: { email: string; role: string; password?: string }) =>
  apiFetch<{ id: string }>("/admin/users", {
    method: "POST",
    body: JSON.stringify(body),
  });

function generateTemporaryPassword(): string {
  const lower = 'abcdefghijkmnpqrstuvwxyz';
  const upper = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
  const digits = '23456789';
  const special = '!@#$%&*';
  const all = lower + upper + digits + special;
  const array = new Uint8Array(20);
  crypto.getRandomValues(array);
  const chars = Array.from(array).map((b) => all[b % all.length]);
  // Ensure at least one of each required type at fixed positions
  const pick = (charset: string) => {
    const b = new Uint8Array(1);
    crypto.getRandomValues(b);
    return charset[b[0] % charset.length];
  };
  chars[0] = pick(upper);
  chars[1] = pick(lower);
  chars[2] = pick(digits);
  chars[3] = pick(special);
  return chars.join('');
}

// ── Helpers ───────────────────────────────────────────────────────────────
function nameFromEmail(email: string): string {
  const [local] = email.split("@");
  return local
    .split(/[._-]/)
    .map((w) => w[0]?.toUpperCase() + w.slice(1))
    .join(" ");
}

function RolePill({ role }: { role: string }) {
  const isAdmin = role === "admin";
  return (
    <span
      className={`inline-flex items-center h-[20px] px-2 rounded text-[10.5px] font-medium font-mono uppercase tracking-wider border ${
        isAdmin
          ? "bg-ink text-paper-2 border-ink"
          : "bg-surface text-text-3 border-line"
      }`}
    >
      {isAdmin && <ShieldCheck size={10} className="mr-1" />}
      {role}
    </span>
  );
}

function StatusPill({ isActive }: { isActive: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 h-[22px] px-2 rounded-full border border-line bg-surface text-[11.5px] text-text-2">
      <span className={`w-1.5 h-1.5 rounded-full ${isActive ? "bg-success" : "bg-danger"}`} />
      {isActive ? "active" : "inactive"}
    </span>
  );
}

// ── Invite modal ──────────────────────────────────────────────────────────
function InviteModal({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (body: { email: string; role: string; password: string }) => Promise<{ id: string }>;
}) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<string>("pilot_user");
  const [error, setError] = useState<string | null>(null);
  const [generatedPassword, setGeneratedPassword] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    if (!email) { setError("Email is required"); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setError("Enter a valid email address"); return; }
    setError(null);
    try {
      setSubmitting(true);
      const password = generateTemporaryPassword();
      await onSubmit({ email, role, password });
      setGeneratedPassword(password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invite failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (generatedPassword) {
    return (
      <div
        className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-sm flex items-center justify-center p-6"
        onClick={onClose}
      >
        <div
          className="bg-surface rounded-lg shadow-pop border border-line w-[480px] max-w-full"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="px-5 py-4 border-b border-line">
            <h3 className="text-[15px] font-medium text-ink tracking-tight">Invite created</h3>
            <p className="text-[12px] text-text-3 mt-1">
              Share this temporary password with the new user. It is shown only once.
            </p>
          </div>
          <div className="p-5 space-y-3">
            <div className="rounded border border-line bg-paper-2 p-3 font-mono text-[12.5px] break-all text-ink">
              {generatedPassword}
            </div>
            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="h-8 px-3 rounded bg-ink text-paper-2 text-[12.5px] font-medium hover:bg-black"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-sm flex items-center justify-center p-6"
      onClick={onClose}
    >
      <div
        className="bg-surface rounded-lg shadow-pop border border-line w-[480px] max-w-full"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-line">
          <div className="flex items-center gap-2.5">
            <UserPlus className="w-4 h-4 text-text-3" strokeWidth={1.5} />
            <h3 className="text-[15px] font-medium text-ink tracking-tight">Invite teammate</h3>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded hover:bg-surface-2 flex items-center justify-center"
          >
            <X className="w-3.5 h-3.5 text-text-3" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {error && (
            <div className="p-3 rounded bg-danger-soft text-danger text-[12.5px]">
              {error}
            </div>
          )}
          <div>
            <label className="block text-[12px] font-medium text-text-2 mb-1.5">Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 w-3.5 h-3.5 text-text-3" strokeWidth={1.5} />
              <input
                type="email"
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                className="w-full h-9 pl-9 pr-3 rounded border border-line bg-surface text-[13.5px] outline-none focus:border-accent focus:ring-2 focus:ring-accent/15"
              />
            </div>
          </div>

          <div>
            <label className="block text-[12px] font-medium text-text-2 mb-1.5">Role</label>
            <div className="grid grid-cols-2 gap-2">
              {(["pilot_user", "admin"] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => setRole(r)}
                  className={`h-9 rounded border text-[12.5px] font-medium capitalize transition-colors ${
                    role === r
                      ? "border-ink bg-paper-2 text-ink"
                      : "border-line bg-surface text-text-2 hover:bg-surface-2"
                  }`}
                >
                  {r === "pilot_user" ? "Viewer" : r}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-[11px] text-text-3 leading-relaxed">
              {role === "admin" && "Full access — users, settings, audit, all documents."}
              {role === "pilot_user" && "Can chat and rate answers. No admin access."}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-surface-2 rounded-b-lg">
          <button
            onClick={onClose}
            className="h-8 px-3 rounded border border-line bg-surface text-[12.5px] font-medium text-text hover:bg-surface-2"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!email || submitting}
            className="h-8 px-3.5 rounded bg-ink text-paper-2 text-[12.5px] font-medium disabled:opacity-40 hover:bg-black"
          >
            {submitting ? "Sending…" : "Send invite"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Deactivate modal ──────────────────────────────────────────────────────
function DeactivateModal({
  user,
  onClose,
  onConfirm,
}: {
  user: User;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-sm flex items-center justify-center p-6">
      <div className="bg-surface rounded-lg shadow-pop border border-line w-[400px] max-w-full p-6">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-full bg-danger/10 flex items-center justify-center">
            <UserX className="w-4 h-4 text-danger" />
          </div>
          <h3 className="text-[15px] font-medium text-ink">Deactivate user?</h3>
        </div>
        <p className="text-[13px] text-text-2 mb-5">
          <b>{user.email}</b> will lose workspace access immediately.
        </p>
        <div className="flex gap-2 justify-end">
          <button
            onClick={onClose}
            className="h-8 px-3 rounded border border-line bg-surface text-[12.5px] font-medium text-text hover:bg-surface-2"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="h-8 px-3.5 rounded bg-danger text-white text-[12.5px] font-medium hover:bg-danger/90"
          >
            Deactivate
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────
export default function UsersPage() {
  const [filter, setFilter] = useState<FilterTab>("all");
  const [query, setQuery] = useState("");
  const [showInvite, setShowInvite] = useState(false);
  const [confirmDeactivate, setConfirmDeactivate] = useState<User | null>(null);

  const qc = useQueryClient();
  const { data: users = [], isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: listUsers,
  });

  const { data: appSettings } = useQuery({
    queryKey: ["settings"],
    queryFn: getSettings,
    staleTime: 60_000,
  });

  const deactivate = useMutation({
    mutationFn: deactivateUser,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const invite = useMutation({
    mutationFn: inviteUser,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
    },
  });

  const filtered = users
    .filter((u) => filter === "all" || (filter === "active" ? u.is_active : !u.is_active))
    .filter(
      (u) =>
        !query ||
        u.email.toLowerCase().includes(query.toLowerCase()) ||
        nameFromEmail(u.email).toLowerCase().includes(query.toLowerCase())
    );

  const counts = {
    all: users.length,
    active: users.filter((u) => u.is_active).length,
    inactive: users.filter((u) => !u.is_active).length,
  };

  return (
    <AdminLayout>
      <div className="h-full flex flex-col bg-paper">
        {/* Header */}
        <header className="px-7 py-4 border-b border-line flex items-center justify-between">
          <div>
            <div className="text-[10.5px] font-mono uppercase tracking-[.06em] text-text-3 mb-1">users</div>
            <h1 className="text-[19px] font-medium text-ink tracking-snug">Team</h1>
            <p className="text-[12.5px] text-text-2">
              {counts.active} active · {counts.inactive} inactive
            </p>
          </div>
          <button
            onClick={() => setShowInvite(true)}
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded bg-ink text-paper-2 text-[12.5px] font-medium hover:bg-black"
          >
            <Plus className="w-3 h-3" strokeWidth={2} />
            Invite teammate
          </button>
        </header>

        {/* Toolbar */}
        <div className="px-7 py-3 border-b border-line flex items-center gap-3">
          <div className="flex items-center gap-1 bg-paper-2 rounded-md p-0.5">
            {(["all", "active", "inactive"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`h-7 px-3 rounded text-[12px] font-medium capitalize transition-colors ${
                  filter === f ? "bg-surface shadow-sm text-ink" : "text-text-2 hover:text-ink"
                }`}
              >
                {f} <span className="ml-1 font-mono text-[10.5px] text-text-3">{counts[f]}</span>
              </button>
            ))}
          </div>

          <div className="relative ml-auto">
            <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-text-3" strokeWidth={1.5} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search name or email…"
              className="h-8 w-64 pl-8 pr-3 rounded border border-line bg-surface text-[12.5px] outline-none focus:border-accent"
            />
          </div>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto">
          <div
            className="px-7 py-3 grid items-center gap-4
                       grid-cols-[minmax(0,2fr)_90px_120px_28px]
                       text-[10.5px] font-mono uppercase tracking-[.06em] text-text-3 border-b border-line"
          >
            <span>Person</span>
            <span>Role</span>
            <span>Status</span>
            <span />
          </div>

          {isLoading && (
            <div className="px-7 py-10 text-center text-[13px] text-text-3 font-mono">loading…</div>
          )}

          {filtered.map((u) => (
            <div
              key={u.id}
              className="px-7 py-3 grid items-center gap-4
                         grid-cols-[minmax(0,2fr)_90px_120px_28px]
                         border-b border-line hover:bg-surface-2 group"
            >
              <div className="flex items-center gap-3 min-w-0">
                <Avatar name={nameFromEmail(u.email)} />
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] font-medium text-text truncate">
                      {nameFromEmail(u.email)}
                    </span>
                  </div>
                  <div className="text-[11.5px] font-mono text-text-3 truncate">{u.email}</div>
                </div>
              </div>

              <div>
                <RolePill role={u.role} />
              </div>

              <div>
                <StatusPill isActive={u.is_active} />
              </div>

              <div className="flex justify-end">
                {u.is_active && u.role !== "admin" && (
                  <button
                    onClick={() => setConfirmDeactivate(u)}
                    aria-label={`Deactivate ${u.email}`}
                    title="Deactivate"
                    className="w-7 h-7 rounded hover:bg-paper-2 flex items-center justify-center"
                  >
                    <MoreHorizontal className="w-3.5 h-3.5 text-text-3" strokeWidth={1.5} />
                  </button>
                )}
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
            User changes are logged to the audit stream and retained for{" "}
            {appSettings?.security?.auditRetentionDays ?? 90} days.
          </div>
        </div>

        {showInvite && (
          <InviteModal
            onClose={() => setShowInvite(false)}
            onSubmit={(body) => invite.mutateAsync(body)}
          />
        )}

        {confirmDeactivate && (
          <DeactivateModal
            user={confirmDeactivate}
            onClose={() => setConfirmDeactivate(null)}
            onConfirm={() => {
              deactivate.mutate(confirmDeactivate.id);
              setConfirmDeactivate(null);
            }}
          />
        )}
      </div>
    </AdminLayout>
  );
}
