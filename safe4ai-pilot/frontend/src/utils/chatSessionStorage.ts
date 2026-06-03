const SESSION_STORAGE_PREFIX = "safe4ai:session-id:";

function storageKey(userId: string): string {
  return `${SESSION_STORAGE_PREFIX}${userId}`;
}

export function readStoredChatSessionId(userId: string | undefined): string | null {
  if (typeof window === "undefined" || !userId) return null;
  return window.localStorage.getItem(storageKey(userId));
}

export function storeChatSessionId(userId: string | undefined, sessionId: string): void {
  if (typeof window === "undefined" || !userId) return;
  window.localStorage.setItem(storageKey(userId), sessionId);
}

export function clearStoredChatSessions(): void {
  if (typeof window === "undefined") return;
  for (let i = window.localStorage.length - 1; i >= 0; i -= 1) {
    const key = window.localStorage.key(i);
    if (key?.startsWith(SESSION_STORAGE_PREFIX) || key === "safe4ai:last-session-id") {
      window.localStorage.removeItem(key);
    }
  }
}
