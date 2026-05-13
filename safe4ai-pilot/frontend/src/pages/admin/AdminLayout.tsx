import { Activity, BarChart2, FileText, LogOut, MessageSquare, Settings, Users } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Avatar from "../../components/Avatar";
import Logo from "../../components/Logo";
import { useAuth } from "../../hooks/useAuth";
import { listFeedback } from "../../api/feedback";

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
  const { data: feedbackItems = [] } = useQuery({
    queryKey: ["feedback"],
    queryFn: listFeedback,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  const negativeFeedbackCount = feedbackItems.filter((i) => i.rating === "down").length;

  const active = (NAV.find((n) => pathname.startsWith(n.to))?.id ?? "overview") as AdminRoute;

  return (
    <div className="flex h-screen bg-paper">
      {/* Sidebar */}
      <nav className="w-52 shrink-0 flex flex-col border-r border-line bg-surface-2">
        <div className="px-4 py-4 border-b border-line">
          <div className="flex items-center gap-2.5">
            <Logo size={20} />
            <span className="font-medium text-[13px] text-ink tracking-tight">private·ai</span>
          </div>
          <p className="font-mono text-[10.5px] uppercase text-text-mute mt-1" style={{ paddingLeft: 30, letterSpacing: "0.06em" }}>
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
        </div>

        {/* Index health card */}
        <div className="mx-2 mb-3 rounded-lg bg-paper-2 border border-line px-3 py-2.5">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-1.5 h-1.5 rounded-full bg-success shrink-0" />
            <span className="text-[11.5px] font-medium text-text-2">Indexing healthy</span>
          </div>
          <p className="text-[10.5px] text-text-mute">All documents indexed</p>
        </div>

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
