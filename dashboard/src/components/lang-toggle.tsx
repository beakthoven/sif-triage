import { Languages } from "lucide-react";
import { Button } from "@/components/ui/button";
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
    <div className="flex items-center gap-1" role="group" aria-label="UI language">
      <Languages className="mr-1 size-4 text-muted-foreground" aria-hidden />
      {(["en", "hi"] as const).map((l) => (
        <Button
          key={l}
          variant={lang === l ? "default" : "ghost"}
          size="sm"
          aria-pressed={lang === l}
          onClick={() => onChange(l)}
          className={cn(
            "min-h-9 min-w-11 font-mono",
            lang === l && "bg-primary text-primary-foreground hover:bg-primary/90",
          )}
        >
          {l === "en" ? "EN" : "हिं"}
        </Button>
      ))}
    </div>
  );
}
