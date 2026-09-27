import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { frontmanPlugin } from "@frontman-ai/vite";

// The API (app/main.py) has no CORS middleware, so browser fetches must be
// same-origin: build with VITE_API_BASE= (empty) and let this proxy forward
// /api → the API. The api.ts client still defaults to http://localhost:8177
// for setups that terminate CORS elsewhere.
const API_TARGET = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8177";

export default defineConfig({
  plugins: [frontmanPlugin({ host: "api.frontman.sh" }), react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true },
    },
  },
  preview: {
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true },
    },
  },
});
