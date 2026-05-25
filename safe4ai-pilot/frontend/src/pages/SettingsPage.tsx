import { AlertCircle, ArrowLeft, CheckCircle2, KeyRound, LogOut, Shield, UserRound } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Avatar from "../components/Avatar";
import Button from "../components/Button";
import Logo from "../components/Logo";
import { ApiError } from "../api/client";
import { changePassword, getAccountSettings } from "../api/account";
import { useAuth } from "../hooks/useAuth";

function formatDate(value: string | null) {
  if (!value) return "No activity yet";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function passwordIssue(password: string, confirmPassword: string): string | null {
  if (password.length < 12) return "Use at least 12 characters.";
  if (!/[A-Z]/.test(password)) return "Add at least one uppercase letter.";
  if (!/[a-z]/.test(password)) return "Add at least one lowercase letter.";
  if (!/[0-9]/.test(password)) return "Add at least one digit.";
  if (!/[^A-Za-z0-9]/.test(password)) return "Add at least one special character.";
  if (password !== confirmPassword) return "New passwords do not match.";
  return null;
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3">
      <div className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3">{label}</div>
      <div className="mt-1 text-[20px] font-semibold tabular-nums text-ink">{value}</div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-4 last:border-b-0">
      <div className="text-[13px] font-medium text-ink">{label}</div>
      <div className="max-w-[60%] truncate text-right font-mono text-[12px] text-text-2">{value}</div>
    </div>
  );
}

export default function SettingsPage() {
  const { me, signOut } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["account-settings"],
    queryFn: getAccountSettings,
    staleTime: 30_000,
    retry: 1,
  });

  const validationError = useMemo(
    () => passwordIssue(newPassword, confirmPassword),
    [newPassword, confirmPassword],
  );
  const canSubmit =
    currentPassword.length > 0 &&
    newPassword.length > 0 &&
    confirmPassword.length > 0 &&
    validationError === null;

  const passwordMutation = useMutation({
    mutationFn: changePassword,
    onSuccess: (result) => {
      setSuccessMessage(result.message);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      queryClient.clear();
      window.setTimeout(() => {
        navigate("/login", { replace: true });
      }, 1400);
    },
  });

  function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || passwordMutation.isPending) return;
    passwordMutation.mutate({ currentPassword, newPassword });
  }

  const knowledgeStatus = data?.knowledgeBase.failedCount
    ? "Needs admin attention"
    : data?.knowledgeBase.inProgressCount
    ? "Indexing"
    : "Healthy";

  return (
    <div className="flex h-screen flex-col bg-paper">
      <header className="flex items-center justify-between border-b border-line bg-surface px-5 py-3">
        <div className="flex items-center gap-3">
          <Logo size={22} />
          <span className="text-[13.5px] font-medium tracking-tight text-ink">private·ai</span>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/chat">
            <Button variant="ghost" size="sm" iconLeft={<ArrowLeft size={13} />}>Chat</Button>
          </Link>
          <Avatar name={me?.email ?? "U"} size={26} />
          <button
            type="button"
            onClick={signOut}
            aria-label="Sign out"
            className="text-text-mute transition-colors hover:text-text-2"
            title="Sign out"
          >
            <LogOut size={14} />
          </button>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-6 py-8">
          <div className="mb-8">
            <div className="mb-1.5 font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3">account</div>
            <h1 className="font-serif text-[30px] italic tracking-tight text-ink">Settings</h1>
            <p className="mt-1.5 max-w-[62ch] text-[13.5px] leading-relaxed text-text-2">
              Manage your account password and review your recent private·ai usage.
            </p>
          </div>

          {isLoading && (
            <div className="rounded-lg border border-line bg-surface px-5 py-8 text-center text-[13px] text-text-mute">
              Loading settings...
            </div>
          )}

          {isError && (
            <div className="rounded-lg border border-danger/20 bg-danger-soft px-5 py-4 text-[13px] text-danger">
              <div className="mb-3 flex items-center gap-2">
                <AlertCircle size={16} />
                <span>{error instanceof Error ? error.message : "Failed to load settings."}</span>
              </div>
              <Button variant="danger" size="sm" onClick={() => void refetch()}>Retry</Button>
            </div>
          )}

          {data && (
            <div className="space-y-8">
              <section>
                <div className="mb-4 flex items-center gap-2">
                  <UserRound size={16} className="text-text-3" />
                  <h2 className="font-serif text-[20px] italic text-ink">Account</h2>
                </div>
                <div className="overflow-hidden rounded-lg border border-line bg-surface">
                  <Field label="Email" value={data.profile.email} />
                  <Field label="Role" value={data.profile.role} />
                  <Field label="Status" value={data.profile.isActive ? "Active" : "Inactive"} />
                  <Field label="Created" value={formatDate(data.profile.createdAt)} />
                </div>
              </section>

              <section>
                <div className="mb-4 flex items-center gap-2">
                  <Shield size={16} className="text-text-3" />
                  <h2 className="font-serif text-[20px] italic text-ink">Security</h2>
                </div>
                <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
                  <div className="overflow-hidden rounded-lg border border-line bg-surface">
                    <Field label="Session lifetime" value={`${data.security.sessionHours} hours`} />
                    <Field label="Password login" value={data.security.ssoOnly ? "Disabled by SSO" : "Enabled"} />
                    <Field label="Password changes" value={data.security.passwordChangeAllowed ? "Allowed" : "Disabled"} />
                  </div>

                  <form onSubmit={submitPassword} className="rounded-lg border border-line bg-surface p-5">
                    <div className="mb-4 flex items-center gap-2">
                      <KeyRound size={15} className="text-text-3" />
                      <div className="text-[13.5px] font-medium text-ink">Change password</div>
                    </div>
                    <div className="space-y-3">
                      <input
                        type="password"
                        value={currentPassword}
                        onChange={(event) => setCurrentPassword(event.target.value)}
                        placeholder="Current password"
                        disabled={!data.security.passwordChangeAllowed}
                        className="h-9 w-full rounded border border-line bg-surface px-3 font-mono text-[12.5px] outline-none focus:border-accent disabled:opacity-50"
                      />
                      <input
                        type="password"
                        value={newPassword}
                        onChange={(event) => setNewPassword(event.target.value)}
                        placeholder="New password"
                        disabled={!data.security.passwordChangeAllowed}
                        className="h-9 w-full rounded border border-line bg-surface px-3 font-mono text-[12.5px] outline-none focus:border-accent disabled:opacity-50"
                      />
                      <input
                        type="password"
                        value={confirmPassword}
                        onChange={(event) => setConfirmPassword(event.target.value)}
                        placeholder="Confirm new password"
                        disabled={!data.security.passwordChangeAllowed}
                        className="h-9 w-full rounded border border-line bg-surface px-3 font-mono text-[12.5px] outline-none focus:border-accent disabled:opacity-50"
                      />
                    </div>

                    {newPassword && confirmPassword && validationError && (
                      <p className="mt-3 text-[12px] text-danger">{validationError}</p>
                    )}
                    {passwordMutation.error && (
                      <p className="mt-3 text-[12px] text-danger">
                        {passwordMutation.error instanceof ApiError
                          ? passwordMutation.error.message
                          : "Password change failed."}
                      </p>
                    )}
                    {successMessage && (
                      <p className="mt-3 flex items-center gap-2 text-[12px] text-success">
                        <CheckCircle2 size={14} />
                        {successMessage}
                      </p>
                    )}

                    <div className="mt-4">
                      <Button
                        type="submit"
                        variant="primary"
                        size="md"
                        loading={passwordMutation.isPending}
                        disabled={!canSubmit || !data.security.passwordChangeAllowed}
                      >
                        Change password
                      </Button>
                    </div>
                  </form>
                </div>
              </section>

              <section>
                <h2 className="mb-4 font-serif text-[20px] italic text-ink">Usage</h2>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  <StatTile label="Questions 7d" value={data.usage.questions7d} />
                  <StatTile label="Questions 30d" value={data.usage.questions30d} />
                  <StatTile label="Thumbs up" value={data.usage.feedbackPositive} />
                  <StatTile label="Thumbs down" value={data.usage.feedbackNegative} />
                  <StatTile label="Last activity" value={formatDate(data.usage.lastActivityAt)} />
                </div>
              </section>

              <section>
                <h2 className="mb-4 font-serif text-[20px] italic text-ink">Knowledge base</h2>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  <StatTile label="Status" value={knowledgeStatus} />
                  <StatTile label="Documents" value={data.knowledgeBase.docCount} />
                  <StatTile label="Chunks" value={data.knowledgeBase.chunkCount} />
                  <StatTile label="Failed" value={data.knowledgeBase.failedCount} />
                  <StatTile label="Indexing" value={data.knowledgeBase.inProgressCount} />
                </div>
              </section>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
