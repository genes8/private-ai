import { Activity, ArrowLeft, BarChart2, FileText, LogOut, MessageSquare, Settings, Users } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Avatar from "../../components/Avatar";
import Logo from "../../components/Logo";
import { useAuth } from "../../hooks/useAuth";
import { apiFetch } from "../../api/client";

type AdminRoute = "overview" | "documents" | "audit" | "feedback" | "users" | "settings";

const NAV: { id: AdminRoute; label: string; to: string; icon: ReactNode }[] = [
  { id: "overview",   label: "Overview",   to: "/admin/overview",   icon: <BarChart2 size={15} /> },
  { id: "documents",  label: "Documents",  to: "/admin/documents",  icon: <FileText size={15} /> },
  { id: "audit",      label: "Activity",   to: "/admin/audit",      icon: <Activity size={15} /> },
  { id: "feedback",   label: "Feedback",   to: "/admin/feedback",   icon: <MessageSquare size={15} /> },
  { id: "users",      label: "Users",      to: "/admin/users",      icon: <Users size={15} /> },
  { id: "settings",   label: "Settings",   to: "/admin/settings",   icon: <Settings size={15} /> },
];

interface Props {
  children: ReactNode;
}

export default function AdminLayout({ children }: Props) {
  const { me, signOut } = useAuth();
  const { pathname } = useLocation();
  const { data: feedbackCount } = useQuery({
    queryKey: ["feedback-count"],
    queryFn: () => apiFetch<{ negative: number }>("/admin/feedback/count"),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  const negativeFeedbackCount = feedbackCount?.negative ?? 0;

  const { data: corpusHealth } = useQuery({
    queryKey: ["corpus-stats"],
    queryFn: () => apiFetch<{ docCount: number; chunkCount: number; failedCount: number; inProgressCount: number }>("/admin/corpus-stats"),
    refetchInterval: 30_000,
    staleTime: 20_000,
  });

  const active = (NAV.find((n) => pathname.startsWith(n.to))?.id ?? "overview") as AdminRoute;

  return (
    <div className="flex h-screen bg-paper">
      {/* Sidebar */}
      <nav className="w-52 shrink-0 flex flex-col border-r border-line bg-surface-2">
        <div className="p-4 border-b border-line">
          <div className="flex items-center gap-2.5">
            <Logo size={20} />
            <span className="font-medium text-[13px] text-ink tracking-tight">private·ai</span>
          </div>
          <p className="font-mono text-[10.5px] uppercase tracking-kicker text-text-mute mt-1" style={{ paddingLeft: 30 }}>
            admin
          </p>
        </div>

        <div className="flex-1 py-3 space-y-0.5 px-2">
          {NAV.map((n) => (
            <Link
              key={n.id}
              to={n.to}
              className={[
                "flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] transition-colors",
                active === n.id
                  ? "bg-surface shadow-[0_0_0_1px_#e7e3d8] text-text font-medium"
                  : "text-text-2 hover:bg-surface",
              ].join(" ")}
            >
              {n.icon}
              {n.label}
              {n.id === "feedback" && negativeFeedbackCount > 0 && (
                <span className="ml-auto rounded-full bg-[#eaf0ff] text-[#1d3fa6] text-[10px] font-mono px-1.5 leading-[18px]">
                  {negativeFeedbackCount}
                </span>
              )}
            </Link>
          ))}

          <div className="pt-2 mt-2 border-t border-line">
            <Link
              to="/chat"
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-[12.5px] text-text-mute hover:bg-surface hover:text-text-2 transition-colors"
            >
              <ArrowLeft size={13} />
              Back to chat
            </Link>
          </div>
        </div>

        {/* Index health card */}
        {(() => {
          const failed = corpusHealth?.failedCount ?? 0;
          const inProgress = corpusHealth?.inProgressCount ?? 0;
          const isError = failed > 0;
          const isPending = !isError && inProgress > 0;
          const dotClass = isError ? "bg-danger" : isPending ? "bg-accent animate-pulse" : "bg-success";
          const label = isError
            ? `${failed} doc${failed !== 1 ? "s" : ""} failed`
            : isPending
            ? `${inProgress} indexing…`
            : "Indexing healthy";
          const detail = isError
            ? "Check Documents tab for details"
            : isPending
            ? "Processing in background"
            : "All documents indexed";
          return (
            <div className="mx-2 mb-3 rounded-lg bg-paper-2 border border-line px-3 py-2.5">
              <div className="flex items-center gap-2 mb-1">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotClass}`} />
                <span className="text-[11.5px] font-medium text-text-2">{label}</span>
              </div>
              <p className="text-[10.5px] text-text-mute">{detail}</p>
            </div>
          );
        })()}

        <div className="border-t border-line px-4 py-3 flex items-center gap-2.5">
          <Avatar name={me?.email ?? "U"} size={24} />
          <div className="min-w-0 flex-1">
            <p className="text-[11px] text-text-mute truncate">{me?.email}</p>
          </div>
          <button
            type="button"
            onClick={signOut}
            aria-label="Sign out"
            className="text-text-mute hover:text-text-2 transition-colors shrink-0"
            title="Sign out"
          >
            <LogOut size={13} />
          </button>
        </div>
      </nav>

      {/* Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {children}
      </div>
    </div>
  );
}
