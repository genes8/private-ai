import { apiFetch } from "./client";

export interface Me {
  id: string;
  email: string;
  role: "admin" | "pilot_user";
  is_active: boolean;
}

export const login = (email: string, password: string) =>
  apiFetch<void>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });

export const logout = () =>
  apiFetch<void>("/auth/logout", { method: "POST" });

export const getMe = () => apiFetch<Me>("/me");
