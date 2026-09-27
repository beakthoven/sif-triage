/* Dev-only mount for dev.html. Uses the queue page's own props contract
 * (onSelectReport / onOpenReport) so the shell wiring can be checked here
 * before routes.tsx exists. */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import QueuePage from "./QueuePage";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@/index.css";

function DevHarness() {
  const lang = new URLSearchParams(window.location.search).get("lang") === "hi" ? "hi" : "en";
  document.documentElement.lang = lang;
  return (
    <div className="min-h-screen bg-background p-6 font-sans">
      <QueuePage
        lang={lang}
        onSelectReport={(id) => console.log("[queue] select", id)}
        onOpenReport={(id) => console.log("[queue] open", id)}
      />
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <DevHarness />
  </StrictMode>,
);