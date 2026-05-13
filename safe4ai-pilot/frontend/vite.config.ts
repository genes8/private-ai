import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API_URL = process.env.VITE_API_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/auth": { target: API_URL, changeOrigin: true },
      "/me":    { target: API_URL, changeOrigin: true },
      "/feedback": { target: API_URL, changeOrigin: true },
      "/chat/stream": { target: API_URL, changeOrigin: true },
      "/admin/documents": { target: API_URL, changeOrigin: true },
      "/admin/users":     { target: API_URL, changeOrigin: true },
      "/admin/feedback":  { target: API_URL, changeOrigin: true },
      "/admin/audit":     { target: API_URL, changeOrigin: true },
      "/admin/stats":     { target: API_URL, changeOrigin: true },
      "/admin/review-queue": { target: API_URL, changeOrigin: true },
      "/settings": { target: API_URL, changeOrigin: true },
    },
  },
});
