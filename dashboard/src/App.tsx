import { useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router";
import { Info, Menu, ShieldCheck } from "lucide-react";
import { MotionProvider, Sheet, Toaster } from "@/components/ui";
import { LangToggle } from "@/components/lang-toggle";
import { ThemeMenu, ThemeSegmented } from "@/components/theme-menu";
import { LimitationsDialog } from "@/features/limitations/limitations-dialog";
import { useLang } from "@/lib/lang";
import { t } from "@/lib/phrasebook";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { AppRoutes, NAV_ITEMS } from "@/routes";

/* Application shell: sticky deep-blue header (identity, primary navigation,
 * theme + language), routed content, and the honest data disclosure footer.
 * No data logic lives here — surfaces fetch through @/lib/api hooks and own
 * their own states.
 *
 * MotionProvider wraps the shell so every motion/react animation honours
 * prefers-reduced-motion; the CSS media block in index.css covers CSS
 * transitions/animations. */

export default function App() {
  const { lang, setLang } = useLang();
  const { resolved } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const [limitsOpen, setLimitsOpen] = useState(false);
  const mainRef = useRef<HTMLElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const { pathname } = useLocation();
  const inReport = pathname.startsWith("/report/");

  return (
    <MotionProvider>
      <div className="flex min-h-dvh flex-col bg-surface-canvas text-content-primary">
        <a
          href="#main-content"
          onClick={(event) => {
            event.preventDefault();
            mainRef.current?.focus({ preventScroll: true });
            mainRef.current?.scrollIntoView({ block: "start" });
          }}
          className="fixed top-2 left-2 z-[60] -translate-y-24 rounded-md bg-action-primary px-4 py-3 text-sm font-semibold text-action-primary-fg shadow-lg transition-transform duration-150 focus:translate-y-0"
        >
          {t(lang, "skipContent")}
        </a>

        <header className="sticky top-0 z-40 border-b border-chrome-border bg-chrome-bg text-chrome-fg">
          <div className="page-shell flex h-14 items-center gap-4 lg:h-16 lg:gap-6">
            <Link
              to="/ingest"
              className="flex min-h-11 shrink-0 items-center gap-3 rounded-md"
              aria-label={t(lang, "appTitle")}
            >
              <span
                aria-hidden="true"
                className="grid size-9 place-items-center rounded-md bg-chrome-bg-hover ring-1 ring-chrome-border ring-inset"
              >
                <ShieldCheck className="size-5 text-chrome-fg" strokeWidth={2.25} />
              </span>
              <span className="hidden min-w-0 flex-col leading-tight xl:flex">
                <span className="text-base font-semibold">{t(lang, "appTitle")}</span>
                <span className="text-xs text-chrome-fg-muted">
                  {t(lang, "appSub")} · {t(lang, "hseOperations")}
                </span>
              </span>
              <span className="text-base font-semibold xl:hidden">{t(lang, "appTitleShort")}</span>
            </Link>

            <nav aria-label={t(lang, "mainNav")} className="hidden h-full lg:block">
              <ul className="flex h-full items-stretch gap-1">
                {NAV_ITEMS.map(({ to, labelKey, icon: Icon }) => (
                  <li key={to} className="flex">
                    <NavLink
                      to={to}
                      className={({ isActive }) => {
                        const active = isActive || (inReport && to === "/queue");
                        return cn(
                          "relative flex items-center gap-2 px-3 text-sm font-semibold whitespace-nowrap transition-colors duration-150",
                          "after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:rounded-full after:transition-colors after:duration-150",
                          active
                            ? "text-chrome-fg after:bg-action-primary"
                            : "text-chrome-fg-muted after:bg-transparent hover:text-chrome-fg",
                        );
                      }}
                    >
                      <Icon aria-hidden="true" className="hidden size-4 xl:block" />
                      {t(lang, labelKey)}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </nav>

            <div className="ml-auto flex shrink-0 items-center gap-2">
              <div className="hidden items-center gap-2 lg:flex">
                <ThemeMenu lang={lang} />
                <LangToggle lang={lang} onChange={setLang} />
              </div>
              <button
                ref={menuButtonRef}
                type="button"
                aria-label={t(lang, "openMenu")}
                aria-haspopup="dialog"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen(true)}
                className="grid size-11 place-items-center rounded-md text-chrome-fg transition-colors duration-150 hover:bg-chrome-bg-hover lg:hidden"
              >
                <Menu aria-hidden="true" className="size-6" />
              </button>
            </div>
          </div>
        </header>

        <Sheet
          open={menuOpen}
          onOpenChange={setMenuOpen}
          side="right"
          title={t(lang, "menuTitle")}
          closeLabel={t(lang, "close")}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            menuButtonRef.current?.focus({ preventScroll: true });
          }}
        >
          <nav aria-label={t(lang, "mainNav")}>
            <ul className="flex flex-col gap-1">
              {NAV_ITEMS.map(({ to, labelKey, icon: Icon }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    onClick={() => setMenuOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        "flex min-h-12 items-center gap-3 rounded-md border-l-2 px-4 text-base font-semibold transition-colors duration-150",
                        isActive || (inReport && to === "/queue")
                          ? "border-action-primary bg-action-secondary text-content-primary"
                          : "border-transparent text-content-secondary hover:bg-action-ghost-hover hover:text-content-primary",
                      )
                    }
                  >
                    <Icon aria-hidden="true" className="size-5 shrink-0" />
                    {t(lang, labelKey)}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
          <div className="mt-8 space-y-6 border-t border-border-subtle pt-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-content-secondary">{t(lang, "themeLabel")}</p>
              <ThemeSegmented lang={lang} />
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium text-content-secondary">{t(lang, "langLabel")}</p>
              <LangToggle lang={lang} onChange={setLang} tone="surface" />
            </div>
          </div>
        </Sheet>

        <main ref={mainRef} id="main-content" tabIndex={-1} className="page-shell min-w-0 flex-1 scroll-mt-20 py-6 outline-none md:py-8">
          <AppRoutes />
        </main>

        <footer className="border-t border-border-subtle bg-surface-card">
          <div className="page-shell flex flex-col gap-3 py-4 lg:flex-row lg:items-start lg:gap-6">
            <p className="text-sm font-medium text-content-primary">{t(lang, "footer")}</p>
            <p className="flex min-w-0 items-start gap-2 text-sm text-content-secondary lg:ml-auto">
              <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              <span>
                {t(lang, "footerDisclosure")}{" "}
                <button
                  type="button"
                  onClick={() => setLimitsOpen(true)}
                  className="font-semibold text-content-link underline underline-offset-2"
                >
                  {t(lang, "viewLimitations")}
                </button>
              </span>
            </p>
          </div>
        </footer>

        <LimitationsDialog lang={lang} open={limitsOpen} onOpenChange={setLimitsOpen} />
        <Toaster theme={resolved} />
      </div>
    </MotionProvider>
  );
}
