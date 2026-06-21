import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API + static asset paths to the FastAPI backend so the
// SPA can call same-origin paths (/api, /health, /static) without CORS.
const BACKEND = process.env.VITE_BACKEND_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
      "/health": { target: BACKEND, changeOrigin: true },
      "/static": { target: BACKEND, changeOrigin: true },
      "/metrics": { target: BACKEND, changeOrigin: true },
    },
  },
});
