import { Component, Suspense, lazy, type ComponentType, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router";
import { ChartNoAxesCombined, FilePlus2, History, ListChecks } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useLang } from "@/lib/lang";
import { t, type Lang } from "@/lib/phrasebook";

/* Route map — the single owner of URL structure. Mounted inside a HashRouter
 * (main.tsx): hash routing needs zero FastAPI changes and survives any static
 * file server.
 *
 * Route map:
 *   /              → redirect to /ingest (data in → result out is the core flow)
 *   /ingest        → add reports       (features/ingest)
 *   /queue         → reports history     (features/queue)
 *   /report/:id    → report detail     (features/report)
 *   /analytics     → risk trends       (features/analytics)
 *   /decisions     → decision log      (features/decisions)
 *
 * Shared-link filter state lives IN the URL, e.g. '#/queue?fsi=0.8&range=90d&page=3'
 * — the QUEUE feature reads/writes it via useSearchParams. No app state is
 * needed to reproduce a reviewer's screen.
 *
 * Feature pages are resolved at build time from src/features/<name>/index.tsx
 * or index.ts (spec §5 ownership — some features ship a plain TS barrel).
 * Surfaces whose module has not landed in this build yet
 * render an honest placeholder — never fabricated data, never a build break. */

const featureModules = import.meta.glob("/src/features/*/index.{ts,tsx}");

function featureLoader(
  dir: string,
): (() => Promise<{ default: ComponentType<{ lang?: Lang }> }>) | null {
  const entry = Object.entries(featureModules).find(([path]) =>
    path.startsWith(`/src/features/${dir}/`),
  );
  return entry
    ? (entry[1] as () => Promise<{ default: ComponentType<{ lang?: Lang }> }>)
    : null;
}

/** Route → feature directory (feature dir name may differ from URL path). */
const ROUTES = [
  { path: "/ingest", dir: "ingest" },
  { path: "/queue", dir: "queue" },
  { path: "/report/:id", dir: "report" },
  { path: "/analytics", dir: "analytics" },
  { path: "/decisions", dir: "decisions" },
] as const;

/** Shell navigation — derived from the route map, keys into the phrasebook.
 *  /report/:id is reachable from the queue and ingest results, not a nav item. */
export const NAV_ITEMS = [
  { to: "/ingest", labelKey: "tabIngest", icon: FilePlus2 },
  { to: "/queue", labelKey: "tabTriage", icon: ListChecks },
  { to: "/analytics", labelKey: "tabInsights", icon: ChartNoAxesCombined },
  { to: "/decisions", labelKey: "tabDecisions", icon: History },
] as const;

function RouteSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-busy="true">
      <div className="space-y-2">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-9 w-80" />
      </div>
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function PendingSurface() {
  const { lang } = useLang();
  return (
    <Card className="max-w-xl">
      <CardHeader title={t(lang, "routePending")} />
      <p className="text-sm text-content-secondary">{t(lang, "routePendingBody")}</p>
    </Card>
  );
}

/** Lazy page per feature dir, created ONCE at module scope — a lazy()
 *  component created during render would remount on every render. */
const PAGE_BY_DIR: Record<string, ComponentType<{ lang?: Lang }> | null> = Object.fromEntries(
  ROUTES.map(({ dir }) => {
    const loader = featureLoader(dir);
    return [dir, loader ? lazy(loader) : null];
  }),
);

function FeatureSurface({ dir }: { dir: string }) {
  const { lang } = useLang();
  const Page = PAGE_BY_DIR[dir];
  if (!Page) return <PendingSurface />;
  return (
    <Suspense fallback={<RouteSkeleton />}>
      <Page lang={lang} />
    </Suspense>
  );
}

/** Class error boundary — declarative <Routes> has no errorElement, so render
 *  errors land here with an honest card and a reload action. */
class RouteErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return <RouteErrorCard error={this.state.error} />;
    }
    return this.props.children;
  }
}

function RouteErrorCard({ error }: { error: Error }) {
  const { lang } = useLang();
  return (
    <Card className="max-w-xl">
      <CardHeader title={t(lang, "errorTitle")} />
      <p className="text-sm text-content-secondary">{t(lang, "errorBody")}</p>
      <p className="font-mono text-xs text-content-muted">{error.message}</p>
      <div>
        <Button variant="secondary" size="sm" onClick={() => window.location.reload()}>
          {t(lang, "reloadPage")}
        </Button>
      </div>
    </Card>
  );
}

function NotFound() {
  const { lang } = useLang();
  return (
    <Card className="max-w-xl">
      <CardHeader title={t(lang, "routeNotFound")} />
      <p className="text-sm text-content-secondary">{t(lang, "routeNotFoundBody")}</p>
    </Card>
  );
}

export function AppRoutes() {
  return (
    <RouteErrorBoundary>
      <Routes>
        <Route path="/" element={<Navigate to="/ingest" replace />} />
        <Route path="/settings" element={<Navigate to="/ingest" replace />} />
        {ROUTES.map(({ path, dir }) => (
          <Route key={path} path={path} element={<FeatureSurface dir={dir} />} />
        ))}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </RouteErrorBoundary>
  );
}
