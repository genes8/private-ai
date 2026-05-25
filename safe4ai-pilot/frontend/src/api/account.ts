import { apiFetch } from "./client";

export interface AccountSettings {
  profile: {
    id: string;
    email: string;
    role: "admin" | "pilot_user";
    isActive: boolean;
    createdAt: string | null;
  };
  security: {
    sessionHours: number;
    ssoOnly: boolean;
    passwordChangeAllowed: boolean;
  };
  usage: {
    questions7d: number;
    questions30d: number;
    lastActivityAt: string | null;
    feedbackPositive: number;
    feedbackNegative: number;
  };
  knowledgeBase: {
    docCount: number;
    chunkCount: number;
    failedCount: number;
    inProgressCount: number;
  };
}

export interface ChangePasswordRequest {
  currentPassword: string;
  newPassword: string;
}

export const getAccountSettings = () =>
  apiFetch<AccountSettings>("/account/settings");

export const changePassword = (body: ChangePasswordRequest) =>
  apiFetch<{ message: string }>("/account/change-password", {
    method: "POST",
    body: JSON.stringify(body),
  });
