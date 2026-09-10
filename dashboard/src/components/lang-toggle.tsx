import type { Lang } from "@/lib/phrasebook";
import { cn } from "@/lib/utils";

/** EN/हिं toggle — UI chrome only; report text is never translated live. */
export function LangToggle({
  lang,
  onChange,
}: {
  lang: Lang;
  onChange: (l: Lang) => void;
}) {
  return (
    <div className="flex items-center font-mono text-sm" role="group" aria-label="UI language">
      {(["en", "hi"] as const).map((l, i) => (
        <span key={l} className="flex items-center">
          {i > 0 && <span className="mx-1 text-border" aria-hidden>/</span>}
          <button
            type="button"
            aria-pressed={lang === l}
            onClick={() => onChange(l)}
            className={cn(
              "min-h-9 min-w-9 rounded-sm px-1 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
              lang === l
                ? "font-semibold text-foreground underline underline-offset-4"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {l === "en" ? "EN" : "हिं"}
          </button>
        </span>
      ))}
    </div>
  );
}
