import { t, type Lang } from "@/lib/phrasebook";
import { cn } from "@/lib/utils";

/** EN/हिं toggle — UI chrome only; report text is never translated live.
 *  `chrome` sits on the deep-blue header; `surface` inside panels. */
export function LangToggle({
  lang,
  onChange,
  tone = "chrome",
}: {
  lang: Lang;
  onChange: (l: Lang) => void;
  tone?: "chrome" | "surface";
}) {
  const chrome = tone === "chrome";
  return (
    <div
      role="group"
      aria-label={t(lang, "langLabel")}
      className={cn(
        "flex items-center gap-0.5 rounded-md border p-0.5",
        chrome ? "border-chrome-border" : "border-border-subtle bg-surface-sunken",
      )}
    >
      {(["en", "hi"] as const).map((l) => (
        <button
          key={l}
          type="button"
          lang={l}
          aria-pressed={lang === l}
          onClick={() => onChange(l)}
          className={cn(
            "relative min-h-9 min-w-10 rounded-sm px-2 text-sm font-semibold transition-colors duration-150 after:absolute after:-inset-y-1 after:inset-x-0 after:content-['']",
            chrome
              ? lang === l
                ? "bg-chrome-bg-hover text-chrome-fg"
                : "text-chrome-fg-muted hover:text-chrome-fg"
              : lang === l
                ? "bg-surface-card text-content-primary shadow-sm"
                : "text-content-secondary hover:text-content-primary",
          )}
        >
          {l === "en" ? "EN" : "हिं"}
        </button>
      ))}
    </div>
  );
}
