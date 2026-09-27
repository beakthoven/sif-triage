/* Dev-only harness: renders AnalyticsView standalone so the analytics slice
 * can be verified without touching App.tsx (SHELL's file). Serve with:
 *   cd dashboard && npx vite --config src/features/analytics/selfcheck/vite.config.ts
 * The /api proxy points at the live stack (read-only GETs only). */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "../../../index.css";
import AnalyticsView from "@/features/analytics";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <main id="main-content" className="page-shell py-6 sm:py-8">
      <AnalyticsView lang="en" />
    </main>
  </StrictMode>,
);