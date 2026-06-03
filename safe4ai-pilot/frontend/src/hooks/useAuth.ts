import { useCallback, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getMe, logout } from "../api/auth";
import { onUnauthorized } from "../api/authEvents";
import { clearStoredChatSessions } from "../utils/chatSessionStorage";

export function useAuth() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data: me, isLoading, isError } = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    retry: false,
  });

  const signOut = useCallback(async () => {
    await logout().catch(() => null);
    clearStoredChatSessions();
    qc.clear();
    navigate("/login", { replace: true });
  }, [navigate, qc]);

  useEffect(() => {
    return onUnauthorized(() => {
      void signOut();
    });
  }, [signOut]);

  return {
    me,
    isLoading,
    isAuthenticated: !isError && !!me,
    isAdmin: me?.role === "admin",
    signOut,
  };
}
