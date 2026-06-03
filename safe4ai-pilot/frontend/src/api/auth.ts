import { apiFetch, apiUrl } from "./client";

export interface Me {
  id: string;
  email: string;
  role: "admin" | "pilot_user";
  is_active: boolean;
}

export interface SsoStatus {
  enabled: boolean;
  configured: boolean;
  ssoOnly: boolean;
  loginUrl: string | null;
}

const fetchCsrf = () =>
  apiFetch<{ csrf_token: string }>("/auth/csrf");

export const login = async (email: string, password: string) => {
  await fetchCsrf();
  return apiFetch<void>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
};

export const getSsoStatus = () => apiFetch<SsoStatus>("/auth/sso/status");

export const ssoStartUrl = () => apiUrl("/auth/sso/start");

export const logout = () =>
  apiFetch<void>("/auth/logout", { method: "POST" });

export const getMe = () => apiFetch<Me>("/me");
