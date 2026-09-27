import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HashRouter } from "react-router";
import "@fontsource-variable/inter/wght.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-mono/600.css";
import "@fontsource/ibm-plex-mono/700.css";
import "./index.css";
import App from "./App";
import { LangProvider } from "@/lib/lang";
import { ThemeProvider } from "@/lib/theme";

/* Providers: react-query (all data surfaces), theme + language contexts
 * (persist across routes), and the HashRouter — hash routing keeps the whole app
 * URL-addressable (/#/queue?fsi=0.8&range=90d&page=3) with zero FastAPI
 * changes; the route map itself lives in routes.tsx. */

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <LangProvider>
          <HashRouter>
            <App />
          </HashRouter>
        </LangProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
);
