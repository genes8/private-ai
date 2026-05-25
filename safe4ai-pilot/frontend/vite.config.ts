import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import type { IncomingMessage } from "node:http";

const API_URL = process.env.VITE_API_URL || "http://localhost:8000";

// Browser navigation sends Accept: text/html — let Vite serve index.html instead of proxying.
// fetch/XHR API calls don't include text/html, so they still reach the backend.
function spaBypass(req: IncomingMessage): string | null | undefined {
  const accept = req.headers["accept"] ?? "";
  if (accept.includes("text/html")) return req.url;
  return null;
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/auth":    { target: API_URL, changeOrigin: true },
      "/me":      { target: API_URL, changeOrigin: true },
      "/account": { target: API_URL, changeOrigin: true },
      "/feedback": { target: API_URL, changeOrigin: true },
      "/chat/stream": { target: API_URL, changeOrigin: true },
      "/admin/documents": { target: API_URL, changeOrigin: true, bypass: spaBypass },
      "/admin/users":     { target: API_URL, changeOrigin: true, bypass: spaBypass },
      "/admin/feedback":  { target: API_URL, changeOrigin: true, bypass: spaBypass },
      "/admin/audit":     { target: API_URL, changeOrigin: true, bypass: spaBypass },
      "/admin/stats":     { target: API_URL, changeOrigin: true, bypass: spaBypass },
      "/admin/review-queue": { target: API_URL, changeOrigin: true, bypass: spaBypass },
      "/settings": { target: API_URL, changeOrigin: true, bypass: spaBypass },
    },
  },
});
