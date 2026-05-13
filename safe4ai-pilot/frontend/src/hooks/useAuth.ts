import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getMe, logout } from "../api/auth";
import { onUnauthorized } from "../api/authEvents";

export function useAuth() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data: me, isLoading, isError } = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    retry: false,
  });

  async function signOut() {
    await logout().catch(() => null);
    qc.clear();
    navigate("/login", { replace: true });
  }

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
