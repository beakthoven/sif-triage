/* Vite config for the analytics selfcheck harness (dev-only; the repo build
 * never uses this). Runs on 8188 — 8187 turned out to be taken by a sibling
 * process (verified via ss); the live demo stack stays on 8177 and the stale
 * foreign port 8183 is avoided. /api GETs are proxied to 8177. */

import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const here = path.dirname(fileURLToPath(import.meta.url));
/** Root stays at the dashboard package root (selfcheck → analytics →
 * features → src → dashboard = four levels up) so Tailwind's automatic
 * content detection covers src/** and the app's vite idioms hold. */
const dashboardRoot = path.resolve(here, "../../../..");

export default defineConfig({
  root: dashboardRoot,
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(dashboardRoot, "src"),
    },
  },
  server: {
    port: 8188,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8177", changeOrigin: true },
    },
  },
  build: {
    outDir: "/tmp/sih26-analytics-dist",
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(here, "index.html"),
    },
  },
  preview: {
    port: 8188,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8177", changeOrigin: true },
    },
  },
});